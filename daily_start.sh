#!/bin/bash
#
# Daily Startup Script for Nifty 50 Breakout Trading Bot
#
# FULLY AUTOMATED — no browser, no manual login, no TOTP entry
# Runs entirely headless. Safe for cron jobs and VPS.
#
# Usage: cd /home/draxxy/Projects/Random/dayhigh-daylow && ./daily_start.sh
# Cron:  55 8 * * 1-5 /home/draxxy/Projects/Random/dayhigh-daylow/daily_start.sh >> /home/draxxy/Projects/Random/dayhigh-daylow/logs/startup.log 2>&1
#

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$BOT_DIR/.venv/bin/python"

echo "========================================================================"
echo "🚀 NIFTY TRADING BOT — DAILY STARTUP (AUTOMATED)"
echo "   $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "========================================================================"
echo ""

# ──────────────────────────────────────────────────
# STEP 1: Kill any running bot instances
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 STEP 1: Checking bot status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BOT_PID=$(pgrep -f "python.*$BOT_DIR/main.py" 2>/dev/null)
if [ -n "$BOT_PID" ]; then
    echo "   ⚠️  Bot is currently RUNNING (PID: $BOT_PID)"
    echo "   Stopping it before token refresh..."
    kill -9 $BOT_PID 2>/dev/null
    sleep 1
    echo "   ✅ Bot stopped"
else
    echo "   ✅ Bot is not running (clean state)"
fi

# Clean stale PID lock
rm -f "$BOT_DIR/.bot.pid"
echo ""

# ──────────────────────────────────────────────────
# STEP 2: Auto-login via TOTP (no browser needed)
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 STEP 2: Auto-login (TOTP — headless)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BOT_DIR"
$PYTHON auto_login.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Auto-login failed!"
    echo "   Falling back to browser-based login..."
    $PYTHON get_access_token.py
    if [ $? -ne 0 ]; then
        echo "❌ Both login methods failed. Exiting."
        exit 1
    fi
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 3: Verify token validity
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ STEP 3: Verifying token validity..."
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
    echo ""
    echo "   Please run manually: $PYTHON get_access_token.py"
    exit 1
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 4: Start the bot
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 STEP 4: Starting the bot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

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
