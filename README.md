# Nifty 50 Breakout Trading Bot

An automated intraday trading system that trades Nifty 50 options based on previous day's high/low breakouts.

## Strategy Overview

**Objective**: Trade breakouts based on the previous day's range

### Entry Conditions
- **Buy CE (Call Option)**: When current price crosses **above** yesterday's high
- **Buy PE (Put Option)**: When current price crosses **below** yesterday's low

### Exit Conditions
- **Stop Loss**: Dynamic (VIX-based) or Fixed percentage
- **Target**: Dynamic (VIX-based) or Fixed percentage
- **EOD Square Off**: All positions squared off at 3:15 PM

#### Risk Management Modes

**VIX-Based (Default):**
- Stop Loss = India VIX × 1.0 (e.g., VIX 11.3% → SL 11.3%)
- Target = India VIX × 3.0 (e.g., VIX 11.3% → Target 33.9%)
- Automatically adapts to market volatility
- See [VIX_TRADING.md](VIX_TRADING.md) for details

**Fixed Percentages:**
- Stop Loss: 10% from entry
- Target: 20% from entry
- Set `USE_VIX_BASED_TARGETS = False` in `config.py`

### Key Features
- ✅ Intraday trading only (MIS)
- ✅ ATM (At The Money) options trading
- ✅ Uses Kite Connect for order placement
- ✅ Uses Yahoo Finance for real-time prices
- ✅ Automatic position monitoring
- ✅ Risk management with SL and Target
- ✅ Trade logging and history
- ✅ Graceful error handling

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher
- Zerodha Kite Connect account
- Active internet connection

### 2. Installation

```bash
# Clone or navigate to the project directory
cd dayhigh-daylow

# Install required packages
pip install -r requirements.txt
```

### 3. Configuration

1. **Copy the example environment file**:
```bash
cp .env.example .env
```

2. **Edit `.env` file with your credentials**:
```env
# Kite Connect API Credentials
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
ACCESS_TOKEN=your_access_token_here

# Trading Configuration
CAPITAL_PER_TRADE=50000
MAX_TRADES_PER_DAY=1
```

### 4. Getting Kite Connect Credentials

1. **Sign up for Kite Connect**: https://kite.trade/
2. **Create an app** to get API Key and API Secret
3. **Generate Access Token**:
   - You need to generate access token daily OR
   - Implement the login flow (see Kite Connect documentation)

### 5. Running the Bot

```bash
# Test individual components first
python data_fetcher.py    # Test data fetching
python kite_broker.py     # Test broker connection
python trade_manager.py   # Test trade logic

# Run the main bot
python main.py
```

## File Structure

```
dayhigh-daylow/
├── main.py                 # Main trading bot entry point
├── config.py              # Configuration settings
├── data_fetcher.py        # Yahoo Finance data fetching
├── kite_broker.py         # Kite Connect broker interface
├── trade_manager.py       # Trade logic and position management
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
├── .env.example          # Example environment file
├── README.md             # This file
├── trade_state.json      # Trade state (auto-generated)
└── trade_history.json    # Trade history log (auto-generated)
```

## Configuration Parameters

Edit `config.py` to customize:

- **STOP_LOSS_PERCENT**: Default 20%
- **TARGET_PERCENT**: Default 40%
- **CAPITAL_PER_TRADE**: Capital allocated per trade
- **MAX_TRADES_PER_DAY**: Maximum trades per day (default: 1)
- **CHECK_INTERVAL_SECONDS**: How often to check prices (default: 30s)
- **TRADING_START_HOUR/MINUTE**: Market open time (9:15 AM)
- **TRADING_END_HOUR/MINUTE**: Market close time (3:15 PM)

## How It Works

1. **Pre-Market** (Before 9:15 AM):
   - Fetches previous day's high and low from Yahoo Finance
   - Initializes trading parameters

2. **During Market Hours** (9:15 AM - 3:15 PM):
   - Monitors Nifty 50 current price every 30 seconds
   - Detects breakout above previous high → Enters CE (Call)
   - Detects breakout below previous low → Enters PE (Put)
   - Monitors positions for Stop Loss or Target hit
   - Maximum 2 trades per day (1 CE + 1 PE)

3. **End of Day** (3:15 PM):
   - Automatically squares off all open positions
   - Saves trade history

## Safety Features

- ✅ Only trades during market hours (9:15 AM - 3:15 PM)
- ✅ Automatic position square-off at 3:15 PM
- ✅ Maximum trades per day limit
- ✅ Stop loss protection (20%)
- ✅ State persistence (recovers from crashes)
- ✅ Comprehensive logging
- ✅ Simulation mode if API credentials not configured

## Monitoring and Logs

### Trade State
- **trade_state.json**: Current trade state (positions, SL, target)

### Trade History
- **trade_history.json**: Complete history of all trades with entry/exit details

### Console Output
The bot provides real-time status updates:
- Current time and market status
- Previous day high/low
- Current Nifty price
- Active positions
- Stop loss and target levels
- Trades taken today

## Troubleshooting

### Issue: "API credentials not configured"
**Solution**: Make sure `.env` file exists with valid API_KEY and ACCESS_TOKEN

### Issue: "Error fetching data from Yahoo Finance"
**Solution**: Check internet connection. Yahoo Finance may have temporary issues.

### Issue: "Order placement failed"
**Solution**: 
- Verify Kite Connect credentials
- Check if you have sufficient margin
- Ensure market is open

### Issue: Bot not detecting breakouts
**Solution**:
- Check if previous day data was fetched correctly
- Verify current price is being fetched
- Check console logs for errors

## Testing

### Test Mode (Simulation)
If you don't configure API credentials, the bot runs in simulation mode:
- Fetches real market data
- Simulates order placement
- Logs all actions without real trades

### Test Individual Components
```bash
# Test data fetching
python data_fetcher.py

# Test broker interface
python kite_broker.py

# Test trade logic
python trade_manager.py
```

## Risk Disclaimer

⚠️ **IMPORTANT**: 
- This is an automated trading system that involves real money
- Options trading involves substantial risk and is not suitable for everyone
- Past performance does not guarantee future results
- Always test thoroughly in paper trading first
- Use proper position sizing and risk management
- Monitor the bot regularly
- The developers are not responsible for any trading losses

## Support

For issues or questions:
1. Check the console logs for error messages
2. Review the trade_history.json for trade details
3. Test individual components to isolate issues

## License

This project is for educational purposes. Use at your own risk.
