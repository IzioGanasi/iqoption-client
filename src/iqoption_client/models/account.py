from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Balance:
    id: int
    user_id: int
    type: int
    amount: float
    enrolled_amount: float = 0
    bonus_amount: float = 0
    hold_amount: float = 0
    currency: str = "USD"

    @classmethod
    def from_dict(cls, d: dict) -> Balance:
        return cls(
            id=d["id"],
            user_id=d["user_id"],
            type=d["type"],
            amount=d["amount"],
            enrolled_amount=d.get("enrolled_amount", 0),
            bonus_amount=d.get("bonus_amount", 0),
            hold_amount=d.get("hold_amount", 0),
            currency=d.get("currency", "USD"),
        )


@dataclass
class Account:
    user_id: int
    ssid: str
    token: str
    balances: list[Balance] = field(default_factory=list)
    selected_balance_id: Optional[int] = None
    company_id: int = 0
    created_at: int = 0

    @property
    def demo_balance(self) -> Optional[Balance]:
        for b in self.balances:
            if b.type == 4:
                return b
        return None

    @property
    def real_balance(self) -> Optional[Balance]:
        for b in self.balances:
            if b.type == 1:
                return b
        return None

    @property
    def active_balance(self) -> Optional[Balance]:
        if self.selected_balance_id:
            for b in self.balances:
                if b.id == self.selected_balance_id:
                    return b
        return self.demo_balance or self.real_balance

    def select_balance(self, balance_id: int) -> bool:
        for b in self.balances:
            if b.id == balance_id:
                self.selected_balance_id = balance_id
                return True
        return False
