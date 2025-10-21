"""
Trade Manager - Handles trade logic, entry, exit, and position management
"""
from datetime import datetime
import pytz
import json
import os
from typing import Optional, Dict
import config
from data_fetcher import DataFetcher
from kite_broker import KiteBroker

class TradeManager:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.broker = KiteBroker()
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Trade state
        self.prev_high = None
        self.prev_low = None
        self.current_position = None  # 'CE' or 'PE' or None
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        self.order_id = None
        self.strike = None
        self.quantity = None
        self.trades_today = 0
        
        # Flags
        self.high_breakout_triggered = False
        self.low_breakout_triggered = False
        
        self.load_state()
    
    def load_state(self):
        """Load trade state from file if exists"""
        try:
            if os.path.exists('trade_state.json'):
                with open('trade_state.json', 'r') as f:
                    state = json.load(f)
                    
                    # Check if state is from today
                    state_date = state.get('date')
                    today = datetime.now(self.ist).strftime('%Y-%m-%d')
                    
                    if state_date == today:
                        self.prev_high = state.get('prev_high')
                        self.prev_low = state.get('prev_low')
                        self.current_position = state.get('current_position')
                        self.entry_price = state.get('entry_price')
                        self.stop_loss = state.get('stop_loss')
                        self.target = state.get('target')
                        self.order_id = state.get('order_id')
                        self.strike = state.get('strike')
                        self.quantity = state.get('quantity')
                        self.trades_today = state.get('trades_today', 0)
                        self.high_breakout_triggered = state.get('high_breakout_triggered', False)
                        self.low_breakout_triggered = state.get('low_breakout_triggered', False)
                        print("Loaded existing trade state")
        except Exception as e:
            print(f"Error loading state: {e}")
    
    def save_state(self):
        """Save current trade state"""
        try:
            state = {
                'date': datetime.now(self.ist).strftime('%Y-%m-%d'),
                'prev_high': self.prev_high,
                'prev_low': self.prev_low,
                'current_position': self.current_position,
                'entry_price': self.entry_price,
                'stop_loss': self.stop_loss,
                'target': self.target,
                'order_id': self.order_id,
                'strike': self.strike,
                'quantity': self.quantity,
                'trades_today': self.trades_today,
                'high_breakout_triggered': self.high_breakout_triggered,
                'low_breakout_triggered': self.low_breakout_triggered,
            }
            
            with open('trade_state.json', 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def log_trade(self, action: str, details: Dict):
        """Log trade to history file"""
        try:
            log_entry = {
                'timestamp': datetime.now(self.ist).isoformat(),
                'action': action,
                'details': details
            }
            
            history = []
            if os.path.exists(config.TRADE_HISTORY_FILE):
                with open(config.TRADE_HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            
            history.append(log_entry)
            
            with open(config.TRADE_HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            print(f"Error logging trade: {e}")
    
    def initialize_day(self):
        """Initialize trading day with previous day's high/low"""
        print("\n" + "="*60)
        print("Initializing Trading Day")
        print("="*60)
        
        self.prev_high, self.prev_low = self.data_fetcher.get_previous_day_high_low()
        
        if self.prev_high and self.prev_low:
            print(f"Previous Day High: {self.prev_high}")
            print(f"Previous Day Low: {self.prev_low}")
            self.save_state()
            return True
        else:
            print("Failed to fetch previous day data")
            return False
    
    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        now = datetime.now(self.ist)
        start_time = now.replace(hour=config.TRADING_START_HOUR, 
                                 minute=config.TRADING_START_MINUTE, second=0)
        end_time = now.replace(hour=config.TRADING_END_HOUR, 
                               minute=config.TRADING_END_MINUTE, second=0)
        
        return start_time <= now <= end_time
    
    def can_take_new_trade(self) -> bool:
        """Check if new trade can be taken"""
        return (self.current_position is None and 
                self.trades_today < config.MAX_TRADES_PER_DAY)
    
    def enter_trade(self, option_type: str, spot_price: float):
        """
        Enter a trade (CE or PE)
        """
        if not self.can_take_new_trade():
            print("Cannot take new trade: Already in position or max trades reached")
            return
        
        print(f"\n{'='*60}")
        print(f"ENTERING {option_type} TRADE")
        print(f"{'='*60}")
        
        # Get ATM strike
        self.strike = self.broker.get_atm_strike(spot_price)
        print(f"Spot Price: {spot_price}")
        print(f"ATM Strike: {self.strike}")
        
        # Get option price
        expiry = self.broker.get_nearest_expiry()
        symbol = self.broker.get_option_symbol(self.strike, option_type, expiry)
        option_price = self.broker.get_option_ltp(symbol)
        
        if not option_price:
            # Simulation fallback
            option_price = spot_price * 0.02  # Assume 2% of spot as option premium
            print(f"[SIMULATION] Using estimated option price: {option_price}")
        
        # Calculate quantity
        self.quantity = self.broker.calculate_quantity(option_price, config.CAPITAL_PER_TRADE)
        print(f"Option Price: {option_price}")
        print(f"Quantity: {self.quantity}")
        
        # Calculate SL and Target (VIX-based or fixed)
        if config.USE_VIX_BASED_TARGETS:
            vix = self.data_fetcher.get_india_vix()
            if vix:
                sl_percent = int(vix * config.VIX_SL_MULTIPLIER)
                target_percent = int(vix * config.VIX_TARGET_MULTIPLIER)
                print(f"India VIX: {vix}% → SL: {sl_percent}%, Target: {target_percent}%")
            else:
                # Fallback to fixed if VIX fetch fails
                print("⚠️  VIX fetch failed, using fixed percentages")
                sl_percent = config.STOP_LOSS_PERCENT
                target_percent = config.TARGET_PERCENT
        else:
            sl_percent = config.STOP_LOSS_PERCENT
            target_percent = config.TARGET_PERCENT
        
        # Place order
        self.order_id = self.broker.place_option_order(self.strike, option_type, 
                                                        quantity=self.quantity)
        
        if self.order_id:
            self.current_position = option_type
            self.entry_price = option_price
            self.stop_loss = option_price * (1 - sl_percent / 100)
            self.target = option_price * (1 + target_percent / 100)
            self.trades_today += 1
            
            if option_type == "CE":
                self.high_breakout_triggered = True
            else:
                self.low_breakout_triggered = True
            
            print(f"Entry Price: {self.entry_price}")
            print(f"Stop Loss: {self.stop_loss:.2f} (-{sl_percent}%)")
            print(f"Target: {self.target:.2f} (+{target_percent}%)")
            print(f"Order ID: {self.order_id}")
            
            self.save_state()
            self.log_trade("ENTRY", {
                'option_type': option_type,
                'strike': self.strike,
                'spot_price': spot_price,
                'entry_price': self.entry_price,
                'stop_loss': self.stop_loss,
                'target': self.target,
                'quantity': self.quantity,
                'order_id': self.order_id
            })
    
    def exit_trade(self, reason: str, current_price: float):
        """
        Exit current trade
        """
        if not self.current_position:
            return
        
        print(f"\n{'='*60}")
        print(f"EXITING {self.current_position} TRADE - {reason}")
        print(f"{'='*60}")
        
        exit_order_id = self.broker.exit_position(self.strike, self.current_position, 
                                                   self.quantity)
        
        pnl = (current_price - self.entry_price) / self.entry_price * 100
        pnl_amount = (current_price - self.entry_price) * self.quantity
        
        print(f"Entry Price: {self.entry_price}")
        print(f"Exit Price: {current_price}")
        print(f"P&L: {pnl:.2f}%")
        print(f"P&L Amount: ₹{pnl_amount:.2f}")
        
        self.log_trade("EXIT", {
            'option_type': self.current_position,
            'strike': self.strike,
            'entry_price': self.entry_price,
            'exit_price': current_price,
            'reason': reason,
            'pnl_percent': pnl,
            'pnl_amount': pnl_amount,
            'quantity': self.quantity,
            'exit_order_id': exit_order_id
        })
        
        # Reset position
        self.current_position = None
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        self.order_id = None
        self.strike = None
        self.quantity = None
        
        self.save_state()
    
    def check_exit_conditions(self):
        """
        Check if exit conditions are met for current position
        """
        if not self.current_position:
            return
        
        expiry = self.broker.get_nearest_expiry()
        symbol = self.broker.get_option_symbol(self.strike, self.current_position, expiry)
        current_price = self.broker.get_option_ltp(symbol)
        
        if not current_price:
            return
        
        # Check stop loss
        if current_price <= self.stop_loss:
            self.exit_trade("STOP_LOSS", current_price)
            return
        
        # Check target
        if current_price >= self.target:
            self.exit_trade("TARGET", current_price)
            return
    
    def check_entry_conditions(self):
        """
        Check if entry conditions are met
        """
        if not self.can_take_new_trade():
            return
        
        current_price = self.data_fetcher.get_current_price()
        
        if not current_price:
            return
        
        # Check for high breakout (CE entry)
        if not self.high_breakout_triggered and current_price > self.prev_high:
            print(f"\n🚀 HIGH BREAKOUT DETECTED!")
            print(f"Current Price: {current_price} > Previous High: {self.prev_high}")
            self.enter_trade("CE", current_price)
            return
        
        # Check for low breakout (PE entry)
        if not self.low_breakout_triggered and current_price < self.prev_low:
            print(f"\n📉 LOW BREAKOUT DETECTED!")
            print(f"Current Price: {current_price} < Previous Low: {self.prev_low}")
            self.enter_trade("PE", current_price)
            return
    
    def monitor_positions(self):
        """
        Main monitoring loop
        """
        if not self.is_trading_hours():
            return
        
        # Check exit conditions first
        if self.current_position:
            self.check_exit_conditions()
        
        # Check entry conditions
        self.check_entry_conditions()
    
    def end_of_day_cleanup(self):
        """
        Square off all positions at end of day (3:15 PM)
        """
        if self.current_position:
            print("\n⚠️  END OF DAY - Squaring off positions")
            expiry = self.broker.get_nearest_expiry()
            symbol = self.broker.get_option_symbol(self.strike, self.current_position, expiry)
            current_price = self.broker.get_option_ltp(symbol)
            
            if not current_price:
                current_price = self.entry_price  # Fallback
            
            self.exit_trade("EOD_SQUARE_OFF", current_price)


if __name__ == "__main__":
    # Test the trade manager
    manager = TradeManager()
    
    print("Testing Trade Manager...")
    print("-" * 50)
    
    if manager.initialize_day():
        print("Day initialized successfully")
        print(f"Can take trade: {manager.can_take_new_trade()}")
        print(f"Is trading hours: {manager.is_trading_hours()}")
