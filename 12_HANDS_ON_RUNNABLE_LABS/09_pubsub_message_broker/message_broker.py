"""
In-Memory Partitioned Message Broker (Kafka-Style).

Features:
- Topics divided into multiple ordered Partitions
- Partition key routing (hash(key) % num_partitions)
- Multiple Consumer Groups with isolated offset pointers
- At-least-once message delivery and manual offset commits
- Time-travel log replay (Seek)
"""

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple


class Message:
    def __init__(self, key: Optional[str], value: Any, offset: int, timestamp: float):
        self.key = key
        self.value = value
        self.offset = offset
        self.timestamp = timestamp

    def __repr__(self):
        return f"Message(key={self.key}, offset={self.offset}, val={self.value})"


class TopicPartition:
    def __init__(self, partition_id: int):
        self.partition_id = partition_id
        self.log: List[Message] = []
        self.next_offset = 0

    def append(self, key: Optional[str], value: Any) -> Message:
        msg = Message(key, value, self.next_offset, time.time())
        self.log.append(msg)
        self.next_offset += 1
        return msg

    def read_from(self, offset: int, limit: int = 10) -> List[Message]:
        return [msg for msg in self.log if msg.offset >= offset][:limit]


class PartitionedMessageBroker:
    """
    Kafka-like partitioned pub-sub message broker.
    """

    def __init__(self):
        # {topic_name: List[TopicPartition]}
        self.topics: Dict[str, List[TopicPartition]] = {}
        # {topic_name: {group_id: {partition_id: committed_offset}}}
        self.consumer_offsets: Dict[str, Dict[str, Dict[int, int]]] = {}
        self._round_robin_counter = 0

    def create_topic(self, topic: str, num_partitions: int = 3) -> None:
        if topic in self.topics:
            return
        self.topics[topic] = [TopicPartition(i) for i in range(num_partitions)]
        self.consumer_offsets[topic] = {}

    def _hash_key(self, key: str, num_partitions: int) -> int:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % num_partitions

    def produce(self, topic: str, key: Optional[str], value: Any) -> Tuple[int, int]:
        """
        Publishes message to topic.
        Returns: (partition_id, assigned_offset)
        """
        if topic not in self.topics:
            self.create_topic(topic)

        partitions = self.topics[topic]
        num_partitions = len(partitions)

        if key is not None:
            # Deterministic partition key routing
            part_id = self._hash_key(key, num_partitions)
        else:
            # Round-robin distribution
            part_id = self._round_robin_counter % num_partitions
            self._round_robin_counter += 1

        msg = partitions[part_id].append(key, value)
        return part_id, msg.offset

    def consume(
        self,
        topic: str,
        group_id: str,
        partition_id: int,
        max_records: int = 10,
    ) -> List[Message]:
        """
        Pulls messages for a consumer group from a specific partition.
        """
        if topic not in self.topics:
            return []
        partitions = self.topics[topic]
        if not (0 <= partition_id < len(partitions)):
            raise ValueError("Invalid partition_id")

        if group_id not in self.consumer_offsets[topic]:
            self.consumer_offsets[topic][group_id] = {}

        current_offset = self.consumer_offsets[topic][group_id].get(partition_id, 0)
        return partitions[partition_id].read_from(current_offset, max_records)

    def commit_offset(self, topic: str, group_id: str, partition_id: int, offset: int) -> None:
        """Commits consumer group reading offset (next offset to read)."""
        if topic not in self.consumer_offsets:
            self.consumer_offsets[topic] = {}
        if group_id not in self.consumer_offsets[topic]:
            self.consumer_offsets[topic][group_id] = {}
        self.consumer_offsets[topic][group_id][partition_id] = offset

    def seek(self, topic: str, group_id: str, partition_id: int, offset: int) -> None:
        """Enables historical log replay by resetting group offset."""
        self.commit_offset(topic, group_id, partition_id, offset)
