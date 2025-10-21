#!/bin/bash
# Daily token refresh script
# Add this to crontab: 0 8 * * 1-5 /home/draxxy/dayhigh-daylow/refresh_token_daily.sh

set -e

LOG_FILE="/home/draxxy/dayhigh-daylow/logs/token-refresh.log"
cd /home/draxxy/dayhigh-daylow

echo "=====================================================================" >> "$LOG_FILE"
echo "$(date): Starting daily token refresh" >> "$LOG_FILE"
echo "=====================================================================" >> "$LOG_FILE"

# Check if it's a weekday (Monday-Friday)
DAY=$(date +%u)
if [ "$DAY" -gt 5 ]; then
    echo "$(date): Weekend - skipping token refresh" >> "$LOG_FILE"
    exit 0
fi

# Stop the bot
echo "$(date): Stopping trading bot..." >> "$LOG_FILE"
sudo systemctl stop nifty-trading-bot 2>> "$LOG_FILE" || true

# Wait a moment
sleep 5

# Generate new token (requires manual login in browser)
echo "$(date): ⚠️  Manual action required - open browser to generate token" >> "$LOG_FILE"
echo "$(date): Run this manually: cd /home/draxxy/dayhigh-daylow && .venv/bin/python get_access_token.py" >> "$LOG_FILE"

# Note: Automatic token generation requires manual browser login
# You need to run get_access_token.py manually each day

echo "$(date): Token refresh script completed (manual step required)" >> "$LOG_FILE"
echo "=====================================================================" >> "$LOG_FILE"
