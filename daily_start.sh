#!/bin/bash
#
# Daily Startup Script for Nifty 50 Breakout Trading Bot
#
# Run this every morning before market opens (before 9:15 AM IST)
# Usage: cd /home/draxxy/Projects/Random/dayhigh-daylow && ./daily_start.sh
#

BOT_DIR="/home/draxxy/Projects/Random/dayhigh-daylow"
PYTHON="$BOT_DIR/.venv/bin/python"

echo "========================================================================"
echo "🚀 NIFTY TRADING BOT — DAILY STARTUP"
echo "   $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "========================================================================"
echo ""

# ──────────────────────────────────────────────────
# STEP 1: Check bot status
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 STEP 1: Checking bot status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BOT_PID=$(pgrep -f "python.*$BOT_DIR/main.py" 2>/dev/null)
if [ -n "$BOT_PID" ]; then
    echo "⚠️  Bot is currently RUNNING (PID: $BOT_PID)"
    echo "   Stopping it before token refresh..."
    kill -9 $BOT_PID 2>/dev/null
    sleep 1
    echo "   ✅ Bot stopped"
else
    echo "   ✅ Bot is not running (clean state)"
fi

# Note: Removed 'sudo systemctl stop nifty-trading-bot' — running via sudo
# was causing log files to become root-owned, leading to permission denied errors.
echo ""

# ──────────────────────────────────────────────────
# STEP 2: Generate new access token
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 STEP 2: Generate new access token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   Starting token generator..."
echo "   Please login to Kite when the browser opens."
echo ""

cd "$BOT_DIR"
$PYTHON get_access_token.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Token generation failed!"
    echo "   Please run manually: $PYTHON get_access_token.py"
    exit 1
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 3: Check and display IP for whitelisting
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 STEP 3: Check IP for whitelisting"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

$PYTHON check_ip.py --no-browser
echo ""

read -p "   Have you updated IPs on Kite developer console? (y/n): " ip_updated
if [ "$ip_updated" != "y" ]; then
    echo ""
    echo "⚠️  Please update IPs first!"
    echo "   Open: https://developers.kite.trade"
    echo "   Then re-run this script."
    exit 1
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 4: Verify token validity
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ STEP 4: Verifying token validity..."
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
    echo "   Please re-run: $PYTHON get_access_token.py"
    exit 1
fi
echo ""

# ──────────────────────────────────────────────────
# STEP 5: Start the bot
# ──────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 STEP 5: Starting the bot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Fix log file permissions if they got owned by root (from previous sudo runs)
mkdir -p "$BOT_DIR/logs"
for logfile in "$BOT_DIR/logs/bot.log" "$BOT_DIR/logs/bot-error.log"; do
    if [ -f "$logfile" ] && [ ! -w "$logfile" ]; then
        echo "   ⚠️  Fixing permissions on $(basename $logfile)..."
        sudo chown $(whoami):$(whoami) "$logfile"
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
