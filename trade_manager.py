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
import notifier
import time

class TradeManager:
    def __init__(self):
        self.broker = KiteBroker()
        # Pass kite instance to data_fetcher so it uses Zerodha API
        self.data_fetcher = DataFetcher(kite=self.broker.kite)
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
        
        # Trailing Stop Loss state (per-trade — resets on exit)
        self.trailing_sl_active = False
        self.highest_price_seen = 0.0   # Persisted: prevents TSL regression after restart
        self.entry_time = None          # When trade was entered — used for TSL cooldown
        
        # Flags
        self.high_breakout_triggered = False
        self.low_breakout_triggered = False
        
        # Rejection circuit breaker — stops order spam after N consecutive rejections
        self.consecutive_rejections = 0
        self.MAX_REJECTIONS = 3  # Stop trying after 3 rejections
        
        # Aggressive monitoring timers (reconcile_position now runs EVERY loop - no timer needed)
        self.last_order_check_time = None
        self.order_check_interval = config.ORDER_BOOK_CHECK_INTERVAL
        
        self.last_trade_analysis_time = None
        self.trade_analysis_interval = config.TRADE_ANALYSIS_INTERVAL
        
        self.last_margin_check_time = None
        self.margin_check_interval = config.MARGIN_CHECK_INTERVAL
        
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
                        # TSL state — critical for restart persistence
                        self.trailing_sl_active = state.get('trailing_sl_active', False)
                        self.highest_price_seen = state.get('highest_price_seen', 0.0)
                        self.entry_time = state.get('entry_time')
                        # Circuit breaker — persists rejection count across restarts
                        self.consecutive_rejections = state.get('consecutive_rejections', 0)
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
                # TSL state — must persist for restart safety
                'trailing_sl_active': self.trailing_sl_active,
                'highest_price_seen': self.highest_price_seen,
                'entry_time': self.entry_time,
                # Circuit breaker — survives crashes
                'consecutive_rejections': self.consecutive_rejections,
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
        """Check if new trade can be taken — must be in trading hours"""
        return (self.is_trading_hours() and
                self.current_position is None and 
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
        
        # Get strike (ATM or OTM based on STRIKE_OFFSET in .env)
        self.strike = self.broker.get_atm_strike(spot_price, option_type)
        print(f"Spot Price: {spot_price}")
        print(f"Strike: {self.strike} ({'OTM' if config.STRIKE_OFFSET else 'ATM'})")
        
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
        
        # Place order and verify actual fill price
        print(f"\n🔄 Placing order with verification...")
        order_result = self.broker.place_option_order_verified(self.strike, option_type, 
                                                               quantity=self.quantity)
        
        if order_result and order_result['status'] == 'COMPLETE':
            self.order_id = order_result['order_id']
            self.current_position = option_type
            
            # Use ACTUAL fill price, not the quote
            actual_fill_price = order_result['average_price']
            self.entry_price = actual_fill_price
            
            # Recalculate SL and Target based on ACTUAL entry price
            self.stop_loss = actual_fill_price * (1 - sl_percent / 100)
            self.target = actual_fill_price * (1 + target_percent / 100)
            self.trades_today += 1
            
            # Initialize per-trade TSL state
            self.trailing_sl_active = False
            self.highest_price_seen = actual_fill_price
            self.entry_time = time.time()  # TSL cooldown starts now
            
            print(f"\n✅ ORDER FILLED SUCCESSFULLY")
            print(f"Quote Price: ₹{option_price}")
            print(f"Actual Fill: ₹{actual_fill_price}")
            if abs(actual_fill_price - option_price) > 1:
                diff = actual_fill_price - option_price
                print(f"⚠️  Slippage: ₹{diff:+.2f}")
            
            # Reset rejection counter on successful fill
            self.consecutive_rejections = 0
            
            print(f"Entry Price: {self.entry_price}")
            print(f"Stop Loss: {self.stop_loss:.2f} (-{sl_percent}%)")
            print(f"Target: {self.target:.2f} (+{target_percent}%)")
            if config.ENABLE_TRAILING_SL:
                print(f"TSL: ON — steps at {[s[0] for s in config.TRAILING_SL_STEPS]}%")
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
            
            # Telegram: order filled
            notifier.notify_entry(option_type, self.strike, actual_fill_price,
                                  self.stop_loss, self.target, self.quantity)
        elif order_result:
            self.consecutive_rejections += 1
            error_msg = order_result.get('error', 'Unknown error')
            print(f"❌ Order {order_result['status']}: {error_msg}")
            print(f"   Rejection #{self.consecutive_rejections}/{self.MAX_REJECTIONS}")
            if self.consecutive_rejections >= self.MAX_REJECTIONS:
                msg = (f"🚨 CIRCUIT BREAKER: {self.MAX_REJECTIONS} consecutive rejections. "
                       f"Stopping order attempts for today.\nLast error: {error_msg}")
                print(f"\n🚨 {msg}")
                notifier.notify_error(msg)
            else:
                notifier.notify_error(f"Order {order_result['status']}: {error_msg}")
            return
        else:
            self.consecutive_rejections += 1
            print(f"❌ Order placement failed (rejection #{self.consecutive_rejections}/{self.MAX_REJECTIONS})")
            if self.consecutive_rejections >= self.MAX_REJECTIONS:
                msg = f"🚨 CIRCUIT BREAKER: {self.MAX_REJECTIONS} consecutive failures. Stopping."
                print(f"\n🚨 {msg}")
                notifier.notify_error(msg)
            else:
                notifier.notify_error("Order placement failed — no order_id returned")
            return
    
    def exit_trade(self, reason: str, current_price: float):
        """
        Exit current trade. Uses verified exit (polls for fill confirmation).
        State is only reset if the exit order is confirmed COMPLETE.
        """
        if not self.current_position or not self.entry_price:
            return
        
        print(f"\n{'='*60}")
        print(f"EXITING {self.current_position} TRADE - {reason}")
        print(f"{'='*60}")
        
        exit_result = self.broker.exit_position_verified(
            self.strike, self.current_position, self.quantity
        )

        if not exit_result or exit_result['status'] != 'COMPLETE':
            # Exit order failed or unconfirmed — do NOT reset state.
            # Keep monitoring; next loop iteration will retry.
            status = exit_result['status'] if exit_result else 'NO_RESULT'
            print(f"🚨 EXIT ORDER NOT CONFIRMED (status={status}). "
                  f"Position still tracked. Will retry next cycle.")
            return

        # Use actual fill price for P&L if available
        actual_exit_price = exit_result.get('average_price') or current_price
        exit_order_id = exit_result.get('order_id')

        pnl = (actual_exit_price - self.entry_price) / self.entry_price * 100
        pnl_amount = (actual_exit_price - self.entry_price) * self.quantity
        
        print(f"Entry Price: ₹{self.entry_price}")
        print(f"Exit Price:  ₹{actual_exit_price:.2f} (pre-exit LTP was ₹{current_price})")
        print(f"P&L: {pnl:.2f}%")
        print(f"P&L Amount: ₹{pnl_amount:.2f}")
        if self.trailing_sl_active:
            print(f"Peak Profit Seen: +{((self.highest_price_seen - self.entry_price) / self.entry_price * 100):.1f}%")
        
        # Telegram: position exited
        notifier.notify_exit(self.current_position, self.strike, self.entry_price,
                             actual_exit_price, pnl, pnl_amount, reason)
        
        self.log_trade("EXIT", {
            'option_type': self.current_position,
            'strike': self.strike,
            'entry_price': self.entry_price,
            'exit_price': actual_exit_price,
            'exit_ltp_at_trigger': current_price,
            'reason': reason,
            'pnl_percent': pnl,
            'pnl_amount': pnl_amount,
            'quantity': self.quantity,
            'exit_order_id': exit_order_id,
            'trailing_sl_active': self.trailing_sl_active,
            'highest_price_seen': self.highest_price_seen,
        })
        
        # Reset position AND per-trade TSL state after confirmed exit
        self.current_position = None
        self.entry_price = None
        self.stop_loss = None
        self.target = None
        self.order_id = None
        self.strike = None
        self.quantity = None
        self.trailing_sl_active = False
        self.highest_price_seen = 0.0
        
        self.save_state()
    
    def update_trailing_sl(self, current_price: float):
        """
        Step-based Trailing Stop Loss.
        Ratchets the SL upward as profit crosses predefined thresholds.
        SL NEVER moves back down. Persists highest_price_seen for restart safety.
        If a step has lock='EXIT', immediately triggers a trade exit.
        
        Returns: 'EXIT' if the hard-exit threshold was crossed, else None.
        """
        if not config.ENABLE_TRAILING_SL:
            return None
        
        if not self.entry_price or self.entry_price <= 0:
            return None
        
        # TSL cooldown — skip trailing SL for first 60s after entry
        # Prevents gamma traps on 0DTE options where prices spike +15% in seconds
        if self.entry_time and (time.time() - self.entry_time) < config.TSL_COOLDOWN_SECONDS:
            return None
        
        # Track the highest option price seen during this trade (persisted)
        if current_price > self.highest_price_seen:
            self.highest_price_seen = current_price
        
        # Calculate current profit percentage
        profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        
        # Find the highest applicable trailing step (iterate in reverse)
        for threshold, sl_level in reversed(config.TRAILING_SL_STEPS):
            if profit_pct >= threshold:
                # Hard exit step
                if sl_level == 'EXIT':
                    print(f"\n🎯 TSL HARD EXIT TRIGGERED!")
                    print(f"   Profit: +{profit_pct:.1f}% crossed +{threshold}% threshold")
                    notifier.notify_trailing_exit(profit_pct, current_price)
                    return 'EXIT'
                
                # Calculate the new SL price
                candidate_sl = round(self.entry_price * (1 + sl_level / 100), 2)
                
                # SL must ONLY move UP, never down
                if candidate_sl > self.stop_loss:
                    old_sl = self.stop_loss
                    self.stop_loss = candidate_sl
                    self.trailing_sl_active = True
                    
                    print(f"\n📈 TRAILING SL TRIGGERED!")
                    print(f"   Profit: +{profit_pct:.1f}% | Peak: +{((self.highest_price_seen - self.entry_price) / self.entry_price * 100):.1f}%")
                    print(f"   Step: +{threshold}% → SL locked at +{sl_level}%")
                    print(f"   SL moved: ₹{old_sl:.2f} → ₹{self.stop_loss:.2f}")
                    
                    # Telegram: TSL moved
                    notifier.notify_trailing_sl(profit_pct, old_sl, self.stop_loss,
                                               threshold, sl_level)
                    self.save_state()
                break  # Found the highest matching step — stop looking
        
        return None
    
    def check_exit_conditions(self):
        """
        Check if exit conditions are met for current position.
        Order: TSL update → SL check → Target check.
        """
        if not self.current_position:
            return
        
        # AGGRESSIVE: Reconcile position EVERY time (10 times/sec when in position)
        # This uses 100% of Zerodha's Positions API limit (10 calls/sec = 36,000/hour)
        self.reconcile_position()
        
        expiry = self.broker.get_nearest_expiry()
        symbol = self.broker.get_option_symbol(self.strike, self.current_position, expiry)
        current_price = self.broker.get_option_ltp(symbol)
        
        if not current_price:
            return
        
        # Update trailing SL (may ratchet SL up, or trigger hard exit)
        tsl_action = self.update_trailing_sl(current_price)
        if tsl_action == 'EXIT':
            self.exit_trade("TSL_HARD_EXIT", current_price)
            return
        
        # Check stop loss (now potentially trailing)
        if current_price <= self.stop_loss:
            reason = "TRAILING_SL" if self.trailing_sl_active else "STOP_LOSS"
            self.exit_trade(reason, current_price)
            return
        
        # Check target
        if current_price >= self.target:
            self.exit_trade("TARGET", current_price)
            return
    
    def reconcile_position(self):
        """
        Reconcile our position with Zerodha to catch any discrepancies
        """
        if not self.current_position or not self.strike:
            return
        
        expiry = self.broker.get_nearest_expiry()
        symbol = self.broker.get_option_symbol(self.strike, self.current_position, expiry)
        
        position_data = self.broker.reconcile_position(symbol)
        
        if position_data:
            actual_entry = position_data['actual_entry']
            
            # Check if entry price differs
            if abs(actual_entry - self.entry_price) > 0.5:
                print(f"\n⚠️  POSITION RECONCILIATION ALERT")
                print(f"Bot Entry Price: ₹{self.entry_price}")
                print(f"Zerodha Actual Entry: ₹{actual_entry}")
                print(f"Difference: ₹{actual_entry - self.entry_price:+.2f}")
                
                # Update to actual entry price
                old_sl = self.stop_loss
                old_target = self.target
                
                self.entry_price = actual_entry
                
                # Recalculate SL and Target
                if config.USE_VIX_BASED_TARGETS:
                    vix = self.data_fetcher.get_india_vix()
                    if vix:
                        sl_percent = int(vix * config.VIX_SL_MULTIPLIER)
                        target_percent = int(vix * config.VIX_TARGET_MULTIPLIER)
                    else:
                        sl_percent = config.STOP_LOSS_PERCENT
                        target_percent = config.TARGET_PERCENT
                else:
                    sl_percent = config.STOP_LOSS_PERCENT
                    target_percent = config.TARGET_PERCENT
                
                self.stop_loss = actual_entry * (1 - sl_percent / 100)
                self.target = actual_entry * (1 + target_percent / 100)
                
                print(f"Updated SL: ₹{old_sl:.2f} → ₹{self.stop_loss:.2f}")
                print(f"Updated Target: ₹{old_target:.2f} → ₹{self.target:.2f}")
                
                self.save_state()
            
            # Log current P&L
            pnl = position_data.get('pnl', 0)
            last_price = position_data.get('last_price', 0)
            if pnl != 0:
                print(f"📊 Position: {symbol} | LTP: ₹{last_price} | P&L: ₹{pnl:+.2f}")
        else:
            print(f"⚠️  Position for {symbol} not found in Zerodha positions")
            # Position was force-closed by broker (margin call, circuit, auto-square-off).
            # Reset local state so the bot does not stay frozen thinking it holds a position.
            print(f"🚨 FORCE-CLOSE DETECTED: Resetting local position state.")
            self.log_trade("FORCE_CLOSE_DETECTED", {
                'option_type': self.current_position,
                'strike': self.strike,
                'entry_price': self.entry_price,
                'symbol': symbol,
                'trailing_sl_active': self.trailing_sl_active,
                'highest_price_seen': self.highest_price_seen,
                'note': 'Position not found in Zerodha — assumed force-closed by broker'
            })
            notifier.notify_error(
                f"FORCE-CLOSE DETECTED\n{self.current_position} {self.strike}\n"
                f"Position not found in Zerodha — state reset."
            )
            self.current_position = None
            self.entry_price = None
            self.stop_loss = None
            self.target = None
            self.order_id = None
            self.strike = None
            self.quantity = None
            self.trailing_sl_active = False
            self.highest_price_seen = 0.0
            self.save_state()
    
    def check_entry_conditions(self):
        """
        Check if entry conditions are met
        """
        if not self.can_take_new_trade():
            return
        
        current_price = self.data_fetcher.get_current_price()
        
        if not current_price:
            return
        
        # Circuit breaker — stop if too many rejections
        if self.consecutive_rejections >= self.MAX_REJECTIONS:
            return
        
        # Check for high breakout (CE entry)
        if not self.high_breakout_triggered and current_price > self.prev_high:
            print(f"\n🚀 HIGH BREAKOUT DETECTED!")
            print(f"Current Price: {current_price} > Previous High: {self.prev_high}")
            # Set flag IMMEDIATELY on detection — prevents retry loop if order fails
            self.high_breakout_triggered = True
            self.save_state()
            notifier.notify_breakout("HIGH", current_price, self.prev_high)
            self.enter_trade("CE", current_price)
            return
        
        # Check for low breakout (PE entry)
        if not self.low_breakout_triggered and current_price < self.prev_low:
            print(f"\n📉 LOW BREAKOUT DETECTED!")
            print(f"Current Price: {current_price} < Previous Low: {self.prev_low}")
            # Set flag IMMEDIATELY on detection — prevents retry loop if order fails
            self.low_breakout_triggered = True
            self.save_state()
            notifier.notify_breakout("LOW", current_price, self.prev_low)
            self.enter_trade("PE", current_price)
            return
    
    def aggressive_order_monitoring(self):
        """
        AGGRESSIVE: Monitor all orders every 5 seconds
        Zerodha limit: 10/sec = 720/minute (we use 12/minute = 1.6%)
        """
        now = time.time()
        if self.last_order_check_time is None or (now - self.last_order_check_time) >= self.order_check_interval:
            orders = self.broker.get_all_orders()
            
            if orders:
                analysis = self.broker.analyze_order_book(orders)
                if analysis['rejected'] > 0 or analysis['pending'] > 0:
                    print(f"⚠️  Orders: {analysis['complete']} complete, {analysis['pending']} pending, {analysis['rejected']} rejected")
            
            self.last_order_check_time = now
    
    def aggressive_trade_analysis(self):
        """
        AGGRESSIVE: Analyze all trades every 60 seconds
        Zerodha limit: 10/sec = 60/hour for this check (negligible)
        """
        now = time.time()
        if self.last_trade_analysis_time is None or (now - self.last_trade_analysis_time) >= self.trade_analysis_interval:
            trades = self.broker.get_all_trades()
            
            if trades:
                analysis = self.broker.analyze_trade_execution(trades)
                if analysis['total_trades'] > 0:
                    print(f"📈 Trades: {analysis['total_trades']} fills, Avg Price: ₹{analysis['avg_price']:.2f}")
            
            self.last_trade_analysis_time = now
    
    def aggressive_margin_monitoring(self):
        """
        AGGRESSIVE: Check margins every 10 seconds
        Zerodha limit: 10/sec = 360/hour for this check (<1%)
        """
        now = time.time()
        if self.last_margin_check_time is None or (now - self.last_margin_check_time) >= self.margin_check_interval:
            margins = self.broker.get_margins()
            
            if margins and 'equity' in margins:
                available = margins['equity'].get('available', {}).get('live_balance', 0)
                used = margins['equity'].get('utilised', {}).get('debits', 0)
                
                if available > 0:
                    utilization = (used / (available + used)) * 100 if (available + used) > 0 else 0
                    if utilization > 80:
                        print(f"⚠️  High margin usage: {utilization:.1f}% (₹{used:.0f}/₹{available+used:.0f})")
            
            self.last_margin_check_time = now
    
    def monitor_positions(self):
        """
        Main monitoring loop with AGGRESSIVE API usage
        Maximizes Zerodha API calls within rate limits
        """
        if not self.is_trading_hours():
            return
        
        # AGGRESSIVE: Order book monitoring (every 5s)
        self.aggressive_order_monitoring()
        
        # AGGRESSIVE: Trade analysis (every 60s)
        self.aggressive_trade_analysis()
        
        # AGGRESSIVE: Margin monitoring (every 10s)
        self.aggressive_margin_monitoring()
        
        # Check exit conditions first (with 1s position reconciliation)
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
