#!/bin/bash
#
# Daily Startup Script for Nifty 50 Breakout Trading Bot
#
# FULLY AUTOMATED — no browser, no manual login, no TOTP entry
# Runs entirely headless. Safe for cron jobs and VPS.
#
# Cron:  55 8 * * 1-5 cd /home/draxxy/Projects/Random/dayhigh-daylow && /bin/bash daily_start.sh >> logs/startup.log 2>&1
#

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$BOT_DIR/.venv/bin/python"
LOCK_FILE="$BOT_DIR/.startup.lock"
LOGIN_TIMEOUT=30  # seconds — kill auto_login if it hangs

# ══════════════════════════════════════════════════════════════
# GUARD 1: Prevent duplicate startup scripts (flock)
# If daily_start.sh is already running (e.g., cron overlap),
# this instance exits immediately without touching anything.
# ══════════════════════════════════════════════════════════════
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  Another daily_start.sh is already running. Exiting."
    exit 0
fi

# ══════════════════════════════════════════════════════════════
# LOG ROTATION (Point 5)
# Rotates logs daily. Keeps last 7 days.
# ══════════════════════════════════════════════════════════════
mkdir -p "$BOT_DIR/logs"
TODAY=$(date '+%Y-%m-%d')

rotate_log() {
    local logfile="$1"
    if [ -f "$logfile" ]; then
        local size=$(stat -c%s "$logfile" 2>/dev/null || echo 0)
        # Rotate if > 5MB
        if [ "$size" -gt 5242880 ]; then
            mv "$logfile" "${logfile}.${TODAY}.bak"
            touch "$logfile"
            echo "[$(date '+%H:%M:%S')] Log rotated (was ${size} bytes)" > "$logfile"
        fi
    fi
}

rotate_log "$BOT_DIR/logs/bot.log"
rotate_log "$BOT_DIR/logs/bot-error.log"
rotate_log "$BOT_DIR/logs/startup.log"

# Delete logs older than 7 days
find "$BOT_DIR/logs" -name "*.bak" -mtime +7 -delete 2>/dev/null

echo "========================================================================"
echo "🚀 NIFTY TRADING BOT — DAILY STARTUP (AUTOMATED)"
echo "   $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "========================================================================"
echo ""

# ══════════════════════════════════════════════════════════════
# GUARD 2: Stale PID cleanup (Point 1)
# Verify .bot.pid actually points to a live process.
# ══════════════════════════════════════════════════════════════
if [ -f "$BOT_DIR/.bot.pid" ]; then
    OLD_PID=$(cat "$BOT_DIR/.bot.pid" 2>/dev/null)
    if ! kill -0 "$OLD_PID" 2>/dev/null; then
        echo "   🧹 Removed stale .bot.pid (PID $OLD_PID is dead)"
        rm -f "$BOT_DIR/.bot.pid"
    fi
fi

