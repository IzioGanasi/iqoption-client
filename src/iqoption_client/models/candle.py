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
        at_val = d.get("from", d.get("at", 0))
        at_int = int(at_val) if at_val else 0
        if at_int > 10**11:  # Se vier em nanossegundos ou microssegundos
            at_int = at_int // 10**9

        return cls(
            at=at_int,
            open=float(d.get("open", 0) or 0),
            close=float(d.get("close", 0) or 0),
            high=float(d.get("max", d.get("high", 0)) or 0),
            low=float(d.get("min", d.get("low", 0)) or 0),
            volume=float(d.get("volume", 0) or 0),
            active_id=int(d.get("active_id", d.get("active", 0)) or 0),
        )
