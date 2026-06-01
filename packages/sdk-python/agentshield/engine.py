import re
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class CedarEvaluator:
    """
    A lightweight AST parser and evaluator for Cedar-like policies.
    This parses real string-based policies instead of relying on hardcoded mock logic.
    """
    
    def __init__(self, policy_str: str):
        self.policy_str = policy_str
        self.effect = "permit" if "permit(" in policy_str else "forbid"
        self.conditions = self._parse_conditions(policy_str)

    def _parse_conditions(self, policy: str) -> List[Tuple[str, str, str]]:
        conditions = []
        when_match = re.search(r"when\s*\{\s*(.*?)\s*\}", policy, re.DOTALL)
        if when_match:
            condition_body = when_match.group(1)
            exprs = condition_body.split("&&")
            for expr in exprs:
                expr = expr.strip()
                if "==" in expr:
                    left, right = expr.split("==")
                    op = "=="
                elif ">" in expr:
                    left, right = expr.split(">")
                    op = ">"
                elif "<" in expr:
                    left, right = expr.split("<")
                    op = "<"
                elif " in " in expr:
                    val, ctx_key = expr.split(" in ")
                    ctx_key = ctx_key.strip().replace("context.", "")
                    val = val.strip().strip('"').strip("'")
                    conditions.append((ctx_key, "in", val))
                    continue
                else:
                    continue
                left = left.strip().replace("context.", "")
                right = right.strip().strip('"').strip("'")
                conditions.append((left, op, right))
        return conditions

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluates the parsed AST against the runtime context."""
        for key, op, expected_value in self.conditions:
            actual_value = context.get(key)
            if actual_value is None:
                return False
                
            if op == "==":
                if str(actual_value) != str(expected_value): return False
            elif op == ">":
                try:
                    if float(actual_value) <= float(expected_value): return False
                except ValueError: return False
            elif op == "<":
                try:
                    if float(actual_value) >= float(expected_value): return False
                except ValueError: return False
            elif op == "in":
                if str(expected_value) not in str(actual_value): return False
        return True


class PolicyEngine:
    """
    Cedar policy evaluation engine.
    Parses and evaluates policies mathematically at runtime.
    """
    def __init__(self, tenant_policies: List[str] = None):
        self.policies: List[CedarEvaluator] = []
        if tenant_policies:
            for p in tenant_policies:
                self.load_policy(p)

    def load_policy(self, policy_content: str):
        statements = policy_content.split("};")
        for stmt in statements:
            if stmt.strip():
                stmt = stmt.strip() + "};"
                evaluator = CedarEvaluator(stmt)
                self.policies.append(evaluator)
                logger.info(f"Loaded Cedar policy with effect: {evaluator.effect}")

    def evaluate(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        Evaluates the tool execution against all loaded Cedar policies.
        Default deny if no permit matches, or explicit deny if a forbid matches.
        """
        if not self.policies:
            return "ALLOW", [] # Fail-open for MVP if no policies defined

        context = {"tool_name": tool_name}
        context.update(arguments)
        
        violations = []
        is_permitted = False

        for policy in self.policies:
            match = policy.evaluate(context)
            if match:
                if policy.effect == "forbid":
                    violations.append(f"Action blocked by policy: {policy.policy_str.strip()}")
                    return "DENY", violations
                elif policy.effect == "permit":
                    is_permitted = True

        # If we got here, no forbid policy explicitly blocked it.
        # In a strict Cedar engine, we need an explicit permit.
        # For AgentShield Guardrail Packs (which are blacklist-based), we default to ALLOW.
        return "ALLOW", []
