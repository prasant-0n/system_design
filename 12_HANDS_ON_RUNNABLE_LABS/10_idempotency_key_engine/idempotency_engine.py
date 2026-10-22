"""
API Idempotency Key Middleware & Deduplication Engine (Stripe-Style).

Ensures that repeated client requests carrying the same Idempotency-Key
produce the exact same response without re-executing state mutations or charging cards twice.
"""

from enum import Enum
import hashlib
import json
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple


class IdempotencyStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IdempotencyConflictError(Exception):
    """Raised when the same key is reused with a different request payload."""
    pass


class ConcurrentRequestError(Exception):
    """Raised when an identical request is already actively processing."""
    pass


class IdempotencyRecord:
    def __init__(self, key: str, payload_hash: str):
        self.key = key
        self.payload_hash = payload_hash
        self.status = IdempotencyStatus.IN_PROGRESS
        self.status_code: Optional[int] = None
        self.response_body: Optional[Any] = None
        self.created_at = time.time()


class IdempotencyEngine:
    """
    Thread-safe API Idempotency Manager.
    """

    def __init__(self, ttl_seconds: float = 3600.0):
        self.ttl_seconds = ttl_seconds
        self.records: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def _hash_payload(self, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def execute(
        self,
        idempotency_key: str,
        payload: Any,
        handler_fn: Callable[[Any], Tuple[int, Any]],
    ) -> Tuple[int, Any, bool]:
        """
        Executes handler_fn with idempotency protection.
        Returns: (http_status, response_payload, is_cached_replay)
        """
        payload_hash = self._hash_payload(payload)

        with self._lock:
            # Check existing record
            if idempotency_key in self.records:
                record = self.records[idempotency_key]

                # 1. Payload validation: Detect key reuse with different parameters
                if record.payload_hash != payload_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency-Key '{idempotency_key}' was previously used with a different request payload!"
                    )

                # 2. Concurrency check: Request is already executing
                if record.status == IdempotencyStatus.IN_PROGRESS:
                    raise ConcurrentRequestError(
                        f"A request with Idempotency-Key '{idempotency_key}' is currently in progress."
                    )

                # 3. Completed: Return cached response!
                if record.status == IdempotencyStatus.COMPLETED:
                    return record.status_code, record.response_body, True

            # Register new IN_PROGRESS transaction
            record = IdempotencyRecord(idempotency_key, payload_hash)
            self.records[idempotency_key] = record

        # Execute business logic outside the central lock to allow concurrency across distinct keys
        try:
            status_code, response_body = handler_fn(payload)
            with self._lock:
                record.status = IdempotencyStatus.COMPLETED
                record.status_code = status_code
                record.response_body = response_body
            return status_code, response_body, False
        except Exception as e:
            with self._lock:
                record.status = IdempotencyStatus.FAILED
                # Remove on failure so client can retry with same key
                del self.records[idempotency_key]
            raise e
