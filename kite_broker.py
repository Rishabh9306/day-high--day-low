"""
Kite Connect broker interface for order placement and management
"""
from kiteconnect import KiteConnect
from datetime import datetime
import pytz
import config
from typing import Optional, Dict, List
import math
import time

class KiteBroker:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET
        self.access_token = config.ACCESS_TOKEN
        self.kite = None
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Cache for instruments - refresh once per day
        self.instruments_cache = None
        self.instruments_cache_time = None
        
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
    
    def get_atm_strike(self, spot_price: float, option_type: str = None) -> int:
        """
        Get strike price based on spot price and STRIKE_OFFSET from config.
        
        If STRIKE_OFFSET = 0   → ATM (nearest 50)
        If STRIKE_OFFSET = 1000 → OTM by 1000 pts
            CE: ATM + 1000 (higher strike = cheaper call = more aggressive)
            PE: ATM - 1000 (lower strike = cheaper put = more aggressive)
        """
        atm = round(spot_price / 50) * 50
        
        if config.STRIKE_OFFSET and option_type:
            if option_type == "CE":
                strike = atm + config.STRIKE_OFFSET
            else:  # PE
                strike = atm - config.STRIKE_OFFSET
            # Round to nearest 50 (in case offset isn't a multiple of 50)
            strike = round(strike / 50) * 50
            print(f"🎯 Strike: ATM {atm} → OTM {strike} ({option_type}, offset: {config.STRIKE_OFFSET})")
            return strike
        
        return atm
    
    def get_instruments(self, exchange: str = "NFO") -> List[Dict]:
        """
        Get instruments list with caching (refreshes once per day at 8:30 AM)
        This saves ~1440 API calls per day
        """
        try:
            now = datetime.now(self.ist)
            
            # Check if cache exists and is fresh (same day, after 8:30 AM)
            if self.instruments_cache is not None and self.instruments_cache_time is not None:
                cache_date = self.instruments_cache_time.date()
                today = now.date()
                
                # Use cache if it's from today and after 8:30 AM
                if cache_date == today and now.hour >= 8:
                    return self.instruments_cache
            
            # Fetch fresh data
            if self.kite:
                print(f"📥 Fetching fresh instruments data for {exchange}...")
                self.instruments_cache = self.kite.instruments(exchange)
                self.instruments_cache_time = now
                print(f"✅ Cached {len(self.instruments_cache)} instruments at {now.strftime('%H:%M:%S')}")
                return self.instruments_cache
            else:
                return []
                
        except Exception as e:
            print(f"Error fetching instruments: {e}")
            # Return cached data if available, even if stale
            if self.instruments_cache is not None:
                print("⚠️ Using stale cache due to error")
                return self.instruments_cache
            return []
    
    def get_option_symbol(self, strike: int, option_type: str, expiry_date: str) -> str:
        """
        Get the exact option symbol from Kite instruments
        This ensures we use the correct symbol format (especially for weekly expiries)
        """
        try:
            if self.kite:
                # Fetch instruments using cached method
                instruments = self.get_instruments("NFO")
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
                # Get instruments for NFO using cached method
                instruments = self.get_instruments("NFO")
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
        Returns the fixed quantity from config.QUANTITY.
        LOT SIZE IS CONTROLLED EXCLUSIVELY BY config.py (NIFTY_LOT_SIZE × MAX_LOTS).
        No local calculation — change config.MAX_LOTS or .env MAX_LOTS to adjust.
        """
        cost = option_price * config.QUANTITY if option_price else 0
        print(f"💰 Qty: {config.QUANTITY} ({config.MAX_LOTS} lot × {config.NIFTY_LOT_SIZE}), "
              f"Option: ₹{option_price:.2f}, Cost: ₹{cost:.0f}")
        return config.QUANTITY
    
    def _round_to_tick(self, price: float, tick_size: float = 0.05) -> float:
        """Round price to valid tick size for NFO options"""
        return round(round(price / tick_size) * tick_size, 2)

    def place_option_order(self, strike: int, option_type: str, 
                          order_type: str = "LIMIT", quantity: int = None) -> Optional[str]:
        """
        Place an option BUY order using LIMIT with a 2% buffer above LTP
        to simulate market-like instant fill (Zerodha blocks raw MARKET via API).
        Returns: order_id if successful, None otherwise
        """
        try:
            quantity = quantity or config.QUANTITY  # Always use config unless explicitly overridden
            if not self.kite:
                print(f"[SIMULATION] Would place {option_type} order for strike {strike}, qty: {quantity}")
                return f"SIM_{datetime.now().timestamp()}"
            
            expiry = self.get_nearest_expiry()
            symbol = self.get_option_symbol(strike, option_type, expiry)
            
            # Get LTP and set limit price 2% above for guaranteed fill
            ltp = self.get_option_ltp(symbol)
            if not ltp or ltp <= 0:
                print(f"❌ Cannot get LTP for {symbol}, aborting order")
                return None
            
            limit_price = self._round_to_tick(ltp * 1.02)  # 2% buffer above LTP
            print(f"📋 LIMIT BUY: LTP=₹{ltp:.2f}, Limit=₹{limit_price:.2f} (+2% buffer)")
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_LIMIT,
                price=limit_price,
            )
            
            print(f"✅ Order placed successfully. Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"Error placing order: {e}")
            return None
    
    def verify_order_fill(self, order_id: str, max_attempts: int = 5) -> Optional[Dict]:
        """
        Verify order fill and get actual average price
        Polls order history up to max_attempts times with 200ms gap
        Returns: dict with average_price, filled_quantity, status
        """
        try:
            if not self.kite or order_id.startswith("SIM"):
                return {
                    "order_id": order_id,
                    "status": "COMPLETE",
                    "average_price": 100.0,
                    "filled_quantity": config.QUANTITY
                }
            
            order_history = None
            latest = None

            for attempt in range(max_attempts):
                time.sleep(0.2)  # 200ms between checks
                
                # Get order history
                order_history = self.kite.order_history(order_id)
                
                if not order_history:
                    continue
                
                # Get latest status
                latest = order_history[-1]
                
                print(f"📊 Order {order_id} Status: {latest['status']} (attempt {attempt + 1}/{max_attempts})")
                
                if latest['status'] == 'COMPLETE':
                    return {
                        "order_id": order_id,
                        "status": "COMPLETE",
                        "average_price": latest['average_price'],
                        "filled_quantity": latest['filled_quantity'],
                        "tradingsymbol": latest['tradingsymbol']
                    }
                elif latest['status'] in ['REJECTED', 'CANCELLED']:
                    print(f"❌ Order {latest['status']}: {latest.get('status_message', 'Unknown error')}")
                    return {
                        "order_id": order_id,
                        "status": latest['status'],
                        "average_price": None,
                        "filled_quantity": 0,
                        "error": latest.get('status_message', 'Unknown error')
                    }
            
            # If not filled within max_attempts
            print(f"⚠️ Order still pending after {max_attempts} attempts")
            return {
                "order_id": order_id,
                "status": latest['status'] if latest else "UNKNOWN",
                "average_price": None,
                "filled_quantity": latest.get('filled_quantity', 0) if latest else 0
            }
            
        except Exception as e:
            print(f"Error verifying order fill: {e}")
            return None
    
    def place_option_order_verified(self, strike: int, option_type: str, quantity: int = None) -> Optional[Dict]:
        """
        Place order and verify actual fill price
        Returns: dict with order_id, average_price, filled_quantity, status
        """
        # Get fresh quote before placing order
        expiry = self.get_nearest_expiry()
        symbol = self.get_option_symbol(strike, option_type, expiry)
        
        ltp_before = self.get_option_ltp(symbol)
        print(f"📈 Pre-order LTP: ₹{ltp_before}")
        
        # Wait 500ms and get fresh quote again
        time.sleep(0.5)
        ltp_fresh = self.get_option_ltp(symbol)
        
        if ltp_before and ltp_fresh:
            diff_pct = abs(ltp_fresh - ltp_before) / ltp_before * 100
            if diff_pct > 2:
                print(f"⚠️ Price moved {diff_pct:.2f}% - using latest LTP: ₹{ltp_fresh}")
        
        # Place order
        order_id = self.place_option_order(strike, option_type, quantity=quantity or config.QUANTITY)
        
        if not order_id:
            return None
        
        # Verify fill and get actual price
        result = self.verify_order_fill(order_id)
        
        if result and result['status'] == 'COMPLETE':
            print(f"✅ Order FILLED at ₹{result['average_price']} (Quote was ₹{ltp_fresh or ltp_before})")
            if ltp_fresh and result['average_price']:
                diff = abs(result['average_price'] - ltp_fresh)
                if diff > 1:
                    print(f"⚠️ Fill price differs by ₹{diff:.2f} from quote")
        
        return result
    
    def exit_position(self, strike: int, option_type: str, quantity: int = None) -> Optional[str]:
        """
        Exit an option position using LIMIT order 2% below LTP
        to simulate market-like instant fill.
        Returns order_id if order was placed, None on failure.
        NOTE: Use exit_position_verified() to confirm the fill.
        """
        try:
            quantity = quantity or config.QUANTITY  # Always use config unless explicitly overridden
            if not self.kite:
                print(f"[SIMULATION] Would exit {option_type} position for strike {strike}, qty: {quantity}")
                return f"SIM_EXIT_{datetime.now().timestamp()}"
            
            expiry = self.get_nearest_expiry()
            symbol = self.get_option_symbol(strike, option_type, expiry)
            
            # Get LTP and set limit price 2% below for guaranteed fill
            ltp = self.get_option_ltp(symbol)
            if not ltp or ltp <= 0:
                print(f"❌ Cannot get LTP for {symbol} to exit, attempting with ₹0.05 (minimum)")
                limit_price = 0.05
            else:
                limit_price = self._round_to_tick(ltp * 0.98)  # 2% buffer below LTP
                limit_price = max(limit_price, 0.05)  # Ensure minimum valid price
            
            print(f"📋 LIMIT SELL: LTP=₹{ltp:.2f}, Limit=₹{limit_price:.2f} (-2% buffer)")
            
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,  # Intraday
                order_type=self.kite.ORDER_TYPE_LIMIT,
                price=limit_price,
            )
            
            print(f"✅ Exit order placed successfully. Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"Error placing exit order: {e}")
            return None

    def exit_position_verified(self, strike: int, option_type: str,
                               quantity: int = None, max_attempts: int = 10) -> Optional[Dict]:
        """
        Place exit order and verify it was actually FILLED.
        Returns dict with status/average_price/filled_quantity, or None on failure.
        Mirrors place_option_order_verified() used for entries.
        """
        if not self.kite:
            quantity = quantity or config.QUANTITY
            print(f"[SIMULATION] Would exit {option_type} strike {strike}, qty: {quantity}")
            return {
                "order_id": f"SIM_EXIT_{datetime.now().timestamp()}",
                "status": "COMPLETE",
                "average_price": 0.0,
                "filled_quantity": quantity,
            }

        order_id = self.exit_position(strike, option_type, quantity)
        if not order_id:
            print("❌ Exit order placement returned no order_id — position may still be open!")
            return None

        result = self.verify_order_fill(order_id, max_attempts=max_attempts)
        if result and result['status'] == 'COMPLETE':
            print(f"✅ Exit order FILLED at ₹{result.get('average_price', 'N/A')}")
        elif result:
            print(f"⚠️ Exit order status: {result['status']} — position may not be closed!")
        else:
            print("❌ Exit order fill verification failed — position status unknown!")
        return result
    
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
    
    def reconcile_position(self, expected_symbol: str) -> Optional[Dict]:
        """
        Reconcile position with Zerodha to get actual entry price
        Returns: dict with actual_entry, quantity, pnl, last_price or None
        """
        try:
            if not self.kite:
                return None
            
            positions = self.kite.positions()
            
            # Check net positions
            for pos in positions.get('net', []):
                if pos['tradingsymbol'] == expected_symbol and pos['quantity'] != 0:
                    return {
                        'tradingsymbol': pos['tradingsymbol'],
                        'actual_entry': pos['average_price'],
                        'quantity': pos['quantity'],
                        'pnl': pos['pnl'],
                        'last_price': pos['last_price'],
                        'buy_price': pos.get('buy_price', 0),
                        'buy_quantity': pos.get('buy_quantity', 0)
                    }
            
            return None
            
        except Exception as e:
            print(f"Error reconciling position: {e}")
            return None
    
    def get_all_orders(self) -> List[Dict]:
        """
        AGGRESSIVE MONITORING: Get all orders for the day
        Call every 5 seconds to track order flow
        """
        try:
            if not self.kite:
                return []
            
            orders = self.kite.orders()
            return orders
            
        except Exception as e:
            print(f"Error getting all orders: {e}")
            return []
    
    def get_all_trades(self) -> List[Dict]:
        """
        AGGRESSIVE MONITORING: Get all executed trades
        Call every minute to analyze execution quality
        """
        try:
            if not self.kite:
                return []
            
            trades = self.kite.trades()
            return trades
            
        except Exception as e:
            print(f"Error getting trades: {e}")
            return []
    
    def get_margins(self) -> Dict:
        """
        AGGRESSIVE MONITORING: Check available margins
        Call before every order and every 10s during trading
        """
        try:
            if not self.kite:
                return {}
            
            margins = self.kite.margins()
            return margins
            
        except Exception as e:
            print(f"Error getting margins: {e}")
            return {}
    
    def get_batch_option_quotes(self, atm_strike: int, option_type: str, 
                                expiry_date: str, strikes_range: int = 3) -> Dict:
        """
        BATCH QUOTE FETCHING: Get multiple strikes in single API call
        Fetches ATM ± strikes_range (7 strikes total for range=3)
        """
        try:
            if not self.kite:
                return {}
            
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
            expiry_str = expiry_dt.strftime('%y%b').upper()
            
            # Generate symbols for multiple strikes
            symbols = []
            for i in range(-strikes_range, strikes_range + 1):
                strike = atm_strike + (i * 50)  # Nifty strikes are in 50s
                symbol = f"NFO:{config.OPTIONS_SYMBOL}{expiry_str}{strike}{option_type}"
                symbols.append(symbol)
            
            # Fetch all quotes in SINGLE API call
            quotes = self.kite.quote(symbols)
            return quotes
            
        except Exception as e:
            print(f"Error fetching batch quotes: {e}")
            return {}
    
    def analyze_order_book(self, orders: List[Dict]) -> Dict:
        """
        Analyze order book for insights
        """
        analysis = {
            'total_orders': len(orders),
            'pending': 0,
            'complete': 0,
            'rejected': 0,
            'cancelled': 0,
            'open': 0
        }
        
        for order in orders:
            status = order['status']
            if 'PENDING' in status:
                analysis['pending'] += 1
            elif status == 'COMPLETE':
                analysis['complete'] += 1
            elif status == 'REJECTED':
                analysis['rejected'] += 1
            elif status == 'CANCELLED':
                analysis['cancelled'] += 1
            elif status == 'OPEN':
                analysis['open'] += 1
        
        return analysis
    
    def analyze_trade_execution(self, trades: List[Dict]) -> Dict:
        """
        Analyze trade execution quality
        """
        if not trades:
            return {}

        total_quantity = sum(t['quantity'] for t in trades)
        avg_price = (
            sum(t['average_price'] * t['quantity'] for t in trades) / total_quantity
            if total_quantity > 0 else 0
        )

        analysis = {
            'total_trades': len(trades),
            'total_quantity': total_quantity,
            'avg_price': avg_price,
            'trades': trades
        }

        return analysis


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
    
    # Test batch quotes
    quotes = broker.get_batch_option_quotes(26000, "CE", expiry, strikes_range=2)
    print(f"\nBatch Quotes: {len(quotes)} strikes fetched")
