import time
import logging
from agentshield import AgentShield, PolicyViolationError

logging.basicConfig(level=logging.INFO)

# 1. Initialize the SDK with real local Cedar policies
shield = AgentShield(
    api_key="sk_test_123", 
    base_url="http://localhost:8000",
    guardrails=[
        {"name": "financial_safety", "content": AgentShield.Packs.FINANCIAL}
    ]
)

# 2. Protect a tool using the decorator
# We govern it as "issue_refund" so it matches the Cedar policy rule
@shield.govern("issue_refund")
def issue_refund(amount: float, customer_id: str):
    """A sensitive business operation."""
    print(f"[EXECUTING] Issuing refund of ${amount} to {customer_id}")
    return {"status": "success", "amount": amount}

# 3. Simulate Agent Actions
if __name__ == "__main__":
    print("--- Test 1: Allowed Action ---")
    try:
        # A $100 refund should be allowed by our mock engine
        issue_refund(amount=100.0, customer_id="cust_abc123")
        print("Test 1 Passed: Action was allowed.")
    except Exception as e:
        print(f"Test 1 Failed: {e}")

    print("\n--- Test 2: Blocked Action (Deterministic Guardrail) ---")
    try:
        # A $10,000 refund should be deterministically BLOCKED
        issue_refund(amount=10000.0, customer_id="cust_xyz987")
        print("Test 2 Failed: Action should have been blocked!")
    except PolicyViolationError as e:
        print(f"Test 2 Passed: Action successfully blocked -> {e}")

    # Give telemetry a moment to fire off in the background
    time.sleep(1)
