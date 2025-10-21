# Running the Bot as a System Service

This guide explains how to run the Nifty 50 Trading Bot continuously as a system service that automatically starts on boot.

## Quick Start

### 1. Install the Service

```bash
cd /home/draxxy/dayhigh-daylow
./install_service.sh
```

This will:
- ✅ Create logs directory
- ✅ Install systemd service file
- ✅ Enable auto-start on boot
- ✅ Configure automatic restarts on failure

### 2. Generate Access Token (Required Daily)

**⚠️ IMPORTANT:** Kite Connect access tokens expire every day. You must regenerate the token before market open (before 9:15 AM).

```bash
cd /home/draxxy/dayhigh-daylow
.venv/bin/python get_access_token.py
```

- Opens browser for Kite login
- Automatically saves new token to `.env`
- Takes ~30 seconds

### 3. Start the Service

```bash
sudo systemctl start nifty-trading-bot
```

### 4. Check Status

```bash
sudo systemctl status nifty-trading-bot
```

---

## Service Management Commands

### Start the Bot
```bash
sudo systemctl start nifty-trading-bot
```

### Stop the Bot
```bash
sudo systemctl stop nifty-trading-bot
```

### Restart the Bot
```bash
sudo systemctl restart nifty-trading-bot
```

### Check Status
```bash
sudo systemctl status nifty-trading-bot
```

### Enable Auto-Start on Boot
```bash
sudo systemctl enable nifty-trading-bot
```

### Disable Auto-Start
```bash
sudo systemctl disable nifty-trading-bot
```

---

## Viewing Logs

### Live Logs (Follow Mode)
```bash
sudo journalctl -u nifty-trading-bot -f
```

### Last 100 Lines
```bash
sudo journalctl -u nifty-trading-bot -n 100
```

### Today's Logs
```bash
sudo journalctl -u nifty-trading-bot --since today
```

### Log Files
```bash
# Standard output
tail -f /home/draxxy/dayhigh-daylow/logs/bot.log

# Error output
tail -f /home/draxxy/dayhigh-daylow/logs/bot-error.log
```

---

## Daily Token Refresh Workflow

### Option 1: Manual (Recommended)

Every trading day before 9:15 AM:

```bash
# 1. Stop the bot
sudo systemctl stop nifty-trading-bot

# 2. Generate new token
cd /home/draxxy/dayhigh-daylow
.venv/bin/python get_access_token.py

# 3. Start the bot
sudo systemctl start nifty-trading-bot
```

### Option 2: Semi-Automated with Cron

Set up a cron job to remind you:

```bash
crontab -e
```

Add this line (runs at 8:00 AM on weekdays):
```cron
0 8 * * 1-5 /usr/bin/notify-send "Trading Bot" "Generate Kite token: cd /home/draxxy/dayhigh-daylow && .venv/bin/python get_access_token.py"
```

### Option 3: Quick Restart Script

Create an alias in `~/.zshrc`:

```bash
alias refresh-bot='cd /home/draxxy/dayhigh-daylow && sudo systemctl stop nifty-trading-bot && .venv/bin/python get_access_token.py && sudo systemctl start nifty-trading-bot'
```

Then just run:
```bash
refresh-bot
```

---

## Troubleshooting

### Bot Not Starting

**Check Status:**
```bash
sudo systemctl status nifty-trading-bot
```

**Check Logs:**
```bash
sudo journalctl -u nifty-trading-bot -n 50
```

**Common Issues:**
1. **Expired Token**: Generate new token with `get_access_token.py`
2. **Python Environment**: Verify venv at `/home/draxxy/dayhigh-daylow/.venv`
3. **Permissions**: Ensure logs directory exists and is writable

### Bot Crashes

The service is configured to **automatically restart** after 10 seconds if it crashes.

Check crash logs:
```bash
cat /home/draxxy/dayhigh-daylow/logs/bot-error.log
```

### Token Expired Error

```bash
# Stop bot
sudo systemctl stop nifty-trading-bot

# Generate new token
cd /home/draxxy/dayhigh-daylow
.venv/bin/python get_access_token.py

# Start bot
sudo systemctl start nifty-trading-bot
```

### View Real-time Market Data

