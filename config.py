"""
Configuration file for trading parameters
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Kite Connect API Configuration
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')

# Trading Parameters
SYMBOL = "NIFTY 50"
NIFTY_SYMBOL = "NIFTY 50"  # For Zerodha API
NIFTY_INDEX_TOKEN = 256265  # Nifty 50 instrument token for Zerodha
INDEX_SYMBOL = "NIFTY 50"
OPTIONS_SYMBOL = "NIFTY"

# Entry/Exit Parameters
# USE_VIX_BASED_TARGETS: If True, SL and Target are calculated dynamically based on India VIX
# If False, uses fixed percentages below
USE_VIX_BASED_TARGETS = True

# Fixed percentages (used only if USE_VIX_BASED_TARGETS = False)
STOP_LOSS_PERCENT = 10  # 10% from entry
TARGET_PERCENT = 20     # 20% from entry

# VIX-based calculation (used only if USE_VIX_BASED_TARGETS = True)
VIX_SL_MULTIPLIER = 1.0   # SL = VIX * 1.0 (i.e., if VIX = 18.4%, SL = 18.4%)
VIX_TARGET_MULTIPLIER = 4.0  # Target = VIX * 4.0 (i.e., if VIX = 18.4%, Target = 73.6%)
INDIA_VIX_TOKEN = 264969  # India VIX instrument token for Zerodha

# Trailing Stop Loss Configuration
# When profit crosses a threshold, SL ratchets up to the lock level.
# SL NEVER moves down. 'EXIT' as lock means force-exit the trade immediately.
# Format: (profit_threshold_%, sl_lock_% or 'EXIT')
# MUST be sorted ascending by threshold.
ENABLE_TRAILING_SL = os.getenv('ENABLE_TRAILING_SL', 'true').lower() == 'true'
TRAILING_SL_STEPS = [
    (15, 0),     # +15% → Break-even (ATM options need room to breathe)
    (25, 10),    # +25% → Lock +10%
    (35, 20),    # +35% → Lock +20%
    (45, 30),    # +45% → Lock +30%
    (55, 42),    # +55% → Lock +42%
    (65, 'EXIT') # +65% → Hard exit
]
TSL_COOLDOWN_SECONDS = int(os.getenv('TSL_COOLDOWN_SECONDS', 60))  # Wait 60s after entry before TSL activates

# ══════════════════════════════════════════════════════════════════════
# LOT SIZE CONFIGURATION — SINGLE SOURCE OF TRUTH
# Change ONLY here. Every order in the system uses these values.
# ══════════════════════════════════════════════════════════════════════
NIFTY_LOT_SIZE = 65                                          # Nifty lot size (exchange-defined)
MAX_LOTS = int(os.getenv('MAX_LOTS', 1))                     # Max lots per trade — DEFAULT 1
QUANTITY = NIFTY_LOT_SIZE * MAX_LOTS                         # Final order quantity — DO NOT OVERRIDE
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# STRIKE OFFSET — OTM AGGRESSIVENESS
# 0    = ATM (At The Money) — spot 24000 → strike 24000
# 1000 = 1000 pts OTM      — spot 24000 → CE 25000 / PE 23000
# ══════════════════════════════════════════════════════════════════════
STRIKE_OFFSET = int(os.getenv('STRIKE_OFFSET', 0))
# ══════════════════════════════════════════════════════════════════════

# Trading Configuration
CAPITAL_PER_TRADE = int(os.getenv('CAPITAL_PER_TRADE', 50000))
MAX_TRADES_PER_DAY = 1  # Only 1 trade allowed per day

# Telegram Notifications (optional — leave blank to disable)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENABLE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# Trading Hours (IST)
TRADING_START_HOUR = 9
TRADING_START_MINUTE = 15
TRADING_END_HOUR = 15
TRADING_END_MINUTE = 15

# Aggressive API Usage - TRUE 100% Zerodha Rate Limit Usage
CHECK_INTERVAL_IDLE = 1          # Check every 1s when idle (Quote API: 1/sec = 100%)
CHECK_INTERVAL_IN_POSITION = 0.1 # Check every 100ms when in position (10/sec)
# RECONCILE_INTERVAL removed - now reconciles EVERY loop (10 times/sec = 100% of Positions API)
ORDER_BOOK_CHECK_INTERVAL = 5    # Check all orders every 5s (conservative)
TRADE_ANALYSIS_INTERVAL = 60     # Analyze trades every 60s (conservative)
MARGIN_CHECK_INTERVAL = 10       # Check margins every 10s (conservative)

# Batch Quote Settings
FETCH_STRIKES_RANGE = 3          # Fetch ATM ±3 strikes (7 total) in single call

# Logging
LOG_FILE = "trading.log"
TRADE_HISTORY_FILE = "trade_history.json"
