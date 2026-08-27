from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .enums import OptionType, Direction


@dataclass
class Option:
    id: int
    user_id: int
    active_id: int
    direction: Direction
    option_type: OptionType
    price: float
    exp: int
    created: int
    profit_income: int = 0
    profit_return: int = 0
    exp_value: float = 0
    value: float = 0
    result: str = ""
    profit_amount: float = 0

    @classmethod
    def from_open_response(cls, d: dict, option_type: OptionType) -> Option:
        direction_str = d.get("direction", "call")
        return cls(
            id=d["id"],
            user_id=d.get("user_id", 0),
            active_id=d.get("act", 0),
            direction=Direction(direction_str),
            option_type=option_type,
            price=d.get("price", 0),
            exp=d.get("exp", 0),
            created=d.get("created", 0),
            profit_income=d.get("profit_income", 0),
            profit_return=d.get("profit_return", 0),
            exp_value=d.get("exp_value", 0),
            value=d.get("value", 0),
        )
