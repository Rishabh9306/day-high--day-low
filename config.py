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
STOP_LOSS_PERCENT = 10  # 10% from entry (initial fixed SL)
TARGET_PERCENT = 20     # 20% from entry

# Trailing Stop Loss Parameters
TRAILING_SL_ENABLED = True  # Enable trailing stop loss feature
TRAILING_ACTIVATION_PERCENT = 20  # Activate trailing SL after 20% profit
TRAILING_SL_PERCENT = 10  # Trail by 10% from High Water Mark

# Trading Configuration
CAPITAL_PER_TRADE = int(os.getenv('CAPITAL_PER_TRADE', 50000))
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY', 2))

# Trading Hours (IST)
TRADING_START_HOUR = 9
TRADING_START_MINUTE = 15
TRADING_END_HOUR = 15
TRADING_END_MINUTE = 15

# Monitoring Interval
CHECK_INTERVAL_SECONDS = 30  # Check every 30 seconds

# Logging
LOG_FILE = "trading.log"
TRADE_HISTORY_FILE = "trade_history.json"
