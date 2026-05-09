# Nifty 50 Breakout Trading Bot

Automated options trading bot for NSE Nifty 50 using Zerodha Kite Connect API. Trades breakouts of the previous day's high/low with dynamic risk management.

## Strategy

- **Entry**: Buy CE when Nifty breaks above previous day's high, PE when it breaks below previous day's low
- **Risk**: VIX-based dynamic Stop Loss and Target (SL = VIX × 1.0, Target = VIX × 4.0)
- **Exit**: Trailing stop-loss with step-based ratchet locks, auto-squareoff at 15:15 IST
- **Limit**: 1 trade per day, ATM weekly expiry options

## Architecture

```
daily_start.sh          # Automated startup (TOTP login → verify → launch)
├── auto_login.py       # Headless Zerodha login via TOTP
├── main.py             # Main loop (heartbeat, monitoring, EOD)
│   ├── trade_manager.py  # Entry/exit logic, TSL, state persistence
│   ├── kite_broker.py    # Order placement, verification, reconciliation
│   ├── data_fetcher.py   # Zerodha API: prices, VIX, historical data
│   └── notifier.py       # Telegram alerts (fire-and-forget)
└── config.py           # All settings from .env
watchdog.py             # Heartbeat monitor (detects silent hangs)
```

## Quick Setup

```bash
# Clone
git clone https://github.com/Rishabh9306/day-high--day-low.git
cd day-high--day-low

# Python environment
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env with your Kite API credentials
```

## Configuration (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `API_KEY` | Kite Connect API key | `abc123` |
| `API_SECRET` | Kite Connect API secret | `xyz789` |
| `CAPITAL_PER_TRADE` | Capital allocated per trade (₹) | `24000` |
| `MAX_LOTS` | Maximum lots per trade | `2` |
| `STRIKE_OFFSET` | OTM offset (0 = ATM) | `0` |
| `ENABLE_TRAILING_SL` | Enable trailing stop-loss | `true` |
| `KITE_USER_ID` | Zerodha client ID | `AB1234` |
| `KITE_PASSWORD` | Zerodha password | `pass` |
| `TOTP_SECRET` | TOTP seed for auto-login | `BASE32KEY` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) | `123:ABC` |
| `TELEGRAM_CHAT_ID` | Telegram chat ID (optional) | `12345` |

## Auto-Login (TOTP)

No manual browser login needed. The bot generates access tokens automatically:

```bash
# Setup: Enable External TOTP in Zerodha
# Kite → My Profile → Password & Security → External TOTP
# Save the TOTP secret key to .env as TOTP_SECRET

# Test auto-login
.venv/bin/python auto_login.py
```

## Running

### Manual start
```bash
./daily_start.sh
```

### Fully automated (cron)
```bash
crontab -e

# Daily startup at 8:55 AM (Mon-Fri)
55 8 * * 1-5 cd /path/to/bot && /bin/bash daily_start.sh >> logs/startup.log 2>&1

# Watchdog every 5 min during market hours
*/5 9-15 * * 1-5 cd /path/to/bot && .venv/bin/python watchdog.py >> logs/watchdog.log 2>&1
```

## Safety Features

| Feature | Description |
|---------|-------------|
| **Circuit Breaker** | Stops after 3 consecutive order rejections |
| **Breakout Flag** | Set on detection (not fill) — prevents retry loops |
| **PID Lock** | Only one bot instance can run at a time |
| **Heartbeat** | Main loop writes `.heartbeat` every iteration |
| **Watchdog** | Detects hung processes, auto-restarts, Telegram alert |
| **flock Guard** | Prevents duplicate startup scripts |
| **Holiday Calendar** | NSE 2026 holidays — skips non-trading days |
| **Login Timeout** | 30s timeout on auto-login prevents hangs |
| **Log Rotation** | Rotates at 5MB, deletes after 7 days |
| **Position Reconciliation** | Verifies position with Zerodha every loop |
| **EOD Square-off** | Auto-exits all positions at 15:15 IST |

## VPS Deployment

Recommended: AWS Lightsail Mumbai (ap-south-1), 1GB RAM, 1 vCPU.

1. Clone repo on VPS
2. Setup `.venv` and install requirements
3. Copy `.env` via SCP
4. Whitelist VPS static IP on [Kite Developer Console](https://developers.kite.trade)
5. Setup cron jobs (above)
6. Verify: `./daily_start.sh`

## Commands

```bash
# Check bot status
ps aux | grep main.py | grep -v grep

# Stop bot
kill $(pgrep -f "main.py")

# Watch logs
tail -f logs/bot.log

# Health check
.venv/bin/python watchdog.py
```

## License

Private — not for redistribution.
