"""
Chandy-Lamport Distributed Snapshot Simulator.

Simulates:
1. Distributed processes connected by directed FIFO channels.
2. In-flight messages (e.g., bank transfers).
3. The Marker Message Protocol.
4. Channel state recording.
5. Global Consistent Cut verification.
"""

from typing import Dict, List, Optional, Tuple, Any
from collections import deque


class Channel:
    """Directed FIFO communication channel between two processes."""

    def __init__(self, sender_id: str, receiver_id: str):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.queue: deque = deque()

    def send(self, message: Any) -> None:
        self.queue.append(message)

    def receive(self) -> Optional[Any]:
        if self.queue:
            return self.queue.popleft()
        return None

    def is_empty(self) -> bool:
        return len(self.queue) == 0


class Process:
    """An individual process in the distributed system."""

    def __init__(self, process_id: str, initial_balance: int):
        self.process_id = process_id
        self.balance = initial_balance

        self.incoming_channels: Dict[str, Channel] = {}
        self.outgoing_channels: Dict[str, Channel] = {}

        # Snapshot state
        self.has_recorded_state = False
        self.recorded_balance: Optional[int] = None
        self.channel_recording: Dict[str, bool] = {}
        self.recorded_channel_messages: Dict[str, List[Any]] = {}

    def add_incoming_channel(self, channel: Channel):
        self.incoming_channels[channel.sender_id] = channel
        self.channel_recording[channel.sender_id] = False
        self.recorded_channel_messages[channel.sender_id] = []

    def add_outgoing_channel(self, channel: Channel):
        self.outgoing_channels[channel.receiver_id] = channel

    def transfer(self, target_id: str, amount: int) -> None:
        """Sends an application message (transfer money)."""
        if self.balance < amount:
            raise ValueError("Insufficient balance")
        self.balance -= amount
        self.outgoing_channels[target_id].send({"type": "TRANSFER", "amount": amount})

    def initiate_snapshot(self) -> None:
        """Rule 1: Initiator records local state and sends Marker on all outgoing channels."""
        self.has_recorded_state = True
        self.recorded_balance = self.balance

        # Start recording on all incoming channels
        for sender_id in self.incoming_channels:
            self.channel_recording[sender_id] = True

        # Broadcast Marker
        for target_id, channel in self.outgoing_channels.items():
            channel.send({"type": "MARKER", "origin": self.process_id})

    def process_incoming_message(self, sender_id: str, msg: Dict[str, Any]) -> None:
        if msg["type"] == "MARKER":
            self._handle_marker(sender_id)
        elif msg["type"] == "TRANSFER":
            amount = msg["amount"]
            self.balance += amount

            # If currently recording on this incoming channel, log message
            if self.has_recorded_state and self.channel_recording.get(sender_id, False):
                self.recorded_channel_messages[sender_id].append(amount)

    def _handle_marker(self, sender_id: str) -> None:
        if not self.has_recorded_state:
            # First time seeing Marker: Record local state, mark channel as empty
            self.has_recorded_state = True
            self.recorded_balance = self.balance
            self.channel_recording[sender_id] = False

            # Start recording on all other incoming channels
            for s_id in self.incoming_channels:
                if s_id != sender_id:
                    self.channel_recording[s_id] = True

            # Broadcast Marker along all outgoing channels
            for target_id, channel in self.outgoing_channels.items():
                channel.send({"type": "MARKER", "origin": self.process_id})
        else:
            # Subsequent Marker: stop recording on this channel
            self.channel_recording[sender_id] = False


class DistributedSnapshotCluster:
    def __init__(self, balances: Dict[str, int], topology: List[Tuple[str, str]]):
        self.processes = {pid: Process(pid, bal) for pid, bal in balances.items()}

        # Create channels
        for src, dst in topology:
            ch = Channel(src, dst)
            self.processes[src].add_outgoing_channel(ch)
            self.processes[dst].add_incoming_channel(ch)

    def total_system_balance(self) -> int:
        return sum(p.balance for p in self.processes.values())

    def snapshot_total(self) -> int:
        """Returns total money captured in snapshot (process balances + in-flight channel balances)."""
        total = 0
        for p in self.processes.values():
            if p.recorded_balance is not None:
                total += p.recorded_balance
            for msgs in p.recorded_channel_messages.values():
                total += sum(msgs)
        return total
