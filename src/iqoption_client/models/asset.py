from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OptionInfo:
    profit_commission: int = 0
    refund_min: float = 0
    refund_max: float = 0
    expiration_times: list[int] = field(default_factory=list)
    default_expiration: int = 0
    exp_time: int = 0
    count: int = 0
    special: dict = field(default_factory=dict)
    start_time: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> OptionInfo:
        profit = d.get("profit", {})
        return cls(
            profit_commission=profit.get("commission", 0),
            refund_min=profit.get("refund_min", 0),
            refund_max=profit.get("refund_max", 0),
            expiration_times=d.get("expiration_times", []),
            default_expiration=d.get("default_expiration", 0),
            exp_time=d.get("exp_time", 0),
            count=d.get("count", 0),
            special=d.get("special", {}),
            start_time=d.get("start_time", 0),
        )

    @property
    def payout_percent(self) -> int:
        return 100 + self.profit_commission


@dataclass
class Schedule:
    start: int
    end: int

    @classmethod
    def from_list(cls, lst: list) -> Schedule:
        return cls(start=lst[0], end=lst[1])


@dataclass
class Rollover:
    expiration_size: int = 0
    offset: int = 0
    offset_from_expiration: int = 0
    deadtime: int = 0
    limit: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> Rollover:
        return cls(
            expiration_size=d.get("expiration_size", 0),
            offset=d.get("offset", 0),
            offset_from_expiration=d.get("offset_from_expiration", 0),
            deadtime=d.get("deadtime", 0),
            limit=d.get("limit", 0),
        )


@dataclass
class Active:
    id: int
    name: str
    description: str
    group_id: int = 0
    exchange: str = ""
    minimal_bet: float = 0
    maximal_bet: float = 0
    precision: int = 6
    option: Optional[OptionInfo] = None
    deadtime: int = 0
    enabled: bool = True
    is_suspended: bool = False
    is_buyback: bool = False
    buyback_deadtime: int = 0
    provider: str = ""
    ticker: str = ""
    schedule: list[Schedule] = field(default_factory=list)
    rollovers: list[Rollover] = field(default_factory=list)
    minmax: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> Active:
        schedule = []
        for s in d.get("schedule", []):
            if isinstance(s, list) and len(s) >= 2:
                schedule.append(Schedule.from_list(s))

        rollovers = []
        for r in d.get("rollovers", []):
            if isinstance(r, dict):
                rollovers.append(Rollover.from_dict(r))

        minmax = d.get("minmax", {})
        if not minmax and "minmax" not in d:
            minmax = {"min": d.get("minimal_bet", 0), "max": d.get("maximal_bet", 0)}

        return cls(
            id=d["id"],
            name=d.get("name", ""),
            description=d.get("description", ""),
            group_id=d.get("group_id", 0),
            exchange=d.get("exchange", ""),
            minimal_bet=d.get("minimal_bet", 0),
            maximal_bet=d.get("maximal_bet", 0),
            precision=d.get("precision", 6),
            option=OptionInfo.from_dict(d["option"]) if "option" in d else None,
            deadtime=d.get("deadtime", 0),
            enabled=d.get("enabled", True),
            is_suspended=d.get("is_suspended", False),
            is_buyback=d.get("is_buyback", False),
            buyback_deadtime=d.get("buyback_deadtime", 0),
            provider=d.get("provider", ""),
            ticker=d.get("ticker", ""),
            schedule=schedule,
            rollovers=rollovers,
            minmax=minmax,
        )

    def is_open(self, server_time: int) -> bool:
        if self.is_suspended or not self.enabled:
            return False
        if not self.schedule:
            return True
        for s in self.schedule:
            if s.start <= server_time <= s.end:
                return True
        return False

    def get_payout(self, commissions: dict | None = None) -> int:
        if commissions and self.id in commissions:
            return 100 + commissions[self.id]
        if self.option:
            return self.option.payout_percent
        return 0
