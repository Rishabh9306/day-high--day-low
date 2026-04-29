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
VIX_SL_MULTIPLIER = 1.0   # SL = VIX * 1.0 (i.e., if VIX = 11.3%, SL = 11.3%)
VIX_TARGET_MULTIPLIER = 3.0  # Target = VIX * 3.0 (i.e., if VIX = 11.3%, Target = 33.9%)
INDIA_VIX_TOKEN = 264969  # India VIX instrument token for Zerodha

# Trailing Stop Loss Configuration
# When profit crosses a threshold, SL ratchets up to the lock level.
# SL NEVER moves down. 'EXIT' as lock means force-exit the trade immediately.
# Format: (profit_threshold_%, sl_lock_% or 'EXIT')
# MUST be sorted ascending by threshold.
ENABLE_TRAILING_SL = True
TRAILING_SL_STEPS = [
    (9,  0),        # At +9% profit  → move SL to break-even (0%)
    (18, 6),        # At +18% profit → lock in +6%
    (30, 15),       # At +30% profit → lock in +15%
    (42, 25),       # At +42% profit → lock in +25%
    (54, 'EXIT'),   # At +54% profit → EXIT immediately (hard target)
]

# ══════════════════════════════════════════════════════════════════════
# LOT SIZE CONFIGURATION — SINGLE SOURCE OF TRUTH
# Change ONLY here. Every order in the system uses these values.
# ══════════════════════════════════════════════════════════════════════
NIFTY_LOT_SIZE = 65                                          # Nifty lot size (exchange-defined)
MAX_LOTS = int(os.getenv('MAX_LOTS', 1))                     # Max lots per trade — DEFAULT 1
QUANTITY = NIFTY_LOT_SIZE * MAX_LOTS                         # Final order quantity — DO NOT OVERRIDE
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
