"""
Twitter Snowflake 64-Bit Unique ID Generator.

Bit Layout:
- 1 bit: Sign bit (always 0)
- 41 bits: Millisecond timestamp from custom epoch (~69 years)
- 5 bits: Datacenter ID (0 - 31)
- 5 bits: Worker / Machine ID (0 - 31)
- 12 bits: Sequence number (0 - 4095 per millisecond)
"""

import threading
import time
from typing import Dict


class ClockMovedBackwardsError(Exception):
    pass


class SnowflakeGenerator:
    """
    Thread-safe Twitter Snowflake 64-bit ID generator.
    """

    # Bit allocation constants
    TIMESTAMP_BITS = 41
    DATACENTER_BITS = 5
    WORKER_BITS = 5
    SEQUENCE_BITS = 12

    MAX_DATACENTER_ID = (1 << DATACENTER_BITS) - 1  # 31
    MAX_WORKER_ID = (1 << WORKER_BITS) - 1          # 31
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1          # 4095

    # Shift offsets
    WORKER_SHIFT = SEQUENCE_BITS
    DATACENTER_SHIFT = SEQUENCE_BITS + WORKER_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_BITS + DATACENTER_BITS

    def __init__(
        self,
        datacenter_id: int,
        worker_id: int,
        custom_epoch: int = 1767225600000,  # 2026-01-01T00:00:00Z UTC
    ):
        if not (0 <= datacenter_id <= self.MAX_DATACENTER_ID):
            raise ValueError(f"datacenter_id must be between 0 and {self.MAX_DATACENTER_ID}")
        if not (0 <= worker_id <= self.MAX_WORKER_ID):
            raise ValueError(f"worker_id must be between 0 and {self.MAX_WORKER_ID}")

        self.datacenter_id = datacenter_id
        self.worker_id = worker_id
        self.custom_epoch = custom_epoch

        self.sequence = 0
        self.last_timestamp = -1
        self._lock = threading.Lock()

    def _get_current_ms(self) -> int:
        return int(time.time() * 1000)

    def generate_id(self) -> int:
        """Generates a globally unique 64-bit integer ID."""
        with self._lock:
            now_ms = self._get_current_ms()

            # Handle clock skew (NTP adjustment backwards)
            if now_ms < self.last_timestamp:
                drift = self.last_timestamp - now_ms
                if drift <= 5:
                    # Small drift: busy-wait until clock catches up
                    while now_ms < self.last_timestamp:
                        time.sleep(0.001)
                        now_ms = self._get_current_ms()
                else:
                    raise ClockMovedBackwardsError(
                        f"Clock drifted backwards by {drift}ms! Refusing to generate ID."
                    )

            if now_ms == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    # Sequence space exhausted for this millisecond! Wait for next ms
                    while now_ms <= self.last_timestamp:
                        time.sleep(0.0001)
                        now_ms = self._get_current_ms()
            else:
                self.sequence = 0

            self.last_timestamp = now_ms

            # Bitwise compose 64-bit integer
            time_delta = now_ms - self.custom_epoch
            id_64 = (
                (time_delta << self.TIMESTAMP_SHIFT)
                | (self.datacenter_id << self.DATACENTER_SHIFT)
                | (self.worker_id << self.WORKER_SHIFT)
                | self.sequence
            )
            return id_64

    def parse_id(self, id_64: int) -> Dict[str, int]:
        """Deconstructs a 64-bit Snowflake ID into its constituent components."""
        sequence = id_64 & self.MAX_SEQUENCE
        worker_id = (id_64 >> self.WORKER_SHIFT) & self.MAX_WORKER_ID
        datacenter_id = (id_64 >> self.DATACENTER_SHIFT) & self.MAX_DATACENTER_ID
        time_delta = id_64 >> self.TIMESTAMP_SHIFT
        timestamp_ms = time_delta + self.custom_epoch

        return {
            "id": id_64,
            "timestamp_ms": timestamp_ms,
            "datacenter_id": datacenter_id,
            "worker_id": worker_id,
            "sequence": sequence,
        }
