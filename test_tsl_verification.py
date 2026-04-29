#!/usr/bin/env python3
"""
TSL PERSISTENCE & SAFETY VERIFICATION
──────────────────────────────────────────
Final pre-deployment verification covering every scenario
the user specified. Tests REAL TradeManager logic with mocked broker.
"""
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch
from copy import deepcopy

# ─── Setup (disable live API and Telegram) ──────────────────────────────
os.environ['API_KEY'] = 'test'
os.environ['API_SECRET'] = 'test'
os.environ['ACCESS_TOKEN'] = 'test'
os.environ['TELEGRAM_BOT_TOKEN'] = ''
os.environ['TELEGRAM_CHAT_ID'] = ''

import config
import notifier

notifier.send_telegram = lambda msg: None

PASS = 0
FAIL = 0
STATE_FILE = 'trade_state.json'
BACKUP_STATE = None


def log_pass(msg):
    global PASS; PASS += 1; print(f"    ✅ {msg}")

def log_fail(msg):
    global FAIL; FAIL += 1; print(f"    ❌ FAIL: {msg}")

def check(condition, pass_msg, fail_msg):
    if condition: log_pass(pass_msg)
    else: log_fail(fail_msg)

def backup_state():
    global BACKUP_STATE
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: BACKUP_STATE = f.read()
    else: BACKUP_STATE = None

def restore_state():
    if BACKUP_STATE is not None:
        with open(STATE_FILE, 'w') as f: f.write(BACKUP_STATE)
    elif os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def create_mock_broker():
    from kite_broker import KiteBroker
    with patch.object(KiteBroker, 'initialize_kite'):
        broker = KiteBroker()
        broker.kite = MagicMock()
        broker.instruments_cache = []
        broker.instruments_cache_time = datetime.now()
    return broker

def create_manager():
    from trade_manager import TradeManager
    with patch('trade_manager.KiteBroker', side_effect=lambda: create_mock_broker()), \
         patch('trade_manager.DataFetcher') as MockDF:
        mock_df = MockDF.return_value
        mock_df.get_india_vix.return_value = 18.0
        mock_df.get_current_price.return_value = 24150.0
        mgr = TradeManager()
        mgr.data_fetcher = mock_df
    return mgr

def write_state(state_dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state_dict, f, indent=2)

def read_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 1: TSL active → no new entries while trade is open
# ════════════════════════════════════════════════════════════════════════
def test_1_no_new_entry_during_active_tsl():
    print("\n" + "═" * 70)
    print("  SCENARIO 1: TSL active → bot must NOT place new entries")
    print("═" * 70)

    backup_state()
    try:
        mgr = create_manager()
        mgr.prev_high = 24310.0
        mgr.prev_low = 24100.0

        # Set up active trade with TSL
        mgr.current_position = 'CE'
        mgr.entry_price = 150.0
        mgr.stop_loss = 159.0       # TSL moved to +6%
        mgr.target = 234.0
        mgr.strike = 24350
        mgr.quantity = 195
        mgr.order_id = 'ORD_1'
        mgr.trades_today = 1
        mgr.trailing_sl_active = True
        mgr.highest_price_seen = 177.0
        mgr.high_breakout_triggered = True

        # Test can_take_new_trade — must be False (both guards active)
        check(mgr.can_take_new_trade() == False,
              "can_take_new_trade() = False (position open + trades_today=1)",
              f"can_take_new_trade() returned True! DANGEROUS")

        # Simulate breakout prices — should NOT enter
        for price in [24315, 24320, 24330]:
            mgr.data_fetcher.get_current_price.return_value = price
            old_trades = mgr.trades_today
            mgr.check_entry_conditions()
            check(mgr.trades_today == old_trades,
                  f"Price {price}: no new trade placed",
                  f"Price {price}: DUPLICATE TRADE placed!")

        # Also test low breakout — must not trigger because position is open
        for price in [24095, 24090]:
            mgr.data_fetcher.get_current_price.return_value = price
            old_pos = mgr.current_position
            mgr.check_entry_conditions()
            check(mgr.current_position == old_pos,
                  f"Price {price}: low breakout blocked while CE position open",
                  f"Price {price}: OPENED PE while CE is active!")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 2: Full restart recovery with all 5 state fields
