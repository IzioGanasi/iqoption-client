from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Operation:
    id: int
    type: str
    active_id: int
    direction: str
    amount: float
    status: str = "pending"
    result: str = ""
    profit: float = 0
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0

    @property
    def is_open(self) -> bool:
        return self.status in ("pending", "opened")

    @property
    def duration(self) -> float:
        if self.completed_at:
            return self.completed_at - self.created_at
        return time.time() - self.created_at


class OperationsManager:
    def __init__(self) -> None:
        self._operations: dict[int, Operation] = {}
        self._callbacks: list[Callable] = []
        self._history: list[Operation] = []

    @property
    def open_operations(self) -> list[Operation]:
        return [op for op in self._operations.values() if op.is_open]

    @property
    def history(self) -> list[Operation]:
        return list(self._history)

    def track(self, operation: Operation) -> None:
        self._operations[operation.id] = operation
        logger.debug(f"Tracking operation {operation.id} ({operation.type})")

    def update(self, operation_id: int, **kwargs) -> Optional[Operation]:
        op = self._operations.get(operation_id)
        if not op:
            return None
        for key, value in kwargs.items():
            if hasattr(op, key):
                setattr(op, key, value)
        if not op.is_open and op.id in self._operations:
            op.completed_at = time.time()
            self._history.append(op)
            del self._operations[operation_id]
            self._notify_callbacks(op)
        return op

    def get(self, operation_id: int) -> Optional[Operation]:
        return self._operations.get(operation_id)

    def on_result(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _notify_callbacks(self, operation: Operation) -> None:
        for cb in self._callbacks:
            try:
                cb(operation)
            except Exception as e:
                logger.error(f"Operation callback error: {e}")

    def clear_history(self) -> None:
        self._history.clear()

    def summary(self) -> dict:
        total = len(self._history)
        wins = sum(1 for op in self._history if op.result == "win")
        losses = sum(1 for op in self._history if op.result == "loose")
        total_profit = sum(op.profit for op in self._history)
        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total if total > 0 else 0,
            "total_profit": total_profit,
        }
