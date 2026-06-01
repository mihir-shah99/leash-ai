"""Assertion-based tests for the runaway-agent circuit breaker."""
from agentshield.circuit_breaker import CircuitBreaker


def test_loop_threshold_trips_regardless_of_arguments():
    cb = CircuitBreaker(loop_threshold=3, loop_time_window_sec=5)
    results = [
        cb.evaluate("execute_sql", {"random_arg": f"hallucination_{i}"})[0]
        for i in range(5)
    ]
    # First (threshold) calls allowed, then the breaker trips — argument
    # variation does not matter, only call velocity.
    assert results[:3] == [True, True, True]
    assert results[3] is False


def test_global_rate_limit():
    cb = CircuitBreaker(max_calls_per_minute=5, loop_threshold=1000)
    allowed = [cb.evaluate(f"tool_{i}", {})[0] for i in range(7)]
    assert allowed[:5] == [True] * 5
    assert allowed[5] is False


def test_distinct_tools_have_independent_loop_counters():
    cb = CircuitBreaker(loop_threshold=2, loop_time_window_sec=5, max_calls_per_minute=1000)
    assert cb.evaluate("a", {})[0] is True
    assert cb.evaluate("a", {})[0] is True
    assert cb.evaluate("a", {})[0] is False  # 'a' tripped
    assert cb.evaluate("b", {})[0] is True   # 'b' independent
