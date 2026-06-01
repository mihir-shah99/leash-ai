import logging
import json
from typing import Any, Dict, List
from langchain_core.callbacks import BaseCallbackHandler

from agentshield.shield import AgentShield
from agentshield.pii import PIIRedactor

logger = logging.getLogger(__name__)

class AgentShieldBlockedError(Exception):
    """Exception raised when AgentShield blocks a tool execution."""
    pass

class AgentShieldCallback(BaseCallbackHandler):
    """
    Official, async-native LangChain callback handler.
    Intercepts tools dynamically without monkey-patching.
    """
    
    def __init__(self):
        super().__init__()
        # Ensure AgentShield is initialized
        self.shield = AgentShield.get_instance()

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> Any:
        """Run when tool starts running."""
        tool_name = serialized.get("name", "unknown_tool")
        
        # Parse arguments safely
        try:
            # Sometimes inputs are passed in kwargs, otherwise we try to parse the string
            arguments = kwargs.get("inputs", {})
            if not arguments and input_str:
                try:
                    arguments = json.loads(input_str)
                except Exception:
                    arguments = {"input": input_str}
        except Exception:
            arguments = {"raw_input": input_str}
            
        # 1. Circuit Breaker Evaluation
        is_safe, cb_reason = self.shield.circuit_breaker.evaluate(tool_name, arguments)
        if not is_safe:
            logger.warning(f"CIRCUIT BREAKER TRIPPED for LangChain tool {tool_name}: {cb_reason}")
            self._send_telemetry_fire_and_forget(tool_name, arguments, "DENY", [cb_reason])
            raise AgentShieldBlockedError(f"Circuit Breaker tripped: {cb_reason}")

        # 2. Local Policy Evaluation
        decision, violations = self.shield.engine.evaluate(tool_name, arguments)

        # 3. PII Redaction
        safe_kwargs = PIIRedactor.redact_payload(arguments)

        # 4. Telemetry Off-loading
        self._send_telemetry_fire_and_forget(tool_name, safe_kwargs, decision, violations)

        # 5. Enforcement
        if decision == "DENY":
            logger.warning(f"AgentShield BLOCKED LangChain tool '{tool_name}'.")
            raise AgentShieldBlockedError(f"AgentShield Security Block: {violations[0]}")

    def _send_telemetry_fire_and_forget(self, tool_name: str, arguments: Dict[str, Any], decision: str, violations: List[str]):
        """Enqueue telemetry on the client's background worker thread.

        This is non-blocking and event-loop-safe: the SDK client owns a daemon
        thread with a bounded queue, so we never touch asyncio here (which is
        what previously crashed sync agents and silently dropped every event).
        """
        event_dict = {
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "action_type": tool_name,
            "action_detail": {"tool_name": tool_name, "arguments": arguments},
            "decision": decision,
            "violations": violations,
        }
        try:
            self.shield.client.send_audit_event_fire_and_forget(event_dict)
        except Exception as e:
            logger.error(f"Telemetry failed: {e}")
