from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    option_id: int
    user_id: int
    active_id: int
    direction: str
    option_type: str
    option_type_id: int
    amount: float
    result: str = "opened"
    profit_amount: float = 0
    expiration_value: Optional[float] = None
    open_time: int = 0
    expiration_time: int = 0
    expiration_size: int = 0
    value: float = 0
    profit_percent: int = 0

    @classmethod
    def from_event(cls, d: dict) -> Position:
        return cls(
            option_id=d.get("option_id", 0),
            user_id=d.get("user_id", 0),
            active_id=d.get("active_id", 0),
            direction=d.get("direction", ""),
            option_type=d.get("option_type", ""),
            option_type_id=d.get("option_type_id", 0),
            amount=d.get("amount", 0),
            result=d.get("result", "opened"),
            profit_amount=d.get("profit_amount", 0) or 0,
            expiration_value=d.get("expiration_value"),
            open_time=d.get("open_time", 0),
            expiration_time=d.get("expiration_time", 0),
            expiration_size=d.get("expiration_size", 0),
            value=d.get("value", 0),
            profit_percent=d.get("profit_percent", 0),
        )


@dataclass
class DigitalPosition:
    id: int
    user_id: int
    instrument_id: str
    instrument_active_id: int
    instrument_dir: str
    status: str
    buy_amount: float
    close_reason: Optional[str] = None
    close_effect_amount: Optional[float] = None
    close_underlying_price: Optional[float] = None
    open_underlying_price: float = 0
    instrument_strike: float = 0
    instrument_expiration: int = 0
    instrument_period: int = 0
    pnl_realized: float = 0
    create_at: int = 0
    update_at: int = 0
    close_at: Optional[int] = None
    order_ids: list[int] = field(default_factory=list)
    instrument_index: int = 0
    instrument_underlying: str = ""

    @classmethod
    def from_event(cls, d: dict) -> DigitalPosition:
        return cls(
            id=d.get("id", 0),
            user_id=d.get("user_id", 0),
            instrument_id=d.get("instrument_id", ""),
            instrument_active_id=d.get("instrument_active_id", 0),
            instrument_dir=d.get("instrument_dir", ""),
            status=d.get("status", ""),
            buy_amount=d.get("buy_amount", 0),
            close_reason=d.get("close_reason"),
            close_effect_amount=d.get("close_effect_amount"),
            close_underlying_price=d.get("close_underlying_price"),
            open_underlying_price=d.get("open_underlying_price", 0),
            instrument_strike=d.get("instrument_strike", 0),
            instrument_expiration=d.get("instrument_expiration", 0),
            instrument_period=d.get("instrument_period", 0),
            pnl_realized=d.get("pnl_realized", 0),
            create_at=d.get("create_at", 0),
            update_at=d.get("update_at", 0),
            close_at=d.get("close_at"),
            order_ids=d.get("order_ids", []),
            instrument_index=d.get("instrument_index", 0),
            instrument_underlying=d.get("instrument_underlying", ""),
        )
