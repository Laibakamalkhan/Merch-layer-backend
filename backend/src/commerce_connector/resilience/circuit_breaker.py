import time
from collections import defaultdict
from dataclasses import dataclass
from commerce_connector.core.exceptions import CircuitOpenError

@dataclass
class CircuitState:
    failures: int = 0
    open_until: float = 0.0

class CircuitBreaker:
    def __init__(self, enabled, failure_threshold, recovery_timeout_seconds):
        self.enabled = enabled
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.states = defaultdict(CircuitState)
    def before_request(self,key):
        if not self.enabled:return
        state = self.states[key]
        if state.open_until > time.monotonic():
            raise CircuitOpenError(f"Circuit breaker is open for {key}")
        if state.open_until: state.open_until = 0
    def success(self,key):
        if self.enabled:self.states[key] = CircuitState()
    def failure(self,key):
        if not self.enabled:return
        state = self.states[key]; state.failures += 1
        if state.failures >= self.failure_threshold:
            state.open_until = time.monotonic()+self.recovery_timeout_seconds