# ════════════════════════════════════════════════════════════════════════
def test_2_restart_recovery_all_fields():
    print("\n" + "═" * 70)
    print("  SCENARIO 2: Restart recovery — all 5 critical fields")
    print("═" * 70)

    backup_state()
    try:
        today = datetime.now().strftime('%Y-%m-%d')

        # ─── Phase A: Simulate mid-trade state at +30% profit ───
        pre_crash = {
            'date': today,
            'prev_high': 24310.2,
            'prev_low': 24134.8,
            'current_position': 'CE',
            'entry_price': 150.0,
            'stop_loss': 172.5,       # TSL locked at +15% (step 3)
            'target': 231.0,
            'order_id': 'ORD_CRASH',
            'strike': 24350,
            'quantity': 195,
            'trades_today': 1,
            'high_breakout_triggered': True,
            'low_breakout_triggered': False,
            'trailing_sl_active': True,
            'highest_price_seen': 198.0,
        }
        write_state(pre_crash)

        # ─── Phase B: "Restart" — create fresh manager ───
        mgr = create_manager()

        print("\n    Verifying all 5 critical fields:")
        check(mgr.entry_price == 150.0,
              f"① entry_price = ₹{mgr.entry_price}", f"entry_price WRONG: {mgr.entry_price}")
        check(mgr.stop_loss == 172.5,
              f"② stop_loss = ₹{mgr.stop_loss} (TSL +15%)", f"stop_loss WRONG: {mgr.stop_loss}")
        check(mgr.highest_price_seen == 198.0,
              f"③ highest_price_seen = ₹{mgr.highest_price_seen}", f"highest_price_seen WRONG: {mgr.highest_price_seen}")
        check(mgr.trailing_sl_active == True,
              f"④ trailing_sl_active = True", f"trailing_sl_active WRONG: {mgr.trailing_sl_active}")
        check(mgr.current_position == 'CE',
              f"⑤ current_position = CE", f"current_position WRONG: {mgr.current_position}")

        # ─── Phase C: Continue trailing from correct step ───
        print("\n    Verifying TSL continues from correct step:")

        # Price at ₹180 (+20%) — below +30% step, SL should stay at ₹172.5
        old_sl = mgr.stop_loss
        mgr.update_trailing_sl(180.0)
        check(mgr.stop_loss == old_sl,
              f"Price ₹180 (+20%): SL stays ₹{mgr.stop_loss} (no regression)",
              f"SL REGRESSED to ₹{mgr.stop_loss}")

        # Price at ₹213 (+42%) — should advance to +25% lock
        mgr.update_trailing_sl(213.0)
        expected = round(150.0 * 1.25, 2)
        check(mgr.stop_loss == expected,
              f"Price ₹213 (+42%): SL advances to ₹{mgr.stop_loss} (+25% lock)",
              f"SL WRONG: ₹{mgr.stop_loss}, expected ₹{expected}")

        # Price at ₹200 (drops) — SL must NOT go back down
        old_sl = mgr.stop_loss
        mgr.update_trailing_sl(200.0)
        check(mgr.stop_loss == old_sl,
              f"Price ₹200 (drop): SL stays ₹{mgr.stop_loss}",
              f"SL REGRESSED to ₹{mgr.stop_loss}")

        # ─── Phase D: No duplicate trade ───
        check(mgr.trades_today == 1,
              "trades_today = 1 after restart (no duplicate entry possible)",
              f"trades_today = {mgr.trades_today}")
        check(mgr.can_take_new_trade() == False,
              "can_take_new_trade() = False after restart",
              "can_take_new_trade() = True AFTER RESTART!")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 3: After TSL/Target exit → MAX_TRADES=1 blocks re-entry
