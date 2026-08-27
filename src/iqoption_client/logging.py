from __future__ import annotations

import logging
import re
from typing import Optional


class CredentialFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""

    PATTERNS = [
        (re.compile(r'"ssid"\s*:\s*"[^"]*"', re.IGNORECASE), '"ssid": "***REDACTED***"'),
        (re.compile(r'"token"\s*:\s*"[^"]*"', re.IGNORECASE), '"token": "***REDACTED***"'),
        (re.compile(r'"password"\s*:\s*"[^"]*"', re.IGNORECASE), '"password": "***REDACTED***"'),
        (re.compile(r'ssid=[a-zA-Z0-9]+'), 'ssid=***REDACTED***'),
        (re.compile(r'\b\d{9,12}\b'), '***REDACTED_ID***'),
        (re.compile(r'WS SEND:.*'), 'WS SEND: [REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


def setup_logging(level: str = "INFO", mask_credentials: bool = True) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    if mask_credentials:
        root.addFilter(CredentialFilter())
