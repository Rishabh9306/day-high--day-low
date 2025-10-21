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
YAHOO_SYMBOL = "^NSEI"  # Nifty 50 symbol on Yahoo Finance
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

# Trading Configuration
CAPITAL_PER_TRADE = int(os.getenv('CAPITAL_PER_TRADE', 50000))
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY', 2))

# Trading Hours (IST)
TRADING_START_HOUR = 9
TRADING_START_MINUTE = 15
TRADING_END_HOUR = 15
TRADING_END_MINUTE = 15

# Monitoring Interval
CHECK_INTERVAL_SECONDS = 10  # Check every 10 seconds

# Logging
LOG_FILE = "trading.log"
TRADE_HISTORY_FILE = "trade_history.json"
