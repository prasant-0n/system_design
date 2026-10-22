"""
Ring AllReduce Collective Communication Simulator.

Features:
1. Ring topology for N distributed workers / GPU ranks.
2. Scatter-Reduce Phase (N-1 steps): computes partial sums per chunk.
3. AllGather Phase (N-1 steps): distributes reduced chunks to all ranks.
4. Bandwidth optimality: Total transferred per rank = 2 * (N - 1) / N * S.
"""

from typing import List


class RingAllReduceCluster:
    def __init__(self, rank_tensors: List[List[float]]):
        if not rank_tensors:
            raise ValueError("Must provide at least one rank tensor")
        self.num_ranks = len(rank_tensors)
        self.tensor_len = len(rank_tensors[0])

        if any(len(t) != self.tensor_len for t in rank_tensors):
            raise ValueError("All tensors must have identical length")
        if self.tensor_len % self.num_ranks != 0:
            raise ValueError(f"Tensor length {self.tensor_len} must be divisible by num_ranks {self.num_ranks}")

        # Tensors owned by each rank
        self.buffers: List[List[float]] = [list(t) for t in rank_tensors]
        self.chunk_size = self.tensor_len // self.num_ranks

    def _get_chunk(self, rank: int, chunk_idx: int) -> List[float]:
        start = chunk_idx * self.chunk_size
        end = start + self.chunk_size
        return self.buffers[rank][start:end]

    def _set_chunk(self, rank: int, chunk_idx: int, data: List[float]) -> None:
        start = chunk_idx * self.chunk_size
        end = start + self.chunk_size
        self.buffers[rank][start:end] = data

    def execute_allreduce(self) -> None:
        N = self.num_ranks

        # -------------------------------------------------------------
        # Phase 1: Scatter-Reduce (N - 1 steps)
        # -------------------------------------------------------------
        for step in range(N - 1):
            # In step, rank i sends chunk (i - step) % N to rank (i + 1) % N
            outgoing_chunks = []
            for i in range(N):
                send_chunk_idx = (i - step) % N
                outgoing_chunks.append((send_chunk_idx, self._get_chunk(i, send_chunk_idx)))

            # Each rank receives chunk from neighbor (i - 1) % N
            for i in range(N):
                prev_rank = (i - 1) % N
                recv_chunk_idx, recv_data = outgoing_chunks[prev_rank]

                # Element-wise reduction (sum) into local buffer
                local_chunk = self._get_chunk(i, recv_chunk_idx)
                reduced_chunk = [a + b for a, b in zip(local_chunk, recv_data)]
                self._set_chunk(i, recv_chunk_idx, reduced_chunk)

        # -------------------------------------------------------------
        # Phase 2: AllGather (N - 1 steps)
        # -------------------------------------------------------------
        for step in range(N - 1):
            # In step, rank i sends chunk (i - step + 1) % N to rank (i + 1) % N
            outgoing_chunks = []
            for i in range(N):
                send_chunk_idx = (i - step + 1) % N
                outgoing_chunks.append((send_chunk_idx, self._get_chunk(i, send_chunk_idx)))

            for i in range(N):
                prev_rank = (i - 1) % N
                recv_chunk_idx, recv_data = outgoing_chunks[prev_rank]
                # Overwrite chunk with the fully reduced values
                self._set_chunk(i, recv_chunk_idx, recv_data)
