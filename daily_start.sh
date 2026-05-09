#!/bin/bash
#
# Daily Startup Script for Nifty 50 Breakout Trading Bot
#
# FULLY AUTOMATED — no browser, no manual login, no TOTP entry
# Runs entirely headless. Safe for cron jobs and VPS.
#
# Usage: cd /home/draxxy/Projects/Random/dayhigh-daylow && ./daily_start.sh
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

echo "========================================================================"
echo "🚀 NIFTY TRADING BOT — DAILY STARTUP (AUTOMATED)"
echo "   $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "========================================================================"
echo ""

# ══════════════════════════════════════════════════════════════
# GUARD 2: If bot is already running with a VALID token,
# don't kill it — just exit. Prevents cron from restarting
# a healthy bot mid-trade.
# ══════════════════════════════════════════════════════════════
BOT_PID=$(pgrep -f "python.*$BOT_DIR/main.py" 2>/dev/null)
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
        echo "   Killing it to refresh token..."
        kill -9 $BOT_PID 2>/dev/null
        sleep 1
        echo "   ✅ Bot stopped"
    fi
else
    echo "📍 Bot is not running (clean state)"
fi

# Clean stale PID lock
rm -f "$BOT_DIR/.bot.pid"
echo ""

# ──────────────────────────────────────────────────
# STEP 1: Auto-login via TOTP (with timeout guard)
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 STEP 1: Auto-login (TOTP — headless)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BOT_DIR"

# GUARD 3: Timeout on auto_login.py
# If Zerodha is down or login hangs, kill it after LOGIN_TIMEOUT seconds
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
echo ""

# ──────────────────────────────────────────────────
# STEP 2: Verify token validity
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

# GUARD 4: Final check — make sure no bot snuck in during login
FINAL_CHECK=$(pgrep -f "python.*$BOT_DIR/main.py" 2>/dev/null)
if [ -n "$FINAL_CHECK" ]; then
    echo "   ⚠️  Bot appeared during login (PID: $FINAL_CHECK). Not starting another."
    exit 0
fi

# Ensure log directory exists with correct permissions
mkdir -p "$BOT_DIR/logs"
for logfile in "$BOT_DIR/logs/bot.log" "$BOT_DIR/logs/bot-error.log"; do
    if [ -f "$logfile" ] && [ ! -w "$logfile" ]; then
        echo "   ⚠️  Fixing permissions on $(basename $logfile)..."
        sudo chown $(whoami):$(whoami) "$logfile" 2>/dev/null
    fi
done

# Start bot in background with nohup
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
    echo ""
else
    echo "   ❌ Bot failed to start! Check logs:"
    echo "   tail -20 $BOT_DIR/logs/bot-error.log"
    exit 1
fi
