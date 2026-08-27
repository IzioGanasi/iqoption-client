from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    email: str = field(default_factory=lambda: os.getenv("IQOPTION_EMAIL", ""))
    password: str = field(default_factory=lambda: os.getenv("IQOPTION_PASSWORD", ""))
    account_type: str = field(default_factory=lambda: os.getenv("IQOPTION_ACCOUNT_TYPE", "demo"))
    log_level: str = field(default_factory=lambda: os.getenv("IQOPTION_LOG_LEVEL", "INFO"))
    ws_url: str = "wss://ws.iqoption.com/echo/websocket"
    login_url: str = "https://api.iqoption.com/v2/login"
    request_timeout: float = 60.0
    heartbeat_interval: float = 30.0
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 5
