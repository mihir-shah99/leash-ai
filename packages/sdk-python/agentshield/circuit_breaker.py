import time
from typing import Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    State-Aware Circuit Breaker for Runaway AI Agents.
    Uses a sliding time-window to detect high-velocity loops,
    independent of argument hallucinations.
    """
    def __init__(self, max_calls_per_minute: int = 60, loop_threshold: int = 4, loop_time_window_sec: int = 10):
        self.max_calls_per_minute = max_calls_per_minute
        
        # Loop detection settings
        self.loop_threshold = loop_threshold
        self.loop_time_window_sec = loop_time_window_sec
        
        # In-memory state tracking: { "tool_name": [timestamp1, timestamp2, ...] }
        self.execution_history: Dict[str, List[float]] = {}
        
        # Global counter for rate limiting
        self.global_history: List[float] = []

    def _clean_old_timestamps(self, current_time: float):
        """Removes timestamps older than 60 seconds from global history."""
        sixty_secs_ago = current_time - 60
        self.global_history = [t for t in self.global_history if t > sixty_secs_ago]
        
        # Clean specific tool histories based on loop window
        loop_window_start = current_time - self.loop_time_window_sec
        for tool, timestamps in self.execution_history.items():
            self.execution_history[tool] = [t for t in timestamps if t > loop_window_start]

    def evaluate(self, tool_name: str, kwargs: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates the current state against circuit breaker limits.
        Returns (is_safe, reason).
        """
        current_time = time.time()
        self._clean_old_timestamps(current_time)

        # 1. Global Rate Limiting
        if len(self.global_history) >= self.max_calls_per_minute:
            return False, f"Global Rate Limit Exceeded: Agent executed {self.max_calls_per_minute} tools in 60s."

        # 2. Semantic Loop Detection (High-velocity identical tool calls)
        tool_history = self.execution_history.get(tool_name, [])
        if len(tool_history) >= self.loop_threshold:
            return False, f"Runaway Agent Loop Detected: Agent called '{tool_name}' {self.loop_threshold} times in {self.loop_time_window_sec}s."

        # Action is safe, record it
        self.global_history.append(current_time)
        if tool_name not in self.execution_history:
            self.execution_history[tool_name] = []
        self.execution_history[tool_name].append(current_time)

        return True, ""
