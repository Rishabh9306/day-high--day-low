"""
Data fetcher for Nifty 50 prices using Yahoo Finance
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Tuple, Optional
import config

class DataFetcher:
    def __init__(self):
        self.yahoo_symbol = config.YAHOO_SYMBOL
        self.ist = pytz.timezone('Asia/Kolkata')
    
    def get_previous_day_high_low(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch previous trading day's high and low for Nifty 50
        Returns: (previous_high, previous_low)
        """
        try:
            # Get data for last 10 days to ensure we have enough data
            end_date = datetime.now(self.ist)
            start_date = end_date - timedelta(days=10)
            
            # Fetch data from Yahoo Finance
            ticker = yf.Ticker(self.yahoo_symbol)
            df = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if df.empty or len(df) < 2:
                print("Error: Not enough historical data available")
                return None, None
            
            # Get today's date in IST
            today = datetime.now(self.ist).date()
            
            # Filter out today's data if it exists (intraday partial data)
            df.index = df.index.tz_localize(None)  # Remove timezone for comparison
            df_filtered = df[df.index.date < today]
            
            if df_filtered.empty:
                print("Error: No previous trading day data available")
                return None, None
            
            # Get the most recent completed trading day (yesterday or last trading day)
            previous_day = df_filtered.iloc[-1]
            prev_high = round(previous_day['High'], 2)
            prev_low = round(previous_day['Low'], 2)
            prev_date = df_filtered.index[-1].date()
            
            print(f"Previous Trading Day ({prev_date}): High: {prev_high}, Low: {prev_low}")
            return prev_high, prev_low
            
        except Exception as e:
            print(f"Error fetching previous day data: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def get_current_price(self) -> Optional[float]:
        """
        Get current price of Nifty 50
        Returns: current_price
        """
        try:
            ticker = yf.Ticker(self.yahoo_symbol)
            
            # Get real-time data
            data = ticker.history(period='1d', interval='1m')
            
            if data.empty:
                print("Error: No current price data available")
                return None
            
            current_price = round(data['Close'].iloc[-1], 2)
            return current_price
            
        except Exception as e:
            print(f"Error fetching current price: {e}")
            return None
    
    def get_today_high_low(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get today's high and low so far
        Returns: (today_high, today_low)
        """
        try:
            ticker = yf.Ticker(self.yahoo_symbol)
            data = ticker.history(period='1d', interval='1m')
            
            if data.empty:
                return None, None
            
            today_high = round(data['High'].max(), 2)
            today_low = round(data['Low'].min(), 2)
            
            return today_high, today_low
            
        except Exception as e:
            print(f"Error fetching today's high/low: {e}")
            return None, None


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = DataFetcher()
    
    print("Testing Data Fetcher...")
    print("-" * 50)
    
    prev_high, prev_low = fetcher.get_previous_day_high_low()
    print(f"Previous Day - High: {prev_high}, Low: {prev_low}")
    
    current_price = fetcher.get_current_price()
    print(f"Current Price: {current_price}")
    
    today_high, today_low = fetcher.get_today_high_low()
    print(f"Today - High: {today_high}, Low: {today_low}")
