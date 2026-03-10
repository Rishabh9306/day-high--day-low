"""
Data fetcher for Nifty 50 prices using ZERODHA KITE CONNECT API ONLY
All data fetched from Zerodha - NO Yahoo Finance
"""
from datetime import datetime, timedelta
import pytz
from typing import Tuple, Optional, List, Dict
import config
from kiteconnect import KiteConnect

class DataFetcher:
    def __init__(self, kite: Optional[KiteConnect] = None):
        """
        Initialize with Kite Connect instance
        If no kite instance provided, will create one
        """
        self.ist = pytz.timezone('Asia/Kolkata')
        
        if kite:
            self.kite = kite
        else:
            # Initialize own kite instance
            if config.API_KEY and config.ACCESS_TOKEN:
                self.kite = KiteConnect(api_key=config.API_KEY)
                self.kite.set_access_token(config.ACCESS_TOKEN)
            else:
                self.kite = None
                print("⚠️  No Kite credentials - running in simulation mode")
    
    def get_previous_day_high_low(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch previous trading day's high and low for Nifty 50 from ZERODHA
        Uses historical candle data API
        Returns: (previous_high, previous_low)
        """
        try:
            if not self.kite:
                print("⚠️  Simulation mode: Using fallback data")
                return 26000.0, 25800.0
            
            # Get last 10 days of daily candles
            to_date = datetime.now(self.ist)
            from_date = to_date - timedelta(days=10)
            
            # Fetch historical data from Zerodha
            historical_data = self.kite.historical_data(
                instrument_token=config.NIFTY_INDEX_TOKEN,
                from_date=from_date,
                to_date=to_date,
                interval="day"
            )
            
            if not historical_data or len(historical_data) < 2:
                print("Error: Not enough historical data from Zerodha")
                return None, None
            
            # Get today's date
            today = datetime.now(self.ist).date()
            
            # Filter to get only previous completed trading days
            previous_days = sorted(
                [candle for candle in historical_data if candle['date'].date() < today],
                key=lambda c: c['date']
            )
            
            if not previous_days:
                print("Error: No previous trading day data")
                return None, None
            
            # Get most recent completed trading day
            previous_day = previous_days[-1]
            prev_high = round(previous_day['high'], 2)
            prev_low = round(previous_day['low'], 2)
            prev_date = previous_day['date'].date()
            
            print(f"✅ Zerodha: Previous Day ({prev_date}): High: {prev_high}, Low: {prev_low}")
            return prev_high, prev_low
            
        except Exception as e:
            print(f"Error fetching previous day data from Zerodha: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current price of Nifty 50 from ZERODHA
        Uses quote API for real-time data
        Returns: current_price
        """
        try:
            if not self.kite:
                print("⚠️  Simulation mode: Using fallback price")
                return 26000.0
            
            # Get real-time quote from Zerodha
            quote = self.kite.quote(["NSE:NIFTY 50"])
            
            if not quote or "NSE:NIFTY 50" not in quote:
                print("Error: No current price data from Zerodha")
                return None
            
            current_price = round(quote["NSE:NIFTY 50"]['last_price'], 2)
            return current_price
            
        except Exception as e:
            print(f"Error fetching current price from Zerodha: {e}")
            return None
    
    def get_today_high_low(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get today's high and low from ZERODHA
        Uses quote API which includes OHLC data
        Returns: (today_high, today_low)
        """
        try:
            if not self.kite:
                return 26100.0, 25900.0
            
            # Get quote with OHLC data
            quote = self.kite.quote(["NSE:NIFTY 50"])
            
            if not quote or "NSE:NIFTY 50" not in quote:
                return None, None
            
            ohlc = quote["NSE:NIFTY 50"]['ohlc']
            today_high = round(ohlc['high'], 2)
            today_low = round(ohlc['low'], 2)
            
            return today_high, today_low
            
        except Exception as e:
            print(f"Error fetching today's high/low from Zerodha: {e}")
            return None, None
    
    def get_india_vix(self) -> Optional[float]:
        """
        Get current India VIX value from ZERODHA
        Uses quote API for India VIX index
        Returns: vix_value (as percentage, e.g., 11.30 for 11.30%)
        """
        try:
            if not self.kite:
                print("⚠️  Simulation mode: Using fallback VIX")
                return 11.0
            
            # Get India VIX quote from Zerodha
            vix_quote = self.kite.quote([f"NSE:INDIA VIX"])
            
            if not vix_quote or "NSE:INDIA VIX" not in vix_quote:
                print("Error: No India VIX data from Zerodha")
                return None
            
            vix_value = round(vix_quote["NSE:INDIA VIX"]['last_price'], 2)
            print(f"✅ Zerodha India VIX: {vix_value}%")
            return vix_value
            
        except Exception as e:
            print(f"Error fetching India VIX from Zerodha: {e}")
            return None
    
    def get_batch_quotes(self, symbols: List[str]) -> Dict:
        """
        Get quotes for multiple instruments in single API call
        Uses Zerodha's batch quote capability (up to 1000 instruments)
        """
        try:
            if not self.kite:
                return {}
            
            quotes = self.kite.quote(symbols)
            return quotes
            
        except Exception as e:
            print(f"Error fetching batch quotes: {e}")
            return {}
    
    def get_option_chain_quotes(self, atm_strike: int, option_type: str, 
                               expiry_date: str, strikes_range: int = 3) -> Dict:
        """
        Get quotes for multiple strikes around ATM (option chain view)
        Fetches ATM ± strikes_range in single API call
        """
        try:
            if not self.kite:
                return {}
            
            # Generate symbols for multiple strikes
            symbols = []
            for i in range(-strikes_range, strikes_range + 1):
                strike = atm_strike + (i * 50)  # Nifty strikes are in 50s
                
                # Format: NIFTY25OCT26000CE
                expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                expiry_str = expiry_dt.strftime('%y%b').upper()
                symbol = f"NFO:{config.OPTIONS_SYMBOL}{expiry_str}{strike}{option_type}"
                symbols.append(symbol)
            
            # Fetch all quotes in single API call
            quotes = self.kite.quote(symbols)
            return quotes
            
        except Exception as e:
            print(f"Error fetching option chain quotes: {e}")
            return {}


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = DataFetcher()
    
    print("Testing Data Fetcher (Zerodha API)...")
    print("-" * 50)
    
    prev_high, prev_low = fetcher.get_previous_day_high_low()
    print(f"Previous Day - High: {prev_high}, Low: {prev_low}")
    
    current_price = fetcher.get_current_price()
    print(f"Current Price: {current_price}")
    
    today_high, today_low = fetcher.get_today_high_low()
    print(f"Today - High: {today_high}, Low: {today_low}")
    
    vix = fetcher.get_india_vix()
    if vix:
        print(f"\nIndia VIX: {vix}%")
        print(f"Dynamic Stop Loss: {int(vix)}%")
        print(f"Dynamic Target: {int(vix * 3)}%")