# ════════════════════════════════════════════════════════════════════════
def test_3_no_reentry_after_exit():
    print("\n" + "═" * 70)
    print("  SCENARIO 3: After exit (TSL/Target) → no re-entry")
    print("═" * 70)

    backup_state()
    try:
        mgr = create_manager()
        mgr.prev_high = 24310.0
        mgr.prev_low = 24100.0

        # Simulate state AFTER a completed trade
        mgr.current_position = None
        mgr.entry_price = None
        mgr.stop_loss = None
        mgr.target = None
        mgr.strike = None
        mgr.quantity = None
        mgr.order_id = None
        mgr.trailing_sl_active = False
        mgr.highest_price_seen = 0.0
        mgr.trades_today = 1          # Already took one trade
        mgr.high_breakout_triggered = True

        check(mgr.can_take_new_trade() == False,
              "can_take_new_trade() = False (trades_today=1, MAX=1)",
              "can_take_new_trade() = True — RE-ENTRY BUG!")

        # Even with new breakout signals, must NOT enter
        mgr.data_fetcher.get_current_price.return_value = 24320
        mgr.check_entry_conditions()
        check(mgr.current_position is None,
              "New high breakout at ₹24320: blocked (MAX_TRADES reached)",
              f"RE-ENTERED at ₹24320! position = {mgr.current_position}")

        # Test low breakout too
        mgr.data_fetcher.get_current_price.return_value = 24090
        mgr.check_entry_conditions()
        check(mgr.current_position is None,
              "New low breakout at ₹24090: blocked (MAX_TRADES reached)",
              f"RE-ENTERED at ₹24090! position = {mgr.current_position}")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 4: No partial selling — always full quantity exit
# ════════════════════════════════════════════════════════════════════════
def test_4_no_partial_sells():
    print("\n" + "═" * 70)
    print("  SCENARIO 4: No partial selling — full quantity exit only")
    print("═" * 70)

    backup_state()
    try:
        mgr = create_manager()

        # Set up position with known quantity
        mgr.current_position = 'CE'
        mgr.entry_price = 150.0
        mgr.stop_loss = 123.0
        mgr.target = 234.0
        mgr.strike = 24350
        mgr.quantity = 195
        mgr.order_id = 'ORD_FULL'
        mgr.trades_today = 1

        # Track what quantity the exit order sends
        exit_calls = []
        def track_exit(strike, option_type, quantity=150, max_attempts=10):
            exit_calls.append(quantity)
            return {
                'status': 'COMPLETE',
                'order_id': 'EXIT_FULL',
                'average_price': 120.0,
                'filled_quantity': quantity,
            }

        mgr.broker.exit_position_verified = track_exit

        # Trigger SL exit
        mgr.exit_trade("STOP_LOSS", 120.0)

        check(len(exit_calls) == 1,
              "Exactly 1 exit order placed",
              f"{len(exit_calls)} exit orders placed!")

        check(exit_calls[0] == 195,
              f"Exit quantity = {exit_calls[0]} (full position, no partial)",
              f"Exit quantity = {exit_calls[0]} — PARTIAL SELL!")

        # Verify NO code path sends less than full quantity
        # Search for any hardcoded partial sell logic
        import inspect
        source = inspect.getsource(type(mgr))
        check('quantity / 2' not in source and 'quantity // 2' not in source
              and 'partial' not in source.lower(),
              "No partial sell logic found in TradeManager source",
              "PARTIAL SELL LOGIC DETECTED in source!")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 5: After restart, no new orders unless previous trade closed
