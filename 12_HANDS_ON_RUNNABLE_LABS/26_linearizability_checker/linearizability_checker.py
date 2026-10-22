"""
Distributed Linearizability Checker (Mini-Jepsen / Wing & Gong Algorithm).

Features:
1. Validates concurrent execution logs against sequential Register specifications.
2. Models invocation and completion time intervals [invoke_time, return_time].
3. Backtracking state-space search to find a valid linearization.
4. Detects stale reads, lost updates, and causal violations.
"""

from typing import List, Optional, Any


class Operation:
    def __init__(
        self,
        op_id: str,
        process_id: str,
        op_type: str,  # "write" or "read"
        val: Any,
        invoke_time: float,
        return_time: float,
    ):
        self.op_id = op_id
        self.process_id = process_id
        self.op_type = op_type
        self.val = val
        self.invoke_time = invoke_time
        self.return_time = return_time

    def __repr__(self):
        return f"Op({self.op_id}: {self.op_type}({self.val}) [{self.invoke_time}..{self.return_time}])"


class RegisterLinearizabilityChecker:
    """
    Validates whether a concurrent execution history of a single-register
    key-value store is Linearizable.
    """

    def is_linearizable(self, history: List[Operation], initial_val: Any = None) -> bool:
        if not history:
            return True

        # Sort operations by invocation time
        ops = list(history)

        def search(remaining_ops: List[Operation], current_register_val: Any, last_linearized_time: float) -> bool:
            if not remaining_ops:
                return True

            # Find candidate operations that could be linearized next.
            # An operation can be linearized if it has already been invoked.
            # Furthermore, we cannot skip an operation that has already returned before any candidate!
            # The earliest return time among all remaining operations bounds our candidate selection.
            min_return_time = min(op.return_time for op in remaining_ops)

            candidates = [
                op for op in remaining_ops
                if op.invoke_time <= min_return_time
            ]

            for op in candidates:
                # Check if this operation is valid under sequential register semantics
                if op.op_type == "write":
                    next_val = op.val
                    valid = True
                elif op.op_type == "read":
                    next_val = current_register_val
                    valid = (op.val == current_register_val)
                else:
                    valid = False
                    next_val = current_register_val

                if valid:
                    # Point of linearization must be within [op.invoke_time, op.return_time]
                    # and >= last_linearized_time
                    lin_time = max(op.invoke_time, last_linearized_time)
                    if lin_time <= op.return_time:
                        next_remaining = [o for o in remaining_ops if o.op_id != op.op_id]
                        if search(next_remaining, next_val, lin_time):
                            return True

            return False

        return search(ops, initial_val, 0.0)
