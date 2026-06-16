from functools import wraps
from typing import Callable, Any, List, Dict, Union
import os
import logging
import threading
import time

from .engine import PolicyEngine
from .client import AgentShieldClient
from .packs import Packs
from .circuit_breaker import CircuitBreaker
from .pii import PIIRedactor

logger = logging.getLogger(__name__)

class PolicyViolationError(Exception):
    """Exception raised when an agent action violates a security policy."""
    pass

class AgentShield:
    """
    Main entry point for AgentShield local evaluation.
    """
    Packs = Packs
    
    _instance = None

    def __init__(self, tenant_id: str = None, api_key: str = None, control_plane_url: str = None, base_url: str = None, guardrails: List[Dict] = None, pii_mode: str = "edge", default_effect: str = "allow", fail_closed: bool = True):
        """
        Initialize the local agent governance engine.
        `guardrails` allows loading Packs (e.g. AgentShield.Packs.OWASP_TOP_10) locally out-of-the-box.
        Supports both api_key/tenant_id and control_plane_url/base_url parameters for compatibility.

        `default_effect` ("allow"|"deny") sets the posture when no policy matches.
        `fail_closed` makes indeterminate comparisons resolve toward blocking.
        """
        self.tenant_id = api_key or tenant_id or os.environ.get("AGENT_SHIELD_API_KEY")
        if not self.tenant_id:
            self.tenant_id = "default_tenant"

        self.control_plane_url = base_url or control_plane_url or os.environ.get("AGENT_SHIELD_BASE_URL", "http://localhost:8000")
        self.pii_mode = pii_mode
        self.default_effect = default_effect
        self.fail_closed = fail_closed
        self.engine = PolicyEngine(default_effect=default_effect, fail_closed=fail_closed)
        self.client = AgentShieldClient(api_key=self.tenant_id, base_url=self.control_plane_url)
        self.circuit_breaker = CircuitBreaker()
        # Tracks whether the most recent control-plane sync succeeded. When False
        # the SDK is enforcing a potentially stale ruleset; surfaced for callers
        # that want to alert on a degraded governance state.
        self.last_sync_ok = False
        
        self._guardrails_cache = guardrails or []
        if guardrails:
            for pack in guardrails:
                self.engine.load_policy(pack["content"])
                logger.info(f"Loaded Guardrail Pack: {pack['name']}")

        AgentShield._instance = self
        logger.info("AgentShield initialized with PII Redaction and Circuit Breakers.")
        
        # Start background policy sync thread
        self._stop_sync = threading.Event()
        self._sync_thread = threading.Thread(target=self._sync_policies_loop, daemon=True)
        self._sync_thread.start()

    def _sync_policies_loop(self):
        """Poll the control plane periodically for updated policies in a background thread."""
        time.sleep(1.0)
        while not self._stop_sync.is_set():
            try:
                import httpx
                headers = {"Authorization": f"Bearer {self.tenant_id}"}
                with httpx.Client(timeout=5.0, headers=headers) as client:
                    response = client.get(f"{self.control_plane_url}/v1/policies/sync")
                    if response.status_code == 200:
                        data = response.json()
                        policies = data.get("policies", [])

                        new_engine = PolicyEngine(
                            default_effect=self.default_effect,
                            fail_closed=self.fail_closed,
                        )

                        # Re-load static local packs
                        if self._guardrails_cache:
                            for pack in self._guardrails_cache:
                                new_engine.load_policy(pack["content"])

                        # Load dynamic policies
                        for p in policies:
                            new_engine.load_policy(p["content"])

                        self.engine = new_engine
                        self.last_sync_ok = True
                        logger.info(f"Dynamically synced {len(policies)} policies from Control Plane.")
                    else:
                        self.last_sync_ok = False
                        logger.warning(
                            f"Policy sync returned HTTP {response.status_code}; "
                            f"continuing with the previously loaded ruleset."
                        )
            except Exception as e:
                # Keep enforcing the last-known-good ruleset, but make the degraded
                # state visible rather than swallowing it at debug level.
                self.last_sync_ok = False
                logger.warning(
                    f"Failed to sync policies from Control Plane ({e}); "
                    f"continuing with the previously loaded ruleset."
                )
            
            # Poll every 10 seconds, but check _stop_sync frequently
            for _ in range(10):
                if self._stop_sync.is_set():
                    break
                time.sleep(1.0)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("AgentShield is not initialized. Instantiate it before running agents.")
        return cls._instance

    def check_action(self, tool_name: str, args: Dict[str, Any]):
        """Evaluate a raw tool call without throwing an exception (for Proxies)."""
        # 1. Circuit Breaker
        is_safe, cb_reason = self.circuit_breaker.evaluate(tool_name, args)
        if not is_safe:
            return type('Decision', (), {'allowed': False, 'reason': cb_reason})()
            
        # 2. Local Kernel Evaluation
        decision_str, violations = self.engine.evaluate(tool_name, args)
        
        # 3. Telemetry (Async)
        safe_args = PIIRedactor.redact_payload(args, self.pii_mode)
        try:
            self.client.send_audit_event_fire_and_forget({
                "agent_id": "mcp_gateway",
                "action_type": tool_name,
                "action_detail": {"tool_name": tool_name, "arguments": safe_args},
                "decision": decision_str,
                "violations": violations
            })
        except Exception:
            pass
            
        if decision_str == "DENY":
            return type('Decision', (), {'allowed': False, 'reason': violations[0] if violations else "Denied by policy"})()
            
        return type('Decision', (), {'allowed': True, 'reason': ""})()

    def _evaluate_and_run(self, func: Callable, action_type: str, *args, **kwargs):
        """Core evaluation logic applied by the decorator."""
        # 1. CIRCUIT BREAKER EVALUATION (Stateful protection)
        is_safe, cb_reason = self.circuit_breaker.evaluate(action_type, kwargs)
        if not is_safe:
            logger.warning(f"AgentShield CIRCUIT BREAKER TRIPPED: {cb_reason}")
            
            # Report telemetry even for circuit breaker trips
            safe_kwargs = PIIRedactor.redact_payload(kwargs, self.pii_mode)
            try:
                self.client.send_audit_event_fire_and_forget({
                    "agent_id": "local_agent",
                    "action_type": action_type,
                    "action_detail": {"tool_name": func.__name__, "arguments": safe_kwargs},
                    "decision": "DENY",
                    "violations": [cb_reason]
                })
            except Exception:
                pass
            raise PolicyViolationError(f"Action blocked by AgentShield Circuit Breaker: {cb_reason}")

        # 2. LOCAL KERNEL EVALUATION
        decision, violations = self.engine.evaluate(action_type, kwargs)

        # 3. PII REDACTION (Before Telemetry)
        safe_kwargs = PIIRedactor.redact_payload(kwargs, self.pii_mode)

        # 4. ASYNC TELEMETRY OFF-LOADING
        try:
            self.client.send_audit_event_fire_and_forget({
                "agent_id": "langchain_agent",
                "action_type": action_type,
                "action_detail": {"tool_name": func.__name__, "arguments": safe_kwargs},
                "decision": decision,
                "violations": violations
            })
        except Exception as e:
            logger.error(f"Telemetry failed: {e}")

        # 5. ENFORCEMENT
        if decision == "DENY":
            logger.warning(f"AgentShield BLOCKED action '{func.__name__}'. Reason: {violations[0]}")
            raise PolicyViolationError(f"Action blocked by AgentShield: {violations[0]}")
        
        return func(*args, **kwargs)

    def govern(self, action_type_or_func: Any = None):
        """
        Decorator to wrap any Python function (tool call) with AgentShield evaluation.
        Supports:
            @shield.govern
            def my_tool(...)
        and:
            @shield.govern("financial")
            def my_tool(...)
        """
        if isinstance(action_type_or_func, str):
            action_type = action_type_or_func
            def decorator(func: Callable):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    return self._evaluate_and_run(func, action_type, *args, **kwargs)
                return wrapper
            return decorator
        else:
            func = action_type_or_func
            action_type = func.__name__ if func else "default"
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self._evaluate_and_run(func, action_type, *args, **kwargs)
            return wrapper

    def close(self):
        """Stop background threads and clean up resources."""
        self._stop_sync.set()
        if hasattr(self, "_sync_thread"):
            self._sync_thread.join(timeout=1.0)

# Global fallback decorator for compatibility
def govern(action_type: str):
    """
    Decorator to wrap any Python function (tool call) with AgentShield evaluation.
    Requires AgentShield to be initialized first.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            shield = AgentShield.get_instance()
            return shield._evaluate_and_run(func, action_type, *args, **kwargs)
        return wrapper
    return decorator
