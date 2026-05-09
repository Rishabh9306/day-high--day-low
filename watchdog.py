#!/usr/bin/env python3
"""
Watchdog — Monitors bot health via heartbeat file.
───────────────────────────────────────────────────
Detects silent hangs that PID-based checks miss:
  - Frozen websockets
  - Deadlocked polling loops
  - Hung API calls

How it works:
  - main.py writes current timestamp to .heartbeat every loop iteration
  - This watchdog checks if .heartbeat is stale (older than STALE_THRESHOLD)
  - If stale → kill bot, send Telegram alert, optionally restart

Usage:
  # One-shot check (for cron):
  python watchdog.py

  # Continuous monitoring:
  python watchdog.py --daemon

Cron (every 5 min during market hours):
  */5 9-15 * * 1-5 cd /home/draxxy/Projects/Random/dayhigh-daylow && .venv/bin/python watchdog.py >> logs/watchdog.log 2>&1
"""

import os
import sys
import time
import signal
from datetime import datetime
import pytz

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT_FILE = os.path.join(BOT_DIR, '.heartbeat')
PID_FILE = os.path.join(BOT_DIR, '.bot.pid')
PYTHON = os.path.join(BOT_DIR, '.venv/bin/python')
MAIN_PY = os.path.join(BOT_DIR, 'main.py')

# ── Configuration ────────────────────────────────────────────────────
STALE_THRESHOLD = 60      # seconds — heartbeat older than this = bot is hung
MAX_RESTARTS = 3          # max restarts per day before giving up
RESTART_COOLDOWN = 30     # seconds to wait after kill before restart
# ─────────────────────────────────────────────────────────────────────

IST = pytz.timezone('Asia/Kolkata')
restarts_today = 0
last_restart_date = None


def send_telegram(message: str):
    """Send alert via Telegram."""
    try:
        import notifier
        notifier.notify_error(message)
    except Exception as e:
        print(f"   Telegram failed: {e}")


def get_bot_pid() -> int:
    """Get bot PID from PID file, verify it's alive."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if alive
        return pid
    except (ProcessLookupError, ValueError, OSError):
        # Stale PID file — clean it
        os.remove(PID_FILE)
        return None


def get_heartbeat_age() -> float:
    """Returns age of heartbeat in seconds, or -1 if no heartbeat."""
    if not os.path.exists(HEARTBEAT_FILE):
        return -1
    try:
        with open(HEARTBEAT_FILE, 'r') as f:
            last_beat = float(f.read().strip())
        return time.time() - last_beat
    except (ValueError, OSError):
        return -1


def is_market_hours() -> bool:
    """Check if we're in trading hours (9:15 - 15:30 IST)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Weekend
        return False
    market_start = now.replace(hour=9, minute=15, second=0)
    market_end = now.replace(hour=15, minute=30, second=0)
    return market_start <= now <= market_end


def kill_bot(pid: int):
    """Force kill the bot process."""
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        print(f"   ✅ Killed PID {pid}")
    except ProcessLookupError:
        print(f"   PID {pid} already dead")
    # Clean up
    for f in (PID_FILE, HEARTBEAT_FILE):
        if os.path.exists(f):
            os.remove(f)


def restart_bot():
    """Restart the bot process."""
    global restarts_today, last_restart_date

    today = datetime.now(IST).strftime('%Y-%m-%d')
    if last_restart_date != today:
        restarts_today = 0
        last_restart_date = today

    if restarts_today >= MAX_RESTARTS:
        msg = f"🚨 WATCHDOG: Max restarts ({MAX_RESTARTS}) reached for today. NOT restarting."
        print(msg)
        send_telegram(msg)
        return False

    print(f"   🔄 Restarting bot (attempt {restarts_today + 1}/{MAX_RESTARTS})...")
    time.sleep(RESTART_COOLDOWN)

    os.system(
        f"nohup {PYTHON} -u {MAIN_PY} "
        f">> {BOT_DIR}/logs/bot.log 2>> {BOT_DIR}/logs/bot-error.log &"
    )

    time.sleep(3)

    new_pid = get_bot_pid()
    if new_pid:
        restarts_today += 1
        msg = f"🔄 WATCHDOG RESTART: Bot restarted (PID: {new_pid}, restart #{restarts_today} today)"
        print(f"   ✅ {msg}")
        send_telegram(msg)
        return True
    else:
        msg = "🚨 WATCHDOG: Restart FAILED — bot did not come up"
        print(f"   ❌ {msg}")
        send_telegram(msg)
        return False


def check_health():
    """
    Main health check. Returns True if healthy, False if action was taken.
    """
    now = datetime.now(IST)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S IST')}] Watchdog check")

    pid = get_bot_pid()
    heartbeat_age = get_heartbeat_age()

    # Case 1: No bot running
    if pid is None:
        if is_market_hours():
            print("   ⚠️  Bot is NOT running during market hours!")
            send_telegram("🚨 WATCHDOG: Bot is not running during market hours! Restarting...")
            restart_bot()
            return False
        else:
            print("   ✅ Bot not running (outside market hours — OK)")
            return True

    # Case 2: Bot running, no heartbeat file
    if heartbeat_age < 0:
        print(f"   ⚠️  Bot running (PID: {pid}) but no heartbeat file")
        print(f"   Waiting — bot may still be initializing")
        return True  # Don't act yet

    # Case 3: Bot running, heartbeat is fresh
    if heartbeat_age <= STALE_THRESHOLD:
        print(f"   ✅ Bot healthy (PID: {pid}, heartbeat: {heartbeat_age:.0f}s ago)")
        return True

    # Case 4: Bot running, heartbeat is STALE — silent hang detected
    msg = (f"🚨 WATCHDOG: Bot HUNG!\n"
           f"PID: {pid}\n"
           f"Last heartbeat: {heartbeat_age:.0f}s ago (threshold: {STALE_THRESHOLD}s)\n"
           f"Killing and restarting...")
    print(f"   🚨 STALE HEARTBEAT: {heartbeat_age:.0f}s (threshold: {STALE_THRESHOLD}s)")
    print(f"   Bot is likely hung — killing PID {pid}")
    send_telegram(msg)

    kill_bot(pid)

    if is_market_hours():
        restart_bot()

    return False


def run_daemon():
    """Continuous monitoring mode."""
    print("🐕 Watchdog started in daemon mode (checking every 30s)")
    try:
        while True:
            check_health()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n👋 Watchdog stopped")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        run_daemon()
    else:
        check_health()


if __name__ == "__main__":
    main()
