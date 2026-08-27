from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Candle:
    at: int
    open: float
    close: float
    high: float
    low: float
    volume: float = 0
    active_id: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> Candle:
        if not isinstance(d, dict):
            return cls(at=0, open=0, close=0, high=0, low=0)
        at_val = d.get("at", d.get("from", 0))
        return cls(
            at=int(at_val) if at_val else 0,
            open=float(d.get("open", 0) or 0),
            close=float(d.get("close", 0) or 0),
            high=float(d.get("high", 0) or 0),
            low=float(d.get("low", 0) or 0),
            volume=float(d.get("volume", 0) or 0),
            active_id=int(d.get("active", 0) or 0),
        )
