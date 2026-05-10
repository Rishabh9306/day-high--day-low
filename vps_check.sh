#!/bin/bash
#
# VPS Health Check — run after setup to verify everything works
# Usage: cd ~/niftybot && bash vps_check.sh
#

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$BOT_DIR/.venv/bin/python"
PASS=0
FAIL=0

check() {
    if [ $? -eq 0 ]; then
        echo "  ✅ $1"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $1"
        FAIL=$((FAIL + 1))
    fi
}

echo "════════════════════════════════════════════════════════"
echo "   VPS HEALTH CHECK — $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "════════════════════════════════════════════════════════"
echo ""

# 1. System
echo "━━━ 1. SYSTEM ━━━"
python3 --version > /dev/null 2>&1; check "Python3 installed ($(python3 --version 2>&1))"
test -f "$PYTHON"; check ".venv exists at $BOT_DIR/.venv"
chronyc tracking 2>/dev/null | grep -q "Normal"; check "Clock sync (chrony) — critical for TOTP"
ufw status 2>/dev/null | grep -q "active"; check "Firewall (ufw) active"
echo ""

# 2. Files
echo "━━━ 2. FILES ━━━"
test -f "$BOT_DIR/.env"; check ".env exists"
test -f "$BOT_DIR/main.py"; check "main.py exists"
test -f "$BOT_DIR/auto_login.py"; check "auto_login.py exists"
test -f "$BOT_DIR/watchdog.py"; check "watchdog.py exists"
test -f "$BOT_DIR/daily_start.sh"; check "daily_start.sh exists"
test -x "$BOT_DIR/daily_start.sh"; check "daily_start.sh is executable"
echo ""

# 3. Dependencies
echo "━━━ 3. DEPENDENCIES ━━━"
$PYTHON -c "from kiteconnect import KiteConnect" 2>/dev/null; check "kiteconnect installed"
$PYTHON -c "import pyotp" 2>/dev/null; check "pyotp installed"
$PYTHON -c "import pytz" 2>/dev/null; check "pytz installed"
$PYTHON -c "from dotenv import load_dotenv" 2>/dev/null; check "python-dotenv installed"
$PYTHON -c "import requests" 2>/dev/null; check "requests installed"
$PYTHON -c "import pandas" 2>/dev/null; check "pandas installed"
echo ""

# 4. Config
echo "━━━ 4. CONFIGURATION ━━━"
cd "$BOT_DIR"
$PYTHON -c "
import config
from dotenv import load_dotenv
import os
load_dotenv()
assert config.API_KEY, 'API_KEY empty'
assert config.API_SECRET, 'API_SECRET empty'
assert os.getenv('KITE_USER_ID'), 'KITE_USER_ID empty'
assert os.getenv('KITE_PASSWORD'), 'KITE_PASSWORD empty'
assert os.getenv('TOTP_SECRET'), 'TOTP_SECRET empty'
print(f'MAX_LOTS={config.MAX_LOTS}, CAPITAL={config.CAPITAL_PER_TRADE}, LOT_SIZE={config.NIFTY_LOT_SIZE}')
" 2>/dev/null; check "All .env credentials present"
echo ""

# 5. Auto-login (TOTP)
echo "━━━ 5. AUTO-LOGIN TEST ━━━"
cd "$BOT_DIR"
$PYTHON auto_login.py 2>&1
LOGIN_OK=$?
[ $LOGIN_OK -eq 0 ]; check "Auto-login (TOTP) succeeded"
echo ""

# 6. Token verification
echo "━━━ 6. TOKEN VERIFICATION ━━━"
cd "$BOT_DIR"
TOKEN_RESULT=$($PYTHON -c "
import config
from kiteconnect import KiteConnect
try:
    kite = KiteConnect(api_key=config.API_KEY)
    kite.set_access_token(config.ACCESS_TOKEN)
    p = kite.profile()
    print(f'Connected as: {p[\"user_name\"]}')
except Exception as e:
    print(f'FAIL: {e}')
    exit(1)
" 2>&1)
echo "  $TOKEN_RESULT"
echo "$TOKEN_RESULT" | grep -q "Connected as"; check "Token is valid (kite.profile() works)"
echo ""

# 7. Network latency
echo "━━━ 7. NETWORK ━━━"
LATENCY=$(ping -c 3 kite.zerodha.com 2>/dev/null | tail -1 | awk -F'/' '{print $5}')
echo "  📡 Avg latency to Zerodha: ${LATENCY:-N/A}ms"
[ -n "$LATENCY" ]; check "Zerodha reachable"
echo ""

# 8. Cron jobs
echo "━━━ 8. CRON JOBS ━━━"
CRON_STARTUP=$(crontab -l 2>/dev/null | grep "daily_start")
CRON_WATCHDOG=$(crontab -l 2>/dev/null | grep "watchdog")
[ -n "$CRON_STARTUP" ]; check "Startup cron set: $CRON_STARTUP"
[ -n "$CRON_WATCHDOG" ]; check "Watchdog cron set: $CRON_WATCHDOG"
echo ""

# 9. Telegram test
echo "━━━ 9. TELEGRAM ━━━"
cd "$BOT_DIR"
$PYTHON -c "
import config
if config.ENABLE_TELEGRAM:
    import notifier
    notifier.send_telegram('🤖 VPS Health Check — all systems operational!')
    print('Telegram notification sent')
else:
    print('Telegram not configured (optional)')
" 2>&1
check "Telegram test"
echo ""

# 10. Disk space
echo "━━━ 10. RESOURCES ━━━"
echo "  💾 Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " used (" $5 ")"}')"
echo "  🧠 RAM:  $(free -h | grep Mem | awk '{print $3 "/" $2 " used"}')"
echo ""

# Summary
echo "════════════════════════════════════════════════════════"
echo "   RESULT: $PASS passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "   🎉 VPS IS READY FOR PRODUCTION!"
else
    echo "   ⚠️  Fix the failed checks above."
fi
echo "════════════════════════════════════════════════════════"
