"""
Log-Structured Merge-Tree (LSM-Tree) Storage Engine.

Features:
1. In-memory sorted MemTable.
2. Flush to immutable Sorted String Tables (SSTables).
3. Sparse Index for fast binary-search range seeking without full table scans.
4. Tombstones for deletes.
5. Multi-way Compaction to merge SSTables, eliminate duplicates, and reclaim tombstone space.
"""

import bisect
from typing import List, Dict, Tuple, Optional, Any

TOMBSTONE = "__DELETED_TOMBSTONE__"


class SSTable:
    """
    Immutable Sorted String Table with a Sparse Index.
    """

    def __init__(self, data: List[Tuple[str, Any]], sparse_index_interval: int = 2):
        # Data is sorted by key
        self.data: List[Tuple[str, Any]] = sorted(data, key=lambda x: x[0])
        self.sparse_index_keys: List[str] = []
        self.sparse_index_offsets: List[int] = []

        # Build sparse index
        for idx in range(0, len(self.data), sparse_index_interval):
            self.sparse_index_keys.append(self.data[idx][0])
            self.sparse_index_offsets.append(idx)

    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Binary search sparse index, then scan the small block.
        Returns (found, value).
        """
        if not self.data:
            return False, None

        # Binary search sparse index
        idx = bisect.bisect_right(self.sparse_index_keys, key) - 1
        if idx < 0:
            start_pos = 0
        else:
            start_pos = self.sparse_index_offsets[idx]

        # Determine upper search bound
        if idx + 1 < len(self.sparse_index_offsets):
            end_pos = self.sparse_index_offsets[idx + 1]
        else:
            end_pos = len(self.data)

        # Linear scan between start_pos and end_pos
        for i in range(start_pos, min(end_pos + 1, len(self.data))):
            k, v = self.data[i]
            if k == key:
                return True, v
            if k > key:
                break
        return False, None


class LSMTree:
    """
    Complete LSM-Tree implementation with MemTable, SSTables, and Compaction.
    """

    def __init__(self, memtable_threshold: int = 4, sparse_interval: int = 2):
        self.memtable_threshold = memtable_threshold
        self.sparse_interval = sparse_interval
        self.memtable: Dict[str, Any] = {}
        # List of SSTables: index 0 is newest, higher indices are older
        self.sstables: List[SSTable] = []

    def put(self, key: str, value: Any) -> None:
        self.memtable[key] = value
        if len(self.memtable) >= self.memtable_threshold:
            self._flush()

    def delete(self, key: str) -> None:
        """Deletes key by writing a tombstone."""
        self.put(key, TOMBSTONE)

    def _flush(self) -> None:
        if not self.memtable:
            return
        sorted_pairs = sorted(self.memtable.items(), key=lambda x: x[0])
        sstable = SSTable(sorted_pairs, sparse_index_interval=self.sparse_interval)
        self.sstables.insert(0, sstable)  # Newest first
        self.memtable.clear()

    def get(self, key: str) -> Optional[Any]:
        # 1. Check MemTable
        if key in self.memtable:
            val = self.memtable[key]
            return None if val == TOMBSTONE else val

        # 2. Check SSTables from newest to oldest
        for sstable in self.sstables:
            found, val = sstable.get(key)
            if found:
                return None if val == TOMBSTONE else val

        return None

    def compact(self) -> None:
        """
        Multi-way merge compaction of all SSTables.
        Merges older and newer SSTables, resolving duplicates in favor of newer SSTables,
        and eliminates tombstones.
        """
        if not self.sstables:
            return

        merged_data: Dict[str, Any] = {}

        # Merge from oldest to newest so newer values overwrite older
        for sstable in reversed(self.sstables):
            for k, v in sstable.data:
                merged_data[k] = v

        # Filter out tombstones
        compacted_pairs = [(k, v) for k, v in sorted(merged_data.items()) if v != TOMBSTONE]

        if compacted_pairs:
            self.sstables = [SSTable(compacted_pairs, sparse_index_interval=self.sparse_interval)]
        else:
            self.sstables = []