# ══════════════════════════════════════════════════════════════
# GUARD 3: If bot is already running with a VALID token,
# don't kill it — just exit. Prevents cron from restarting
# a healthy bot mid-trade.
# ══════════════════════════════════════════════════════════════
BOT_PID=$(pgrep -f "main\.py" 2>/dev/null | head -1)
if [ -n "$BOT_PID" ]; then
    # Bot process exists — check if its token is still valid
    TOKEN_CHECK=$($PYTHON -c "
import config
from kiteconnect import KiteConnect
try:
    kite = KiteConnect(api_key=config.API_KEY)
    kite.set_access_token(config.ACCESS_TOKEN)
    kite.profile()
    print('VALID')
except:
    print('EXPIRED')
" 2>/dev/null)

    if [ "$TOKEN_CHECK" = "VALID" ]; then
        echo "✅ Bot is already running (PID: $BOT_PID) with a valid token."
        echo "   Nothing to do. Exiting."
        exit 0
    else
        echo "⚠️  Bot is running (PID: $BOT_PID) but token is EXPIRED."
        echo "   Killing ALL bot processes to refresh token..."
        pkill -9 -f "main\.py" 2>/dev/null
        sleep 1
        rm -f "$BOT_DIR/.bot.pid" "$BOT_DIR/.heartbeat"
        echo "   ✅ Bot stopped"
    fi
else
    echo "📍 Bot is not running (clean state)"
    rm -f "$BOT_DIR/.bot.pid" "$BOT_DIR/.heartbeat"
fi
echo ""

# ══════════════════════════════════════════════════════════════
# GUARD 4: Trading day validation (Point 4)
# Checks weekday + NSE holiday calendar.
# Prevents unnecessary login attempts on holidays.
# ══════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📅 Checking if today is a trading day..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TRADING_DAY=$($PYTHON -c "
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')
now = datetime.now(IST)

# Weekend check
if now.weekday() >= 5:
    print('WEEKEND')
    exit()

# NSE Holidays 2026 (update annually)
# Source: https://www.nseindia.com/regulations/listing-compliance/nse-market-timings-holidays
NSE_HOLIDAYS = [
    '2026-01-26',  # Republic Day
    '2026-02-17',  # Mahashivratri (tentative)
    '2026-03-10',  # Holi
    '2026-03-30',  # Id-ul-Fitr (tentative)
    '2026-04-02',  # Ram Navami
    '2026-04-06',  # Mahavir Jayanti
    '2026-04-14',  # Dr. Ambedkar Jayanti
    '2026-04-18',  # Good Friday
    '2026-05-01',  # Maharashtra Day
    '2026-06-06',  # Id-ul-Adha (Bakri Id) (tentative)
    '2026-07-06',  # Muharram (tentative)
    '2026-08-15',  # Independence Day
    '2026-08-17',  # Parsi New Year (tentative)
    '2026-09-04',  # Milad-un-Nabi (tentative)
    '2026-10-02',  # Mahatma Gandhi Jayanti
    '2026-10-20',  # Dussehra
    '2026-10-21',  # Dussehra (tentative)
    '2026-11-09',  # Diwali (Laxmi Puja)
    '2026-11-10',  # Diwali (Balipratipada)
    '2026-11-27',  # Guru Nanak Jayanti
    '2026-12-25',  # Christmas
]

today_str = now.strftime('%Y-%m-%d')
if today_str in NSE_HOLIDAYS:
    print('HOLIDAY')
else:
    print('TRADING_DAY')
" 2>/dev/null)

if [ "$TRADING_DAY" = "WEEKEND" ]; then
    echo "   📅 It's a weekend. No trading today."
    exit 0
elif [ "$TRADING_DAY" = "HOLIDAY" ]; then
    echo "   🎉 NSE holiday today. No trading."
    exit 0
else
    echo "   ✅ Trading day confirmed."
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 1: Auto-login via TOTP (with timeout guard)
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 STEP 1: Auto-login (TOTP — headless)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BOT_DIR"

# GUARD 5: Timeout on auto_login.py
timeout $LOGIN_TIMEOUT $PYTHON auto_login.py
LOGIN_EXIT=$?

if [ $LOGIN_EXIT -eq 124 ]; then
    echo ""
    echo "❌ Auto-login TIMED OUT after ${LOGIN_TIMEOUT}s (Zerodha may be down)"
    echo "   Exiting. Will retry on next cron run."
    exit 1
elif [ $LOGIN_EXIT -ne 0 ]; then
    echo ""
    echo "❌ Auto-login failed (exit code: $LOGIN_EXIT)"
    echo "   Falling back to browser-based login..."
    $PYTHON get_access_token.py
    if [ $? -ne 0 ]; then
        echo "❌ Both login methods failed. Exiting."
        exit 1
    fi
fi

# Point 2: Startup cooldown after login
# Zerodha sometimes has token propagation delay
echo ""
echo "   ⏳ Cooldown (2s for token propagation)..."
sleep 2
echo ""

# ──────────────────────────────────────────────────
# STEP 2: Verify token validity (Point 3)
# Actually hits kite.profile() — not just checking
# if token string exists.
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ STEP 2: Verifying token validity..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOKEN_CHECK=$($PYTHON -c "
import config
from kiteconnect import KiteConnect
try:
    kite = KiteConnect(api_key=config.API_KEY)
    kite.set_access_token(config.ACCESS_TOKEN)
    profile = kite.profile()
    print('SUCCESS:' + profile['user_name'])
except Exception as e:
    print('FAIL:' + str(e))
" 2>&1)

if [[ "$TOKEN_CHECK" == SUCCESS:* ]]; then
    USER_NAME="${TOKEN_CHECK#SUCCESS:}"
    echo "   ✅ Token is VALID! Connected as: $USER_NAME"
else
    ERROR="${TOKEN_CHECK#FAIL:}"
    echo "   ❌ Token is INVALID: $ERROR"
    echo "   Will retry on next cron run."
    exit 1
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 3: Start the bot
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 STEP 3: Starting the bot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# GUARD 6: Final check — make sure no bot snuck in during login
FINAL_CHECK=$(pgrep -f "python.*$BOT_DIR/main.py" 2>/dev/null)
if [ -n "$FINAL_CHECK" ]; then
    echo "   ⚠️  Bot appeared during login (PID: $FINAL_CHECK). Not starting another."
    exit 0
fi

# Fix log permissions if owned by root
for logfile in "$BOT_DIR/logs/bot.log" "$BOT_DIR/logs/bot-error.log"; do
    if [ -f "$logfile" ] && [ ! -w "$logfile" ]; then
        echo "   ⚠️  Fixing permissions on $(basename $logfile)..."
        sudo chown $(whoami):$(whoami) "$logfile" 2>/dev/null
    fi
done

# Start bot in background
nohup $PYTHON -u "$BOT_DIR/main.py" >> "$BOT_DIR/logs/bot.log" 2>> "$BOT_DIR/logs/bot-error.log" &
BOT_PID=$!
sleep 2

# Check if it's still running
if kill -0 $BOT_PID 2>/dev/null; then
    echo "   ✅ Bot started successfully! (PID: $BOT_PID)"
    echo ""
    echo "========================================================================"
    echo "🎉 ALL DONE! Bot is running."
    echo "========================================================================"
    echo ""
    echo "   📊 Watch live logs:  tail -f $BOT_DIR/logs/bot.log"
    echo "   🛑 Stop the bot:    kill $BOT_PID"
    echo "   📋 Check status:    ps aux | grep main.py"
    echo "   🐕 Watchdog:        $PYTHON $BOT_DIR/watchdog.py"
    echo ""
else
    echo "   ❌ Bot failed to start! Check logs:"
    echo "   tail -20 $BOT_DIR/logs/bot-error.log"
    exit 1
fi
