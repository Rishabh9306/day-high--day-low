#!/usr/bin/env python3
"""
Production Readiness Test Suite
────────────────────────────────
Tests the REAL TradeManager logic with mocked broker calls.
Covers: restart recovery, reconciliation, order failures,
fast-tick duplicate prevention, and EOD square-off safety.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from copy import deepcopy

# ─── Setup ──────────────────────────────────────────────────────────────
os.environ['API_KEY'] = 'test'
os.environ['API_SECRET'] = 'test'
os.environ['ACCESS_TOKEN'] = 'test'
os.environ['TELEGRAM_BOT_TOKEN'] = ''  # Disable telegram for tests
os.environ['TELEGRAM_CHAT_ID'] = ''

import config
import notifier

# Silence telegram during tests
notifier.send_telegram = lambda msg: None

PASS = 0
FAIL = 0
STATE_FILE = 'trade_state.json'
BACKUP_STATE = None


def log_pass(msg):
    global PASS
    PASS += 1
    print(f"  ✅ {msg}")


def log_fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ❌ {msg}")


def assert_check(condition, pass_msg, fail_msg):
    if condition:
        log_pass(pass_msg)
    else:
        log_fail(fail_msg)


def backup_state():
    global BACKUP_STATE
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            BACKUP_STATE = f.read()
    else:
        BACKUP_STATE = None


def restore_state():
    global BACKUP_STATE
    if BACKUP_STATE is not None:
        with open(STATE_FILE, 'w') as f:
            f.write(BACKUP_STATE)
    elif os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def create_mock_broker():
    """Create a mock KiteBroker that doesn't hit any APIs"""
    from kite_broker import KiteBroker

    with patch.object(KiteBroker, 'initialize_kite'):
        broker = KiteBroker()
        broker.kite = MagicMock()
        broker.instruments_cache = []
        broker.instruments_cache_time = datetime.now()
    return broker


def create_test_manager():
    """Create a TradeManager with fully mocked broker"""
    from trade_manager import TradeManager

    with patch('trade_manager.KiteBroker', side_effect=lambda: create_mock_broker()), \
         patch('trade_manager.DataFetcher') as MockDF:
        mock_df = MockDF.return_value
        mock_df.get_india_vix.return_value = 18.0
        mock_df.get_current_price.return_value = 24150.0
        manager = TradeManager()
        manager.data_fetcher = mock_df
    return manager


