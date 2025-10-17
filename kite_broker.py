"""
Kite Connect broker interface for order placement and management
"""
from kiteconnect import KiteConnect
from datetime import datetime
import pytz
import config
from typing import Optional, Dict, List
import math

class KiteBroker:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.access_token = config.ACCESS_TOKEN
        self.kite = None
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initialize_kite()
    
    def initialize_kite(self):
        """Initialize Kite Connect"""
        try:
            if not self.api_key or not self.access_token:
                print("Warning: API credentials not configured. Running in simulation mode.")
                self.kite = None
                return
            
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            
            # Test connection
            profile = self.kite.profile()
            print(f"Connected to Kite as: {profile['user_name']}")
            
        except Exception as e:
            print(f"Error initializing Kite: {e}")
            self.kite = None
    
    def get_atm_strike(self, spot_price: float) -> int:
        """
        Get ATM strike price (rounded to nearest 50)
        """
        return round(spot_price / 50) * 50
    
    def get_option_symbol(self, strike: int, option_type: str, expiry_date: str) -> str:
        """
        Get the exact option symbol from Kite instruments
        This ensures we use the correct symbol format (especially for weekly expiries)
        """
        try:
            if self.kite:
                # Fetch instruments and find the matching option
                instruments = self.kite.instruments("NFO")
                target_expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                
                # Find exact match
                for inst in instruments:
                    inst_expiry = inst['expiry'].date() if hasattr(inst['expiry'], 'date') else inst['expiry']
                    
                    if (inst['name'] == config.OPTIONS_SYMBOL and
                        inst['strike'] == strike and
                        inst['instrument_type'] == option_type and
                        inst_expiry == target_expiry):
                        print(f"✅ Found symbol: {inst['tradingsymbol']} for {strike} {option_type} expiry {expiry_date}")
                        return inst['tradingsymbol']
            
            # Fallback: Generate symbol manually (may not work for weekly expiries)
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
            expiry_str = expiry_dt.strftime('%y%b').upper()
            symbol = f"{config.OPTIONS_SYMBOL}{expiry_str}{strike}{option_type}"
            print(f"⚠️ Using fallback symbol: {symbol}")
            return symbol
            
        except Exception as e:
            print(f"Error getting option symbol: {e}")
            # Final fallback
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
            expiry_str = expiry_dt.strftime('%y%b').upper()
            return f"{config.OPTIONS_SYMBOL}{expiry_str}{strike}{option_type}"
    
    def get_nearest_expiry(self) -> str:
        """
        Get nearest weekly expiry for Nifty options
        Nifty weekly expiries are on Mondays (as of 2024)
        Returns date in YYYY-MM-DD format
        """
        from datetime import timedelta
        
        try:
            if self.kite:
                # Get instruments for NFO
                instruments = self.kite.instruments("NFO")
                nifty_options = [i for i in instruments if i['name'] == config.OPTIONS_SYMBOL]
                
                if nifty_options:
                    # Get unique expiry dates and find the nearest one
                    expiries = sorted(list(set([i['expiry'].strftime('%Y-%m-%d') for i in nifty_options])))
                    today = datetime.now(self.ist).date()
                    
                    # Return the very first expiry date that is today or in future (nearest weekly)
                    for expiry in expiries:
                        expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                        if expiry_date >= today:
                            print(f"✅ Nearest Expiry: {expiry} ({expiry_date.strftime('%A')})")
                            return expiry
            
            # Fallback: Calculate next Monday (Nifty weekly expiry day)
            today = datetime.now(self.ist)
            days_ahead = (0 - today.weekday()) % 7  # Monday is 0
            if days_ahead == 0 and today.hour >= 15:  # If today is Monday after market close
                days_ahead = 7
            next_monday = today + timedelta(days=days_ahead)
            print(f"⚠️ Using fallback: Next Monday {next_monday.strftime('%Y-%m-%d')}")
            return next_monday.strftime('%Y-%m-%d')
            
        except Exception as e:
            print(f"Error getting nearest expiry: {e}")
            # Return next Monday as fallback (Nifty weekly expiry day)
            today = datetime.now(self.ist)
            days_ahead = (0 - today.weekday()) % 7
            if days_ahead == 0 and today.hour >= 15:
                days_ahead = 7
            next_monday = today + timedelta(days=days_ahead)
            print(f"⚠️ Fallback Monday: {next_monday.strftime('%Y-%m-%d')}")
            return next_monday.strftime('%Y-%m-%d')
    
    def get_option_ltp(self, symbol: str, exchange: str = "NFO") -> Optional[float]:
        """
        Get Last Traded Price for an option
        """
        try:
            if not self.kite:
                return None
            
            quote = self.kite.quote(f"{exchange}:{symbol}")
            ltp = quote[f"{exchange}:{symbol}"]['last_price']
            return ltp
            
        except Exception as e:
            print(f"Error getting LTP for {symbol}: {e}")
            return None
    
    def calculate_quantity(self, option_price: float, capital: float) -> int:
        """
        Calculate lot quantity based on available capital
        Nifty lot size is 75 (updated from 50)
        """
        LOT_SIZE = 75
        max_lots = 2  # Fixed to 2 lots only
        return max_lots * LOT_SIZE  # Returns 150
    
    def place_option_order(self, strike: int, option_type: str, 
                          order_type: str = "MARKET", quantity: int = 150) -> Optional[str]:
        """
        Place an option order
        order_type: MARKET or LIMIT
        Returns: order_id if successful, None otherwise
        """
        try:
            if not self.kite:
                print(f"[SIMULATION] Would place {option_type} order for strike {strike}, qty: {quantity}")
                return f"SIM_{datetime.now().timestamp()}"
            
            expiry = self.get_nearest_expiry()
            symbol = self.get_option_symbol(strike, option_type, expiry)
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_MARKET,
            )
            
            print(f"Order placed successfully. Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"Error placing order: {e}")
            return None
    
    def exit_position(self, strike: int, option_type: str, quantity: int = 150) -> Optional[str]:
        """
        Exit an option position
        """
        try:
            if not self.kite:
                print(f"[SIMULATION] Would exit {option_type} position for strike {strike}, qty: {quantity}")
                return f"SIM_EXIT_{datetime.now().timestamp()}"
            
            expiry = self.get_nearest_expiry()
            symbol = self.get_option_symbol(strike, option_type, expiry)
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_MARKET,
            )
            
            print(f"Exit order placed successfully. Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"Error placing exit order: {e}")
            return None
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get status of an order
        """
        try:
            if not self.kite or order_id.startswith("SIM"):
                return {"status": "COMPLETE", "average_price": 100.0}  # Simulation
            
            orders = self.kite.orders()
            for order in orders:
                if order['order_id'] == order_id:
                    return order
            return None
            
        except Exception as e:
            print(f"Error getting order status: {e}")
            return None
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions
        """
        try:
            if not self.kite:
                return []
            
            positions = self.kite.positions()
            return positions['day']  # Intraday positions
            
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []


if __name__ == "__main__":
    # Test the broker interface
    broker = KiteBroker()
    
    print("Testing Kite Broker...")
    print("-" * 50)
    
    # Test ATM calculation
    spot = 19500.50
    atm = broker.get_atm_strike(spot)
    print(f"Spot: {spot}, ATM Strike: {atm}")
    
    # Test expiry calculation
    expiry = broker.get_nearest_expiry()
    print(f"Nearest Expiry: {expiry}")
    
    # Test symbol generation
    symbol = broker.get_option_symbol(atm, "CE", expiry)
    print(f"Option Symbol: {symbol}")
