from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ..models.asset import Active, OptionInfo, Schedule
from ..models.enums import OptionType

if TYPE_CHECKING:
    from ..connection.websocket_manager import WebSocketManager
    from ..connection.clock_sync import ClockSync

logger = logging.getLogger(__name__)


class AssetsManager:
    def __init__(self, ws: WebSocketManager, clock_sync: ClockSync) -> None:
        self._ws = ws
        self._clock_sync = clock_sync
        self._actives: dict[str, dict[int, Active]] = {
            "turbo": {},
            "binary": {},
            "blitz": {},
        }
        self._commissions: dict[str, dict[int, int]] = {
            "turbo": {},
            "binary": {},
            "blitz": {},
        }

    @property
    def turbo_actives(self) -> dict[int, Active]:
        return self._actives["turbo"]

    @property
    def binary_actives(self) -> dict[int, Active]:
        return self._actives["binary"]

    @property
    def blitz_actives(self) -> dict[int, Active]:
        return self._actives["blitz"]

    def get_active(self, active_id: int, option_type: OptionType) -> Optional[Active]:
        type_key = option_type.value
        return self._actives.get(type_key, {}).get(active_id)

    def get_commission(self, active_id: int, option_type: OptionType) -> int:
        type_key = option_type.value
        return self._commissions.get(type_key, {}).get(active_id, 0)

    def get_payout(self, active_id: int, option_type: OptionType) -> int:
        """Get payout percentage (e.g. comm=14 means 100-14 = 86% net profit return)."""
        comm = self.get_commission(active_id, option_type)
        if comm > 0:
            return 100 - comm
        active = self.get_active(active_id, option_type)
        if active and active.option:
            return active.option.payout_percent
        return 0

    def get_profit_percent(self, active_id: int, option_type: OptionType) -> int:
        """Get profit_percent to send in open-option (100 - commission)."""
        comm = self.get_commission(active_id, option_type)
        if comm > 0:
            return 100 - comm
        active = self.get_active(active_id, option_type)
        if active and active.option:
            return active.option.profit_commission
        return 88  # default fallback

    async def load_initialization_data(self) -> dict:
        result = await self._ws.send_message(
            "get-initialization-data", "4.0", body={}
        )
        init_data = result.get("msg", {})

        for type_key in ["turbo", "binary", "blitz"]:
            type_data = init_data.get(type_key, {})
            actives_dict = type_data.get("actives", {})
            for active_id_str, active_data in actives_dict.items():
                try:
                    active_id = int(active_id_str)
                    active = Active.from_dict(active_data)
                    self._actives[type_key][active_id] = active
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse active {active_id_str}: {e}")

        total = sum(len(v) for v in self._actives.values())
        logger.info(f"Loaded {total} actives (turbo={len(self._actives['turbo'])}, "
                     f"binary={len(self._actives['binary'])}, blitz={len(self._actives['blitz'])})")
        return init_data

    async def load_trading_params(self) -> None:
        for type_key, inst_type in [
            ("turbo", "turbo-option"),
            ("binary", "binary-option"),
            ("blitz", "blitz-option"),
        ]:
            try:
                result = await self._ws.send_message(
                    "trading-settings.get-trading-group-params",
                    "2.0",
                    body={"instrument_type": inst_type},
                )
                data = result.get("msg", {})
                commissions = data.get("commissions", [])
                for c in commissions:
                    active_id = c.get("active_id", 0)
                    value = c.get("value", 0)
                    if active_id and value:
                        self._commissions[type_key][active_id] = value
                logger.info(f"Loaded {len(commissions)} commissions for {type_key}")
            except Exception as e:
                logger.error(f"Failed to load trading params for {type_key}: {e}")

        # If blitz actives are empty but commissions exist, build synthetic actives
        if not self._actives["blitz"] and self._commissions["blitz"]:
            self._build_blitz_actives_from_commissions()

    def _build_blitz_actives_from_commissions(self) -> None:
        """Build synthetic blitz actives when init data doesn't provide them.
        
        Blitz options use expiration_size (seconds) instead of fixed candle periods.
        They are typically OTC assets that trade 24/7.
        """
        now = self._clock_sync.server_time // 1000
        blitz_commissions = self._commissions["blitz"]

        for active_id, commission in blitz_commissions.items():
            option = OptionInfo(
                profit_commission=commission,
                expiration_times=[30, 45, 60, 120, 180, 300],
                default_expiration=30,
                exp_time=0,
                count=0,
                start_time=now,
            )
            # Create broad schedule (essentially always open for OTC)
            schedule = [Schedule(start=now - 86400, end=now + 86400 * 365)]
            active = Active(
                id=active_id,
                name=f"blitz-{active_id}",
                description=f"Blitz Active {active_id}",
                minimal_bet=2,
                maximal_bet=20000,
                precision=6,
                option=option,
                deadtime=0,
                enabled=True,
                is_suspended=False,
                is_buyback=True,
                provider="OTC",
                schedule=schedule,
                minmax={"min": 2, "max": 20000},
            )
            self._actives["blitz"][active_id] = active

        logger.info(
            f"Built {len(blitz_commissions)} synthetic blitz actives from commissions"
        )

    def find_open_active(self, option_type: OptionType, active_id: int | None = None) -> Optional[Active]:
        server_time = self._clock_sync.server_time // 1000
        type_key = option_type.value
        actives = self._actives.get(type_key, {})

        if active_id:
            active = actives.get(active_id)
            if active and active.is_open(server_time):
                return active
            return None

        for active in actives.values():
            if active.is_open(server_time):
                return active
        return None
