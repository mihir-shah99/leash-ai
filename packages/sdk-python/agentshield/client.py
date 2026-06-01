import logging
import uuid
import threading
import queue
import httpx
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AgentShieldClient:
    """Synchronous client with background thread queueing for AgentShield telemetry."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.agentshield.dev"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._telemetry_queue = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        
        # Start the background worker thread for telemetry
        self._worker_thread = threading.Thread(target=self._telemetry_worker, daemon=True)
        self._worker_thread.start()

    def _telemetry_worker(self):
        """Background thread that consumes telemetry events and sends them synchronously."""
        # Create a single sync httpx client for this thread
        with httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=5.0
        ) as client:
            while not self._stop_event.is_set() or not self._telemetry_queue.empty():
                try:
                    # Wait up to 1 second for an event
                    event = self._telemetry_queue.get(timeout=1.0)
                    
                    try:
                        response = client.post(
                            f"{self.base_url}/v1/telemetry/ingest",
                            json=event
                        )
                        response.raise_for_status()
                    except Exception as e:
                        # In production, we'd add exponential backoff/retry here.
                        # For now, just log and discard to prevent queue explosion.
                        logger.error(f"Failed to send telemetry to AgentShield: {e}")
                    finally:
                        self._telemetry_queue.task_done()
                        
                except queue.Empty:
                    # Queue is empty, loop again
                    continue
                except Exception as e:
                    logger.error(f"AgentShield telemetry worker error: {e}")

    def send_audit_event_fire_and_forget(self, event: Dict[str, Any]) -> None:
        """Fire off an audit event without blocking the current thread by adding to the queue."""
        payload = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action_type": event.get("action_type", "unknown"),
            "action_detail": event.get("action_detail", {}),
            "policy_decision": event.get("decision", "ALLOW"),
            "policy_reason": event.get("violations", [""])[0] if event.get("violations") else "All policies passed.",
            "evaluation_duration_ms": 1.5
        }
        
        try:
            self._telemetry_queue.put_nowait(payload)
        except queue.Full:
            logger.warning("AgentShield telemetry queue full. Dropping event.")

    def sync_policies(self) -> Dict[str, Any]:
        """Fetch the latest policies from the control plane synchronously (used by SDK init)."""
        with httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=5.0
        ) as client:
            response = client.get(f"{self.base_url}/v1/policies/sync")
            response.raise_for_status()
            return response.json()

    def close(self):
        """Signal the worker thread to stop and wait for it to flush the queue."""
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
