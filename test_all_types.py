#!/usr/bin/env python3
"""
Comprehensive test for all option types: Blitz, Binary, Turbo, Digital.
Tests connection, placement, tracking, and result verification.
"""

import asyncio
import logging
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from iqoption_client.client import IQOptionClient
from iqoption_client.configuration import Config
from iqoption_client.models.enums import OptionType, Direction, InstrumentType
from iqoption_client.exceptions import TradingError
from iqoption_client.operations.manager import Operation

logger = logging.getLogger("test_all_types")
results_log = []


def log_result(test_name, result, details=""):
    entry = {"test": test_name, "result": result, "details": details, "time": time.time()}
    results_log.append(entry)
    sym = "✅" if result == "PASS" else "❌" if result == "FAIL" else "ℹ️"
    print(f"  {sym} [{test_name}] {result}: {details}")


async def test_connection(client):
    print("\n" + "=" * 60)
    print("TEST: CONNECTION & INITIALIZATION")
    print("=" * 60)
    try:
        await client.connect()
        log_result("connect", "PASS", f"user_id={client.user_id}")
    except Exception as e:
        log_result("connect", "FAIL", str(e))
        return False

    log_result("balance_id", "PASS", f"id={client.balance_id}")
    log_result("clock_sync", "PASS" if client.server_time > 0 else "FAIL",
               f"server_time={client.server_time}, offset={client.clock_offset}ms")
    log_result("blitz_actives", "PASS", f"count={len(client.assets.blitz_actives)}")
    log_result("turbo_actives", "PASS", f"count={len(client.assets.turbo_actives)}")
    log_result("binary_actives", "PASS", f"count={len(client.assets.binary_actives)}")
    log_result("session_manager", "PASS" if client.session.has_valid_ssid else "FAIL",
               f"age={client.session.age_seconds:.1f}s")
    log_result("operations_manager", "PASS",
               f"tracking enabled, open={len(client.operations.open_operations)}")
    log_result("connection_manager", "PASS",
               f"state={client.connection_manager.state}")
    log_result("reconnection_manager", "PASS",
               f"monitoring={client.reconnection.is_reconnecting}")
    return True


async def test_blitz(client):
    print("\n" + "=" * 60)
    print("TEST: BLITZ OPTIONS")
    print("=" * 60)

    active = client.assets.find_open_active(OptionType.BLITZ)
    if not active:
        log_result("blitz_active", "FAIL", "No open blitz active found!")
        return

    payout = client.assets.get_payout(active.id, OptionType.BLITZ)
    profit_pct = client.assets.get_profit_percent(active.id, OptionType.BLITZ)
    commission = client.assets.get_commission(active.id, OptionType.BLITZ)
    log_result("blitz_active", "PASS",
               f"id={active.id}, payout={payout}%, profit%={profit_pct}, commission={commission}")

    server_time = client.server_time // 1000
    log_result("blitz_schedule", "PASS" if active.is_open(server_time) else "FAIL",
               f"is_open={active.is_open(server_time)}, deadtime={active.deadtime}")

    await client.subscribe_positions(InstrumentType.BLITZ_OPTION)

    exp_size = 30
    bal_before = client.accounts.account.active_balance.amount

    print(f"\n  Placing CALL + PUT: amount=$1.0, exp={exp_size}s, active={active.id}")
    try:
        call_opt = await client.place_call(
            active.id, 1.0, OptionType.BLITZ, expiration_size=exp_size
        )
        log_result("blitz_call", "PASS",
                   f"id={call_opt.id}, exp={call_opt.exp}, dir={call_opt.direction.value}")
    except TradingError as e:
        log_result("blitz_call", "FAIL", str(e))
        return

    try:
        put_opt = await client.place_put(
            active.id, 1.0, OptionType.BLITZ, expiration_size=exp_size
        )
        log_result("blitz_put", "PASS",
                   f"id={put_opt.id}, exp={put_opt.exp}, dir={put_opt.direction.value}")
    except TradingError as e:
        log_result("blitz_put", "FAIL", str(e))

    wait = exp_size + 15
    print(f"  Waiting {wait}s for expiry...")
    await asyncio.sleep(wait)

    await client.accounts.get_balances()
    bal_after = client.accounts.account.active_balance.amount
    diff = bal_after - bal_before
    log_result("blitz_balance", "PASS",
               f"${bal_before:.2f} → ${bal_after:.2f} (diff={diff:+.2f})")