```bash
# Monitor bot activity
tail -f /home/draxxy/dayhigh-daylow/logs/bot.log | grep -E "Current Nifty|ENTRY|EXIT"
```

---

## Uninstalling the Service

```bash
# Stop and disable
sudo systemctl stop nifty-trading-bot
sudo systemctl disable nifty-trading-bot

# Remove service file
sudo rm /etc/systemd/system/nifty-trading-bot.service

# Reload systemd
sudo systemctl daemon-reload
```

---

## Service Configuration

**Service File Location:**
```
/etc/systemd/system/nifty-trading-bot.service
```

**Key Features:**
- ✅ Auto-start on system boot
- ✅ Auto-restart on crash (every 10 seconds)
- ✅ Runs under user `draxxy`
- ✅ Logs to both systemd journal and files
- ✅ Waits for network before starting

**Edit Service:**
```bash
sudo nano /etc/systemd/system/nifty-trading-bot.service
sudo systemctl daemon-reload
sudo systemctl restart nifty-trading-bot
```

---

## Best Practices

### Daily Checklist (Before Market Open)

1. ☑️ Generate new Kite access token (before 9:15 AM)
2. ☑️ Check bot is running: `sudo systemctl status nifty-trading-bot`
3. ☑️ Verify current VIX: Check logs or run test
4. ☑️ Clear old state files if needed: `rm trade_state.json`

### Weekly Maintenance

1. Review logs: `ls -lh /home/draxxy/dayhigh-daylow/logs/`
2. Archive old logs: `mv bot.log bot-$(date +%Y%m%d).log`
3. Check trade history: `cat trade_history.json | jq`

### Monthly Review

1. Analyze performance: Check win rate, P&L
2. Update bot code: `git pull`
3. Backup trade history
4. Review and adjust VIX multipliers if needed

---

## Monitoring Tips

### Create Dashboard Alias

Add to `~/.zshrc`:

```bash
alias bot-status='echo "=== Service Status ===" && sudo systemctl status nifty-trading-bot && echo && echo "=== Recent Logs ===" && sudo journalctl -u nifty-trading-bot -n 10 --no-pager'
```

### Watch Bot Live

```bash
watch -n 10 'sudo journalctl -u nifty-trading-bot -n 20 --no-pager'
```

### Check if Bot is Trading

```bash
ps aux | grep main.py
curl -s localhost:8000/status  # If you add a status endpoint later
```

---

## Security Considerations

1. **Secrets**: Never commit `.env` file
2. **Logs**: Rotate logs regularly (contain sensitive data)
3. **Permissions**: Service runs as your user (`draxxy`)
4. **Token Storage**: Access tokens saved in `.env` (0600 permissions)

---

## System Requirements

- **OS**: Linux (Ubuntu/Debian/Fedora)
- **Systemd**: Version 230+
- **Python**: 3.8+
- **Permissions**: Sudo access for service management
- **Network**: Stable internet connection

---

## FAQ

**Q: Will the bot survive system reboot?**  
A: Yes, it auto-starts on boot. But you must generate new Kite token after reboot if it's a new day.

**Q: What happens on weekends?**  
A: The bot detects weekends and sleeps. No trading happens.

**Q: Can I run multiple bots?**  
A: Yes, but you need to create separate service files and use different working directories.

**Q: How do I update the bot code?**  
A: 
```bash
cd /home/draxxy/dayhigh-daylow
git pull
sudo systemctl restart nifty-trading-bot
```

**Q: Where is trading data stored?**  
A: 
- State: `trade_state.json`
- History: `trade_history.json`
- Logs: `logs/` directory

---

## Quick Reference Card

```bash
# Daily Morning Routine (before 9:15 AM)
cd /home/draxxy/dayhigh-daylow
sudo systemctl stop nifty-trading-bot
.venv/bin/python get_access_token.py
sudo systemctl start nifty-trading-bot

# Check if running
sudo systemctl status nifty-trading-bot

# Watch live logs
sudo journalctl -u nifty-trading-bot -f

# Emergency stop
sudo systemctl stop nifty-trading-bot
```

---

**Status**: ✅ Service configured and ready  
**Auto-start**: Enabled on boot  
**Restart Policy**: Always restart on failure  
**Last Updated**: October 21, 2025