# ════════════════════════════════════════════════════════════════════════
def test_5_restart_no_orders_unless_closed():
    print("\n" + "═" * 70)
    print("  SCENARIO 5: After restart — no new orders unless trade is closed")
    print("═" * 70)

    backup_state()
    try:
        today = datetime.now().strftime('%Y-%m-%d')

        # ─── Case A: Restart with ACTIVE position ───
        print("\n    Case A: Restart with active position")
        write_state({
            'date': today,
            'prev_high': 24310.2, 'prev_low': 24134.8,
            'current_position': 'CE',
            'entry_price': 150.0, 'stop_loss': 159.0,
            'target': 231.0, 'order_id': 'ORD_ACTIVE',
            'strike': 24350, 'quantity': 195,
            'trades_today': 1,
            'high_breakout_triggered': True,
            'low_breakout_triggered': False,
            'trailing_sl_active': True,
            'highest_price_seen': 180.0,
        })

        mgr = create_manager()

        check(mgr.current_position == 'CE',
              "Position restored: CE",
              f"Position not restored: {mgr.current_position}")
        check(mgr.can_take_new_trade() == False,
              "can_take_new_trade() = False (active position)",
              "can_take_new_trade() = True while position is open!")

        # Simulate breakout — must NOT enter
        mock_broker = MagicMock()
        entry_called = [False]
        original_enter = mgr.enter_trade
        def track_enter(*args, **kwargs):
            entry_called[0] = True
            original_enter(*args, **kwargs)
        mgr.enter_trade = track_enter

        mgr.data_fetcher.get_current_price.return_value = 24320
        mgr.check_entry_conditions()

        check(entry_called[0] == False,
              "enter_trade() NOT called while position is active",
              "enter_trade() WAS called — DUPLICATE ENTRY!")

        # ─── Case B: Restart with CLOSED position but trades_today=1 ───
        print("\n    Case B: Restart with closed position, trades_today=1")
        write_state({
            'date': today,
            'prev_high': 24310.2, 'prev_low': 24134.8,
            'current_position': None,
            'entry_price': None, 'stop_loss': None,
            'target': None, 'order_id': None,
            'strike': None, 'quantity': None,
            'trades_today': 1,
            'high_breakout_triggered': True,
            'low_breakout_triggered': False,
            'trailing_sl_active': False,
            'highest_price_seen': 0.0,
        })

        mgr2 = create_manager()
        check(mgr2.can_take_new_trade() == False,
              "can_take_new_trade() = False (trades_today=1, MAX=1)",
              "can_take_new_trade() = True — would re-enter!")

        # ─── Case C: Restart with NO previous state (new day) ───
        print("\n    Case C: Restart with no state (fresh day)")
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)

        mgr3 = create_manager()
        check(mgr3.current_position is None,
              "No position on fresh start",
              f"Ghost position: {mgr3.current_position}")
        check(mgr3.trades_today == 0,
              "trades_today = 0 on fresh start",
              f"trades_today = {mgr3.trades_today}")
        check(mgr3.trailing_sl_active == False,
              "TSL inactive on fresh start",
              f"TSL active on fresh start!")
        check(mgr3.highest_price_seen == 0.0,
              "highest_price_seen = 0 on fresh start",
              f"highest_price_seen = {mgr3.highest_price_seen}")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# SCENARIO 6: Complete trade lifecycle — entry → TSL steps → exit → blocked
