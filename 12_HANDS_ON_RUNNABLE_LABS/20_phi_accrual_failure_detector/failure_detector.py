"""
Hayashibara's Phi (Φ) Accrual Failure Detector.

Features:
1. Replaces binary alive/dead timeouts with a continuous suspicion metric Φ.
2. Sliding window of heartbeat arrival intervals.
3. Gaussian cumulative distribution function (CDF) calculation.
4. Scale:
   - Φ = 1 -> 10% chance delay is normal network jitter.
   - Φ = 2 -> 1% chance.
   - Φ = 8 -> 10^-8 chance (Cassandra default threshold for dead node eviction).
"""

import math
import time
from typing import List, Optional
from collections import deque


class PhiAccrualFailureDetector:
    def __init__(self, threshold: float = 8.0, max_sample_size: int = 1000, min_std_dev: float = 0.1):
        self.threshold = threshold
        self.max_sample_size = max_sample_size
        self.min_std_dev = min_std_dev

        self.intervals: deque = deque(maxlen=max_sample_size)
        self.last_heartbeat_time: Optional[float] = None

    def heartbeat(self, timestamp: Optional[float] = None) -> None:
        now = time.time() if timestamp is None else timestamp

        if self.last_heartbeat_time is not None:
            interval = now - self.last_heartbeat_time
            if interval > 0:
                self.intervals.append(interval)

        self.last_heartbeat_time = now

    def _mean_and_std(self) -> (float, float):
        if not self.intervals:
            return 1.0, self.min_std_dev

        mean = sum(self.intervals) / len(self.intervals)
        variance = sum((x - mean) ** 2 for x in self.intervals) / len(self.intervals)
        std_dev = max(math.sqrt(variance), self.min_std_dev)
        return mean, std_dev

    def phi(self, current_time: Optional[float] = None) -> float:
        if self.last_heartbeat_time is None or not self.intervals:
            return 0.0

        now = time.time() if current_time is None else current_time
        delta_t = now - self.last_heartbeat_time

        if delta_t <= 0:
            return 0.0

        mean, std_dev = self._mean_and_std()

        # Gaussian survival function: P_later(t) = 1 - CDF(t)
        # CDF(t) = 0.5 * (1 + erf((t - mean) / (std_dev * sqrt(2))))
        z = (delta_t - mean) / (std_dev * math.sqrt(2))
        cdf = 0.5 * (1.0 + math.erf(z))
        p_later = max(1.0 - cdf, 1e-15)  # Avoid math domain error with log10(0)

        phi_val = -math.log10(p_later)
        return max(phi_val, 0.0)

    def is_suspect(self, current_time: Optional[float] = None) -> bool:
        return self.phi(current_time) >= self.threshold