# ════════════════════════════════════════════════════════════════════════
# TEST 1: RESTART RECOVERY
# ════════════════════════════════════════════════════════════════════════
def test_restart_recovery():
    print("\n" + "━" * 70)
    print("TEST 1: RESTART RECOVERY — Trade at +25%, kill, restart")
    print("━" * 70)

    backup_state()

    try:
        # Phase 1: Simulate a trade that reached +25% profit with TSL active
        state_before_crash = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'prev_high': 24310.2,
            'prev_low': 24134.8,
            'current_position': 'CE',
            'entry_price': 150.0,
            'stop_loss': 159.0,      # TSL moved to +6% (from +18% step)
            'target': 234.0,
            'order_id': 'ORDER_123',
            'strike': 24150,
            'quantity': 195,
            'trades_today': 1,
            'high_breakout_triggered': True,
            'low_breakout_triggered': False,
            'trailing_sl_active': True,
            'highest_price_seen': 187.5,  # Peak was +25%
        }

        # Write pre-crash state
        with open(STATE_FILE, 'w') as f:
            json.dump(state_before_crash, f, indent=2)

        # Phase 2: "Restart" — create fresh manager (simulates bot restart)
        manager = create_test_manager()

        # Verify all state loaded correctly
        assert_check(
            manager.current_position == 'CE',
            "Position restored: CE",
            f"Position NOT restored: {manager.current_position}"
        )
        assert_check(
            manager.entry_price == 150.0,
            "Entry price restored: ₹150.0",
            f"Entry price wrong: {manager.entry_price}"
        )
        assert_check(
            manager.stop_loss == 159.0,
            "Trailing SL restored: ₹159.0 (+6%)",
            f"SL wrong: {manager.stop_loss} (should be 159.0)"
        )
        assert_check(
            manager.trailing_sl_active == True,
            "trailing_sl_active = True",
            f"trailing_sl_active wrong: {manager.trailing_sl_active}"
        )
        assert_check(
            manager.highest_price_seen == 187.5,
            "highest_price_seen restored: ₹187.5",
            f"highest_price_seen wrong: {manager.highest_price_seen}"
        )
        assert_check(
            manager.trades_today == 1,
            "trades_today = 1 (prevents duplicate entry)",
            f"trades_today wrong: {manager.trades_today}"
        )
        assert_check(
            manager.order_id == 'ORDER_123',
            "order_id restored for reconciliation",
            f"order_id wrong: {manager.order_id}"
        )

        # Phase 3: Verify TSL doesn't regress after restart
        # Simulate current price at ₹170 (+13.3%) — below +18% step
        # SL should NOT move down from ₹159 to ₹150 (break-even)
        old_sl = manager.stop_loss
        manager.update_trailing_sl(170.0)
        assert_check(
            manager.stop_loss == old_sl,
            f"SL stayed at ₹{manager.stop_loss} after restart (no regression)",
            f"SL REGRESSED to ₹{manager.stop_loss} from ₹{old_sl}!"
        )

        # Phase 4: Verify TSL advances correctly post-restart
        # Price goes to ₹195 (+30%) — should advance to +15% lock
        manager.update_trailing_sl(195.0)
        expected_sl = round(150.0 * 1.15, 2)
        assert_check(
            manager.stop_loss == expected_sl,
            f"TSL advanced post-restart: SL = ₹{manager.stop_loss} (+15% lock)",
            f"TSL advance failed: SL = {manager.stop_loss}, expected {expected_sl}"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# TEST 2: BROKER RECONCILIATION
# ════════════════════════════════════════════════════════════════════════
def test_broker_reconciliation():
    print("\n" + "━" * 70)
    print("TEST 2: BROKER RECONCILIATION — Position/SL integrity after restart")
    print("━" * 70)

    backup_state()

    try:
        state = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'prev_high': 24310.2,
            'prev_low': 24134.8,
            'current_position': 'PE',
            'entry_price': 160.0,
            'stop_loss': 169.6,   # TSL at +6%
            'target': 249.6,
            'order_id': 'ORDER_456',
            'strike': 24100,
            'quantity': 195,
            'trades_today': 1,
            'high_breakout_triggered': False,
            'low_breakout_triggered': True,
            'trailing_sl_active': True,
            'highest_price_seen': 195.0,
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)

        manager = create_test_manager()

        # Mock broker returning a slightly different entry (fill price correction)
        broker_position = {
            'tradingsymbol': 'NIFTY26APR24100PE',
            'actual_entry': 162.5,  # Broker shows different fill price
            'quantity': 195,
            'pnl': 450.0,
            'last_price': 175.0,
            'buy_price': 162.5,
            'buy_quantity': 195,
        }

        # Mock the broker methods
        manager.broker.get_nearest_expiry = MagicMock(return_value='2026-04-28')
        manager.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24100PE')
        manager.broker.reconcile_position = MagicMock(return_value=broker_position)

        # Run reconciliation
        manager.reconcile_position()

        assert_check(
            manager.entry_price == 162.5,
            f"Entry price reconciled to broker: ₹{manager.entry_price}",
            f"Entry price NOT reconciled: {manager.entry_price}"
        )
        assert_check(
            manager.stop_loss is not None and manager.stop_loss > 0,
            f"SL recalculated after reconciliation: ₹{manager.stop_loss:.2f}",
            f"SL broken after reconciliation: {manager.stop_loss}"
        )
        assert_check(
            manager.current_position == 'PE',
            "Position type preserved: PE",
            f"Position type changed: {manager.current_position}"
        )

        # Test: broker says position is GONE (force-closed)
        manager.broker.reconcile_position = MagicMock(return_value=None)
        manager.reconcile_position()

        assert_check(
            manager.current_position is None,
            "Force-close detected: position reset to None",
            f"Force-close NOT detected: position = {manager.current_position}"
        )
        assert_check(
            manager.trailing_sl_active == False,
            "TSL state reset after force-close",
            f"TSL state NOT reset: {manager.trailing_sl_active}"
        )
        assert_check(
            manager.highest_price_seen == 0.0,
            "highest_price_seen reset after force-close",
            f"highest_price_seen NOT reset: {manager.highest_price_seen}"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# TEST 3: ORDER FAILURE HANDLING
# ════════════════════════════════════════════════════════════════════════
def test_order_failure_handling():
    print("\n" + "━" * 70)
    print("TEST 3: ORDER FAILURE HANDLING — Entry/exit failures")
    print("━" * 70)

    backup_state()

    try:
        manager = create_test_manager()
        manager.prev_high = 24310.2
        manager.prev_low = 24134.8

        # ─── Entry failure: place_option_order_verified returns None ───
        manager.broker.get_atm_strike = MagicMock(return_value=24150)
        manager.broker.get_nearest_expiry = MagicMock(return_value='2026-04-28')
        manager.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24150CE')
        manager.broker.get_option_ltp = MagicMock(return_value=155.0)
        manager.broker.calculate_quantity = MagicMock(return_value=195)
        manager.broker.place_option_order_verified = MagicMock(return_value=None)
        manager.data_fetcher.get_india_vix = MagicMock(return_value=18.0)

        manager.enter_trade("CE", 24350.0)

        assert_check(
            manager.current_position is None,
            "Entry failure: no position taken",
            f"Entry failure: position incorrectly set to {manager.current_position}"
        )
        assert_check(
            manager.trades_today == 0,
            "Entry failure: trades_today stays 0",
            f"Entry failure: trades_today = {manager.trades_today}"
        )
        assert_check(
            manager.trailing_sl_active == False,
            "Entry failure: TSL not activated",
            f"Entry failure: TSL incorrectly activated"
        )

        # ─── Entry failure: REJECTED order ───
        manager.broker.place_option_order_verified = MagicMock(return_value={
            'status': 'REJECTED',
            'error': 'Insufficient margin',
            'order_id': 'REJ_001'
        })
        manager.enter_trade("CE", 24350.0)

        assert_check(
            manager.current_position is None,
            "Rejected order: no position taken",
            f"Rejected order: position set to {manager.current_position}"
        )

        # ─── Exit failure: exit_position_verified returns non-COMPLETE ───
        # First, set up a valid position
        manager.current_position = 'CE'
        manager.entry_price = 150.0
        manager.stop_loss = 123.0
        manager.target = 234.0
        manager.strike = 24150
        manager.quantity = 195
        manager.order_id = 'ORDER_789'
        manager.trades_today = 1
        manager.trailing_sl_active = True
        manager.highest_price_seen = 180.0

        # Mock exit failure
        manager.broker.exit_position_verified = MagicMock(return_value={
            'status': 'PENDING',
            'order_id': 'EXIT_001'
        })

        manager.exit_trade("STOP_LOSS", 120.0)

        assert_check(
            manager.current_position == 'CE',
            "Exit failure: position PRESERVED (will retry next cycle)",
            f"Exit failure: position incorrectly cleared to {manager.current_position}"
        )
        assert_check(
            manager.entry_price == 150.0,
            "Exit failure: entry_price preserved",
            f"Exit failure: entry_price cleared to {manager.entry_price}"
        )
        assert_check(
            manager.trailing_sl_active == True,
            "Exit failure: TSL state preserved for retry",
            f"Exit failure: TSL state cleared"
        )

        # ─── Exit None result ───
        manager.broker.exit_position_verified = MagicMock(return_value=None)
        manager.exit_trade("STOP_LOSS", 120.0)

        assert_check(
            manager.current_position == 'CE',
            "Exit None: position PRESERVED",
            f"Exit None: position cleared to {manager.current_position}"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# TEST 4: FAST-TICK DUPLICATE PREVENTION
# ════════════════════════════════════════════════════════════════════════
def test_fast_tick_duplicates():
    print("\n" + "━" * 70)
    print("TEST 4: FAST-TICK DUPLICATE PREVENTION — Rapid breakouts")
    print("━" * 70)

    backup_state()

    try:
        manager = create_test_manager()
        manager.prev_high = 24310.2
        manager.prev_low = 24134.8

        # Mock successful trade entry
        manager.broker.get_atm_strike = MagicMock(return_value=24350)
        manager.broker.get_nearest_expiry = MagicMock(return_value='2026-04-28')
        manager.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24350CE')
        manager.broker.get_option_ltp = MagicMock(return_value=155.0)
        manager.broker.calculate_quantity = MagicMock(return_value=195)
        manager.broker.place_option_order_verified = MagicMock(return_value={
            'status': 'COMPLETE',
            'order_id': 'ORD_100',
            'average_price': 156.0,
            'filled_quantity': 195,
        })
        manager.data_fetcher.get_india_vix = MagicMock(return_value=18.0)

        # Simulate 10 rapid breakout signals (fast ticks above prev_high)
        prices = [24311, 24312, 24313, 24314, 24315, 24316, 24317, 24318, 24319, 24320]
        entries_made = 0

        for price in prices:
            manager.data_fetcher.get_current_price = MagicMock(return_value=price)
            old_trades = manager.trades_today
            manager.check_entry_conditions()
            if manager.trades_today > old_trades:
                entries_made += 1

        assert_check(
            entries_made == 1,
            f"Only 1 trade entered across 10 rapid ticks",
            f"DUPLICATE ENTRIES: {entries_made} trades entered!"
        )
        assert_check(
            manager.trades_today == 1,
            "trades_today = 1 after rapid fire",
            f"trades_today = {manager.trades_today}"
        )
        assert_check(
            manager.high_breakout_triggered == True,
            "high_breakout_triggered flag set",
            "high_breakout_triggered NOT set"
        )

        # Verify: even after exit, no re-entry (MAX_TRADES_PER_DAY = 1)
        manager.current_position = None  # Simulate exit
        manager.data_fetcher.get_current_price = MagicMock(return_value=24320)
        manager.check_entry_conditions()

        assert_check(
            manager.trades_today == 1,
            "No re-entry after exit (MAX_TRADES=1 enforced)",
            f"RE-ENTRY BUG: trades_today = {manager.trades_today}"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# TEST 5: END-OF-DAY SQUARE-OFF
# ════════════════════════════════════════════════════════════════════════
def test_eod_squareoff():
    print("\n" + "━" * 70)
    print("TEST 5: END-OF-DAY SQUARE-OFF — Forced exit at 15:15")
    print("━" * 70)

    backup_state()

    try:
        manager = create_test_manager()

        # Set up active position
        manager.current_position = 'PE'
        manager.entry_price = 160.0
        manager.stop_loss = 131.2
        manager.target = 249.6
        manager.strike = 24100
        manager.quantity = 195
        manager.order_id = 'ORDER_EOD'
        manager.trades_today = 1
        manager.trailing_sl_active = True
        manager.highest_price_seen = 190.0

        # Mock broker for exit
        manager.broker.get_nearest_expiry = MagicMock(return_value='2026-04-28')
        manager.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24100PE')
        manager.broker.get_option_ltp = MagicMock(return_value=175.0)
        manager.broker.exit_position_verified = MagicMock(return_value={
            'status': 'COMPLETE',
            'order_id': 'EXIT_EOD',
            'average_price': 174.5,
            'filled_quantity': 195,
        })

        # Verify EOD config
        assert_check(
            config.TRADING_END_HOUR == 15 and config.TRADING_END_MINUTE == 15,
            f"EOD time configured: {config.TRADING_END_HOUR}:{config.TRADING_END_MINUTE:02d}",
            f"EOD time wrong: {config.TRADING_END_HOUR}:{config.TRADING_END_MINUTE:02d}"
        )

        # Verify is_end_of_day logic
        from main import TradingBot
        with patch.object(TradingBot, '__init__', lambda self: None):
            bot = TradingBot()
            bot.trade_manager = manager
            bot.ist = manager.ist

            # 15:14 → NOT EOD
            with patch('main.datetime') as mock_dt:
                mock_now = datetime(2026, 4, 28, 15, 14, 0, tzinfo=manager.ist)
                mock_dt.now.return_value = mock_now
                assert_check(
                    not bot.is_end_of_day(),
                    "15:14 → NOT end of day",
                    "15:14 incorrectly flagged as EOD"
                )

            # 15:15 → IS EOD
            with patch('main.datetime') as mock_dt:
                mock_now = datetime(2026, 4, 28, 15, 15, 0, tzinfo=manager.ist)
                mock_dt.now.return_value = mock_now
                assert_check(
                    bot.is_end_of_day(),
                    "15:15 → IS end of day",
                    "15:15 NOT detected as EOD!"
                )

            # 15:20 → IS EOD
            with patch('main.datetime') as mock_dt:
                mock_now = datetime(2026, 4, 28, 15, 20, 0, tzinfo=manager.ist)
                mock_dt.now.return_value = mock_now
                assert_check(
                    bot.is_end_of_day(),
                    "15:20 → IS end of day",
                    "15:20 NOT detected as EOD!"
                )

        # Test actual square-off
        manager.end_of_day_cleanup()

        assert_check(
            manager.current_position is None,
            "EOD: position squared off",
            f"EOD: position NOT squared off: {manager.current_position}"
        )
        assert_check(
            manager.trailing_sl_active == False,
            "EOD: TSL state reset",
            f"EOD: TSL state NOT reset"
        )
        assert_check(
            manager.highest_price_seen == 0.0,
            "EOD: highest_price_seen reset",
            f"EOD: highest_price_seen NOT reset: {manager.highest_price_seen}"
        )

        # Verify no overnight carry possible (position is None after EOD)
        assert_check(
            manager.current_position is None and manager.entry_price is None,
            "No overnight carry: position and entry fully cleared",
            "OVERNIGHT CARRY RISK: state not fully cleared!"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# TEST 6: TSL HARD EXIT AT +54%
# ════════════════════════════════════════════════════════════════════════
def test_tsl_hard_exit():
    print("\n" + "━" * 70)
    print("TEST 6: TSL HARD EXIT — Forced exit at +54%")
    print("━" * 70)

    backup_state()

    try:
        manager = create_test_manager()
        manager.current_position = 'CE'
        manager.entry_price = 100.0
        manager.stop_loss = 82.0
        manager.target = 256.0
        manager.strike = 24150
        manager.quantity = 195
        manager.trades_today = 1
        manager.trailing_sl_active = False
        manager.highest_price_seen = 100.0

        # Test: price at +53% (should NOT hard exit)
        result = manager.update_trailing_sl(153.0)
        assert_check(
            result != 'EXIT',
            "+53% → no hard exit (correctly waiting)",
            "+53% incorrectly triggered hard exit!"
        )

        # Test: price at +54% (SHOULD hard exit)
        result = manager.update_trailing_sl(154.0)
        assert_check(
            result == 'EXIT',
            "+54% → HARD EXIT triggered correctly",
            f"+54% did NOT trigger hard exit, got: {result}"
        )

        # Verify SL was ratcheted up before exit
        assert_check(
            manager.stop_loss >= 125.0,
            f"SL ratcheted to ₹{manager.stop_loss} before hard exit",
            f"SL not ratcheted: ₹{manager.stop_loss}"
        )

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("🔒 PRODUCTION READINESS TEST SUITE")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_restart_recovery()
    test_broker_reconciliation()
    test_order_failure_handling()
    test_fast_tick_duplicates()
    test_eod_squareoff()
    test_tsl_hard_exit()

    print("\n" + "=" * 70)
    total = PASS + FAIL
    if FAIL == 0:
        print(f"🎉 ALL {total} CHECKS PASSED — PRODUCTION READY")
    else:
        print(f"⚠️  {PASS}/{total} passed, {FAIL} FAILED")
    print("=" * 70)

    sys.exit(1 if FAIL > 0 else 0)