# ════════════════════════════════════════════════════════════════════════
def test_6_full_lifecycle():
    print("\n" + "═" * 70)
    print("  SCENARIO 6: Full lifecycle — entry → TSL → exit → blocked")
    print("═" * 70)

    backup_state()
    try:
        mgr = create_manager()
        mgr.prev_high = 24310.0
        mgr.prev_low = 24100.0

        # ─── STEP 1: Entry ───
        print("\n    Step 1: Entry")
        mgr.broker.get_atm_strike = MagicMock(return_value=24350)
        mgr.broker.get_nearest_expiry = MagicMock(return_value='2026-04-29')
        mgr.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24350CE')
        mgr.broker.get_option_ltp = MagicMock(return_value=100.0)
        mgr.broker.calculate_quantity = MagicMock(return_value=195)
        mgr.broker.place_option_order_verified = MagicMock(return_value={
            'status': 'COMPLETE', 'order_id': 'LIFE_1',
            'average_price': 100.0, 'filled_quantity': 195,
        })
        mgr.data_fetcher.get_india_vix.return_value = 18.0

        mgr.enter_trade("CE", 24315.0)

        check(mgr.current_position == 'CE', "Position entered: CE", f"No position: {mgr.current_position}")
        check(mgr.entry_price == 100.0, "Entry: ₹100", f"Entry wrong: {mgr.entry_price}")
        check(mgr.trailing_sl_active == False, "TSL not yet active", "TSL active before any profit!")
        check(mgr.highest_price_seen == 100.0, "highest_price_seen = ₹100 (entry)", f"wrong: {mgr.highest_price_seen}")
        check(mgr.trades_today == 1, "trades_today = 1", f"trades_today = {mgr.trades_today}")

        # ─── STEP 2: Price rises to +9% → TSL step 1 ───
        print("\n    Step 2: TSL Step 1 (+9% → SL = break-even)")
        mgr.update_trailing_sl(109.0)
        check(mgr.stop_loss == 100.0, f"SL = ₹{mgr.stop_loss} (break-even)", f"SL wrong: {mgr.stop_loss}")
        check(mgr.trailing_sl_active == True, "TSL now active", "TSL not activated!")

        # ─── STEP 3: Price rises to +18% → TSL step 2 ───
        print("\n    Step 3: TSL Step 2 (+18% → SL = +6%)")
        mgr.update_trailing_sl(118.0)
        expected_sl = round(100.0 * 1.06, 2)
        check(mgr.stop_loss == expected_sl, f"SL = ₹{mgr.stop_loss} (+6%)", f"SL wrong: {mgr.stop_loss}")

        # ─── STEP 4: Price rises to +30% → TSL step 3 ───
        print("\n    Step 4: TSL Step 3 (+30% → SL = +15%)")
        mgr.update_trailing_sl(130.0)
        expected_sl = round(100.0 * 1.15, 2)
        check(mgr.stop_loss == expected_sl, f"SL = ₹{mgr.stop_loss} (+15%)", f"SL wrong: {mgr.stop_loss}")

        # ─── STEP 5: Price drops, SL holds ───
        print("\n    Step 5: Price drops to ₹120 — SL must hold")
        old_sl = mgr.stop_loss
        mgr.update_trailing_sl(120.0)
        check(mgr.stop_loss == old_sl, f"SL holds at ₹{mgr.stop_loss}", f"SL regressed: {mgr.stop_loss}")

        # ─── STEP 6: Persist and restart ───
        print("\n    Step 6: Persist → restart → verify")
        mgr.save_state()
        state = read_state()
        check(state['trailing_sl_active'] == True, "State file: trailing_sl_active=True", "NOT persisted!")
        check(state['highest_price_seen'] == 130.0, "State file: highest_price_seen=₹130", f"wrong: {state['highest_price_seen']}")
        check(state['stop_loss'] == mgr.stop_loss, f"State file: stop_loss=₹{state['stop_loss']}", "NOT persisted!")

        # Create fresh manager (simulate restart)
        mgr2 = create_manager()
        check(mgr2.stop_loss == mgr.stop_loss, f"Post-restart SL = ₹{mgr2.stop_loss}", f"SL changed: {mgr2.stop_loss}")
        check(mgr2.trailing_sl_active == True, "Post-restart TSL active", "TSL lost!")
        check(mgr2.highest_price_seen == 130.0, f"Post-restart peak = ₹{mgr2.highest_price_seen}", f"Peak lost: {mgr2.highest_price_seen}")

        # ─── STEP 7: Exit via trailing SL hit ───
        print("\n    Step 7: Price drops below trailing SL → exit")
        mgr2.broker.get_nearest_expiry = MagicMock(return_value='2026-04-29')
        mgr2.broker.get_option_symbol = MagicMock(return_value='NIFTY26APR24350CE')
        mgr2.broker.reconcile_position = MagicMock(return_value={
            'tradingsymbol': 'NIFTY26APR24350CE', 'actual_entry': 100.0,
            'quantity': 195, 'pnl': 1950.0, 'last_price': 114.0,
            'buy_price': 100.0, 'buy_quantity': 195,
        })
        mgr2.broker.get_option_ltp = MagicMock(return_value=114.0)  # Below SL of ₹115
        mgr2.broker.exit_position_verified = MagicMock(return_value={
            'status': 'COMPLETE', 'order_id': 'EXIT_TSL',
            'average_price': 114.5, 'filled_quantity': 195,
        })

        mgr2.check_exit_conditions()

        check(mgr2.current_position is None, "Position closed after TSL exit", f"Still open: {mgr2.current_position}")
        check(mgr2.trailing_sl_active == False, "TSL reset after exit", f"TSL still active!")
        check(mgr2.highest_price_seen == 0.0, "highest_price_seen reset", f"Not reset: {mgr2.highest_price_seen}")

        # ─── STEP 8: Verify no re-entry ───
        print("\n    Step 8: Verify blocked after exit")
        check(mgr2.trades_today == 1, "trades_today still 1", f"trades_today = {mgr2.trades_today}")
        check(mgr2.can_take_new_trade() == False, "can_take_new_trade() = False", "RE-ENTRY BUG!")

    finally:
        restore_state()


# ════════════════════════════════════════════════════════════════════════
# RUN ALL
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("  🔒 TSL PERSISTENCE & SAFETY VERIFICATION")
    print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    test_1_no_new_entry_during_active_tsl()
    test_2_restart_recovery_all_fields()
    test_3_no_reentry_after_exit()
    test_4_no_partial_sells()
    test_5_restart_no_orders_unless_closed()
    test_6_full_lifecycle()

    print("\n" + "=" * 70)
    total = PASS + FAIL
    if FAIL == 0:
        print(f"  🎉 ALL {total} CHECKS PASSED — SAFE FOR LIVE DEPLOYMENT")
    else:
        print(f"  ⚠️  {PASS}/{total} passed, {FAIL} FAILED — DO NOT DEPLOY")
    print("=" * 70)
    sys.exit(1 if FAIL > 0 else 0)