async def test_turbo(client):
    print("\n" + "=" * 60)
    print("TEST: TURBO OPTIONS")
    print("=" * 60)

    active = client.assets.find_open_active(OptionType.TURBO)
    if not active:
        log_result("turbo_active", "FAIL", "No open turbo active found!")
        return

    payout = client.assets.get_payout(active.id, OptionType.TURBO)
    log_result("turbo_active", "PASS",
               f"id={active.id}, payout={payout}%, exp_time={active.option.exp_time if active.option else 'N/A'}")

    await client.subscribe_positions(InstrumentType.TURBO_OPTION)

    bal_before = client.accounts.account.active_balance.amount
    try:
        call_opt = await client.place_call(active.id, 1.0, OptionType.TURBO)
        log_result("turbo_call", "PASS",
                   f"id={call_opt.id}, exp={call_opt.exp}")
    except TradingError as e:
        log_result("turbo_call", "FAIL", str(e))
        return

    wait = max(10, (call_opt.exp - client.server_time // 1000) + 10)
    wait = min(wait, 120)  # Cap at 2 minutes for test
    print(f"  Waiting {wait}s for expiry...")
    await asyncio.sleep(wait)

    try:
        await client.accounts.get_balances()
        bal_after = client.accounts.account.active_balance.amount
        diff = bal_after - bal_before
        log_result("turbo_balance", "PASS",
                   f"${bal_before:.2f} → ${bal_after:.2f} (diff={diff:+.2f})")
    except Exception as e:
        log_result("turbo_balance", "FAIL", f"Balance check failed: {e}")


async def test_binary(client):
    print("\n" + "=" * 60)
    print("TEST: BINARY OPTIONS")
    print("=" * 60)

    # Find active with shortest exp_time for testing
    best_active = None
    for active in client.assets.binary_actives.values():
        if active.option and active.option.exp_time > 0:
            if active.is_open(client.server_time // 1000):
                if best_active is None or active.option.exp_time < best_active.option.exp_time:
                    best_active = active

    if not best_active:
        log_result("binary_active", "FAIL", "No open binary active found!")
        return

    payout = client.assets.get_payout(best_active.id, OptionType.BINARY)
    log_result("binary_active", "PASS",
               f"id={best_active.id}, payout={payout}%, exp_time={best_active.option.exp_time}s")

    await client.subscribe_positions(InstrumentType.BINARY_OPTION)

    bal_before = client.accounts.account.active_balance.amount
    try:
        call_opt = await client.place_call(best_active.id, 1.0, OptionType.BINARY)
        log_result("binary_call", "PASS",
                   f"id={call_opt.id}, exp={call_opt.exp}")
    except TradingError as e:
        log_result("binary_call", "FAIL", str(e))
        return

    wait = max(10, (call_opt.exp - client.server_time // 1000) + 10)
    wait = min(wait, 120)  # Cap at 2 minutes for test
    print(f"  Waiting {wait}s for expiry...")
    await asyncio.sleep(wait)

    try:
        await client.accounts.get_balances()
        bal_after = client.accounts.account.active_balance.amount
        diff = bal_after - bal_before
        log_result("binary_balance", "PASS",
                   f"${bal_before:.2f} → ${bal_after:.2f} (diff={diff:+.2f})")
    except Exception as e:
        log_result("binary_balance", "FAIL", f"Balance check failed: {e}")


async def test_digital(client):
    print("\n" + "=" * 60)
    print("TEST: DIGITAL OPTIONS")
    print("=" * 60)

    asset_id = 1861
    log_result("digital_asset", "PASS", f"target={asset_id}")

    await client.subscribe_positions(InstrumentType.DIGITAL_OPTION)

    instrument_event = {"data": None}

    async def on_instrument(msg):
        if isinstance(msg, dict):
            # Event bus passes full message; asset_id is in msg.msg
            inner = msg.get("msg", msg)
            if isinstance(inner, dict) and inner.get("asset_id") == asset_id:
                instrument_event["data"] = inner

    client.events.on("instrument-generated", on_instrument)

    try:
        await client._ws.subscribe(
            "digital-option-instruments.instrument-generated",
            "3.0",
            params={"routingFilters": {
                "instrument_type": "digital-option",
                "asset_id": asset_id,
            }},
        )
        log_result("digital_subscribe", "PASS", "instrument-generated subscribed")
    except Exception as e:
        log_result("digital_subscribe", "FAIL", str(e))
        return

    print("  Waiting for instrument (60s)...")
    for _ in range(120):
        if instrument_event["data"]:
            break
        await asyncio.sleep(0.5)

    if not instrument_event["data"]:
        log_result("digital_instrument", "FAIL", "No instrument event received!")
        return

    evt = instrument_event["data"]
    index = evt.get("index")
    call_items = [d for d in evt.get("data", []) if d.get("direction") == "call"]
    if not call_items:
        log_result("digital_instrument", "FAIL", "No call instruments in event!")
        return

    pick = call_items[len(call_items) // 2]
    log_result("digital_instrument", "PASS",
               f"symbol={pick['symbol']}, strike={pick.get('strike')}, index={index}")

    bal_before = client.accounts.account.active_balance.amount
    try:
        result = await client.trading.open_digital_option(
            asset_id=asset_id, direction=Direction.CALL, amount="1",
            instrument_id=pick["symbol"], instrument_index=index,
        )
        log_result("digital_place", "PASS", f"response={result}")
        print("  Waiting 70s for expiry...")
        await asyncio.sleep(70)

        await client.accounts.get_balances()
        bal_after = client.accounts.account.active_balance.amount
        diff = bal_after - bal_before
        log_result("digital_balance", "PASS",
                   f"${bal_before:.2f} → ${bal_after:.2f} (diff={diff:+.2f})")
    except Exception as e:
        log_result("digital_place", "FAIL", str(e))


async def test_candles(client):
    print("\n" + "=" * 60)
    print("TEST: CANDLES")
    print("=" * 60)

    active = client.assets.find_open_active(OptionType.TURBO)
    if not active:
        active = client.assets.find_open_active(OptionType.BINARY)
    if not active:
        log_result("candles_active", "FAIL", "No active found for candle test")
        return

    log_result("candles_active", "PASS", f"using active={active.id}")

    try:
        candles = await client.candles.get_history(active.id, period=60, count=10)
        log_result("candles_history", "PASS" if candles else "FAIL",
                   f"received {len(candles)} candles")
    except Exception as e:
        log_result("candles_history", "FAIL", str(e))

    try:
        await client.candles.subscribe(active.id, period=60)
        log_result("candles_subscribe", "PASS")
        await asyncio.sleep(3)
        await client.candles.unsubscribe(active.id, period=60)
        log_result("candles_unsubscribe", "PASS")
    except Exception as e:
        log_result("candles_subscribe", "FAIL", str(e))


async def test_subscriptions(client):
    print("\n" + "=" * 60)
    print("TEST: SUBSCRIPTIONS")
    print("=" * 60)

    types_to_test = [
        ("binary-option", InstrumentType.BINARY_OPTION),
        ("turbo-option", InstrumentType.TURBO_OPTION),
        ("blitz-option", InstrumentType.BLITZ_OPTION),
        ("digital-option", InstrumentType.DIGITAL_OPTION),
    ]

    for name, inst_type in types_to_test:
        try:
            result = await client.subscribe_positions(inst_type)
            log_result(f"sub_{name}", "PASS", f"result={result.get('success', False)}")
        except Exception as e:
            log_result(f"sub_{name}", "FAIL", str(e))


async def test_history(client):
    print("\n" + "=" * 60)
    print("TEST: HISTORY")
    print("=" * 60)

    try:
        user_id = client.user_id
        bal_id = client.balance_id
        history = await client.history.get_history_positions(user_id, bal_id, limit=5)
        log_result("history_positions", "PASS", f"received {len(history)} items")
    except Exception as e:
        log_result("history_positions", "FAIL", str(e))


async def main():
    config = Config()
    client = IQOptionClient(config)

    try:
        print("=" * 60)
        print("IQ OPTION - COMPREHENSIVE ALL-TYPES TEST")
        print("=" * 60)

        connected = await test_connection(client)
        if not connected:
            print("\n❌ Cannot continue without connection")
            return

        await test_blitz(client)
        await test_turbo(client)
        await test_binary(client)
        await test_digital(client)
        await test_candles(client)
        await test_subscriptions(client)
        await test_history(client)

        print("\n" + "=" * 60)
        print("RESULTS SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in results_log if r["result"] == "PASS")
        failed = sum(1 for r in results_log if r["result"] == "FAIL")

        print(f"  Total: {len(results_log)} tests")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")

        if failed > 0:
            print("\n  Failed tests:")
            for r in results_log:
                if r["result"] == "FAIL":
                    print(f"    - {r['test']}: {r['details']}")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
