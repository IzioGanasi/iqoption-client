from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import time
import random


def make_request_id(prefix: str = "") -> str:
    if prefix:
        return f"{prefix}_{random.randint(100000, 999999999)}"
    return str(random.randint(0, 999999999))


def make_local_time() -> int:
    return int(time.time() * 1000) % 100000


@dataclass
class WSMessage:
    name: str
    request_id: Optional[str] = None
    msg: Any = None
    status: Optional[int] = None
    microserviceName: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> WSMessage:
        return cls(
            name=d.get("name", ""),
            request_id=d.get("request_id"),
            msg=d.get("msg"),
            status=d.get("status"),
            microserviceName=d.get("microserviceName"),
        )


@dataclass
class SendMessage:
    name: str
    version: str
    body: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"name": self.name, "version": self.version}
        if self.body:
            d["body"] = self.body
        return d


@dataclass
class SubscribeMessage:
    name: str
    version: str = "1.0"
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"name": self.name, "version": self.version}
        if self.params:
            d["params"] = self.params
        return d
