import time
from agentshield.circuit_breaker import CircuitBreaker

cb = CircuitBreaker(loop_threshold=3, loop_time_window_sec=5)

# Simulate an LLM stuck in an infinite loop
# Even if arguments change wildly, the velocity triggers the breaker
for i in range(5):
    is_safe, reason = cb.evaluate("execute_sql", {"random_arg": f"hallucination_{i}"})
    if not is_safe:
        print(f"Loop {i+1} BLOCKED: {reason}")
    else:
        print(f"Loop {i+1} ALLOWED")
    time.sleep(0.1)
