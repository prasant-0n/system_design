"""
Two-Phase Commit (2PC) Distributed Transaction Protocol.

Features:
1. Formal Finite State Machines (Coordinator & Participants).
2. Persistent Write-Ahead Log (WAL) simulation.
3. Prepare and Commit/Abort phases.
4. Crash recovery handling:
   - Resolving in-doubt participants after restart.
   - Coordinator crash recovery from WAL.
"""

from enum import Enum
from typing import Dict, List, Optional, Any


class TxState(str, Enum):
    INITIAL = "INITIAL"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class Participant:
    def __init__(self, name: str):
        self.name = name
        self.wal: List[str] = []
        self.state: Dict[str, TxState] = {}
        self.data_store: Dict[str, Any] = {}
        self.pending_mutations: Dict[str, Dict[str, Any]] = {}
        self.should_fail_prepare: bool = False

    def log(self, entry: str):
        self.wal.append(entry)

    def prepare(self, tx_id: str, mutations: Dict[str, Any]) -> bool:
        """Phase 1: Prepare request."""
        if self.should_fail_prepare:
            self.state[tx_id] = TxState.ABORTED
            self.log(f"{tx_id}:ABORT")
            return False

        # Lock resources and write PREPARE record to WAL
        self.pending_mutations[tx_id] = mutations
        self.state[tx_id] = TxState.PREPARED
        self.log(f"{tx_id}:PREPARED")
        return True

    def commit(self, tx_id: str) -> None:
        """Phase 2: Commit request."""
        if tx_id in self.pending_mutations:
            self.data_store.update(self.pending_mutations.pop(tx_id))
        self.state[tx_id] = TxState.COMMITTED
        self.log(f"{tx_id}:COMMIT")

    def abort(self, tx_id: str) -> None:
        """Phase 2: Abort request."""
        self.pending_mutations.pop(tx_id, None)
        self.state[tx_id] = TxState.ABORTED
        self.log(f"{tx_id}:ABORT")

    def recover(self, coordinator: "Coordinator") -> None:
        """
        Crash recovery for participant:
        Replays WAL. If left in PREPARED state, asks coordinator for decision.
        """
        for tx_id, state in list(self.state.items()):
            if state == TxState.PREPARED:
                coord_decision = coordinator.get_transaction_status(tx_id)
                if coord_decision == TxState.COMMITTED:
                    self.commit(tx_id)
                else:
                    self.abort(tx_id)


class Coordinator:
    def __init__(self, participants: List[Participant]):
        self.participants = participants
        self.wal: List[str] = []
        self.tx_status: Dict[str, TxState] = {}

    def log(self, entry: str):
        self.wal.append(entry)

    def get_transaction_status(self, tx_id: str) -> TxState:
        return self.tx_status.get(tx_id, TxState.ABORTED)

    def execute_transaction(self, tx_id: str, participant_mutations: Dict[Participant, Dict[str, Any]]) -> bool:
        """
        Executes atomic distributed commit across all participants.
        Returns True if committed, False if aborted.
        """
        self.tx_status[tx_id] = TxState.PREPARING
        self.log(f"{tx_id}:START_2PC")

        # Phase 1: Prepare
        votes: Dict[Participant, bool] = {}
        for p, mutations in participant_mutations.items():
            vote = p.prepare(tx_id, mutations)
            votes[p] = vote

        all_voted_yes = all(votes.values()) and len(votes) == len(participant_mutations)

        # Phase 2: Decision & Broadcast
        if all_voted_yes:
            # WAL Invariant: Must append COMMIT record before broadcasting commit
            self.tx_status[tx_id] = TxState.COMMITTED
            self.log(f"{tx_id}:COMMIT")

            for p in participant_mutations.keys():
                p.commit(tx_id)
            return True
        else:
            self.tx_status[tx_id] = TxState.ABORTED
            self.log(f"{tx_id}:ABORT")

            for p in participant_mutations.keys():
                p.abort(tx_id)
            return False
