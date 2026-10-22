"""
Resilience & Traffic Throttling Patterns:
1. Circuit Breaker: Martin Fowler / Netflix Hystrix pattern with sliding failure counting and half-open state testing.
2. SingleFlight: In-flight duplicate call suppression (Go sync/singleflight pattern) to prevent cache stampedes / thundering herd.
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Dict, Optional, Tuple


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Stateful circuit breaker with failure thresholds and recovery timeout.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()
        self._lock = threading.Lock()

    def execute(self, func: Callable[[], Any], current_time: Optional[float] = None) -> Any:
        now = time.time() if current_time is None else current_time

        with self._lock:
            # Check if OPEN duration has passed -> transition to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                else:
                    raise CircuitBreakerOpenException("Circuit breaker is OPEN. Fast failing request.")

        # Execute function
        try:
            result = func()
            self._on_success(now)
            return result
        except Exception as e:
            self._on_failure(now)
            raise e

    def _on_success(self, now: float):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                # Successfully recovered
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = now
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def _on_failure(self, now: float):
        with self._lock:
            self.failure_count += 1
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = now


class _InFlightCall:
    def __init__(self):
        self.event = threading.Event()
        self.val: Any = None
        self.err: Optional[Exception] = None


class SingleFlight:
    """
    Suppresses duplicate concurrent function calls for the same key.
    When N threads request the same key concurrently, only 1 execution occurs.
    The remaining N-1 callers wait and share the result.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: Dict[str, _InFlightCall] = {}

    def do(self, key: str, fn: Callable[[], Any]) -> Tuple[Any, bool]:
        """
        Executes fn for given key.
        Returns (result, was_shared).
        """
        call = None
        with self._lock:
            if key in self._calls:
                call = self._calls[key]
                first_caller = False
            else:
                call = _InFlightCall()
                self._calls[key] = call
                first_caller = True

        if not first_caller:
            # Wait for leader thread to finish execution
            call.event.wait()
            if call.err is not None:
                raise call.err
            return call.val, True

        # First caller executes the target function
        try:
            val = fn()
            call.val = val
        except Exception as err:
            call.err = err
        finally:
            with self._lock:
                self._calls.pop(key, None)
            call.event.set()

        if call.err is not None:
            raise call.err
        return call.val, False
