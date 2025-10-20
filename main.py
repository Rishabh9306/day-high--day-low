#!/usr/bin/env python3
"""
Main trading bot - Nifty 50 Breakout Strategy
Trades breakouts based on previous day's high/low
"""
import time
from datetime import datetime
import pytz
import signal
import sys
import config
from trade_manager import TradeManager

class TradingBot:
    def __init__(self):
        self.trade_manager = TradeManager()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.running = False
        self.day_initialized = False
    
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⚠️  Shutdown signal received...")
        self.running = False
    
    def is_market_day(self) -> bool:
        """Check if today is a trading day (weekday)"""
        now = datetime.now(self.ist)
        return now.weekday() < 5  # Monday = 0, Friday = 4
    
    def should_initialize_day(self) -> bool:
        """Check if day should be initialized"""
        # Always initialize if prev_high/prev_low are not set
        if self.trade_manager.prev_high is None or self.trade_manager.prev_low is None:
            return True
        
        now = datetime.now(self.ist)
        
        # Initialize before market opens (before 9:15 AM)
        if now.hour < config.TRADING_START_HOUR or \
           (now.hour == config.TRADING_START_HOUR and now.minute < config.TRADING_START_MINUTE):
            return True
        
        # Also allow initialization during early trading hours if not done
        if now.hour == config.TRADING_START_HOUR and now.minute < 30:
            return True
        
        return False
    
    def is_end_of_day(self) -> bool:
        """Check if it's time for end of day square off"""
        now = datetime.now(self.ist)
        return (now.hour == config.TRADING_END_HOUR and 
                now.minute >= config.TRADING_END_MINUTE)
    
    def print_status(self):
        """Print current status"""
        now = datetime.now(self.ist)
        status = "🟢 ACTIVE" if self.trade_manager.is_trading_hours() else "🔴 CLOSED"
        
        print(f"\n{'='*70}")
        print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S IST')} | Market: {status}")
        print(f"{'='*70}")
        
        if self.trade_manager.prev_high and self.trade_manager.prev_low:
            print(f"📊 Previous Day - High: {self.trade_manager.prev_high}, Low: {self.trade_manager.prev_low}")
        
        current_price = self.trade_manager.data_fetcher.get_current_price()
        if current_price:
            print(f"💹 Current Nifty: {current_price}")
        
        if self.trade_manager.current_position:
            print(f"📍 Position: {self.trade_manager.current_position} @ {self.trade_manager.strike}")
            print(f"   Entry: ₹{self.trade_manager.entry_price:.2f}")
            
            if self.trade_manager.trailing_sl_active:
                print(f"   🎯 Trailing SL Active!")
                print(f"   High Water Mark: ₹{self.trade_manager.high_water_mark:.2f}")
                print(f"   Trailing SL: ₹{self.trade_manager.trailing_stop_loss:.2f} | Target: ₹{self.trade_manager.target:.2f}")
            else:
                print(f"   SL: ₹{self.trade_manager.stop_loss:.2f} | Target: ₹{self.trade_manager.target:.2f}")
        else:
            print(f"📍 Position: None")
        
        print(f"📈 Trades Today: {self.trade_manager.trades_today}/{config.MAX_TRADES_PER_DAY}")
        print(f"🔸 High Breakout: {'✓' if self.trade_manager.high_breakout_triggered else '✗'}")
        print(f"🔹 Low Breakout: {'✓' if self.trade_manager.low_breakout_triggered else '✗'}")
        print(f"{'='*70}")
    
    def run(self):
        """Main execution loop"""
        print("\n" + "="*70)
        print("🚀 NIFTY 50 BREAKOUT TRADING BOT")
        print("="*70)
        print(f"Strategy: Day High/Low Breakout")
        print(f"Stop Loss: {config.STOP_LOSS_PERCENT}% | Target: {config.TARGET_PERCENT}%")
        print(f"Trading Hours: {config.TRADING_START_HOUR}:{config.TRADING_START_MINUTE:02d} - {config.TRADING_END_HOUR}:{config.TRADING_END_MINUTE:02d} IST")
        print(f"Check Interval: {config.CHECK_INTERVAL_SECONDS} seconds")
        print("="*70)
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.running = True
        
        while self.running:
            try:
                # Check if market day
                if not self.is_market_day():
                    print("📅 Weekend - Market closed. Waiting...")
                    time.sleep(3600)  # Check every hour
                    continue
                
                # Initialize day if needed
                if not self.day_initialized and self.should_initialize_day():
                    if self.trade_manager.initialize_day():
                        self.day_initialized = True
                        print("✅ Day initialized successfully")
                    else:
                        print("⚠️  Failed to initialize day. Retrying in 5 minutes...")
                        time.sleep(300)
                        continue
                
                # Check if end of day
                if self.is_end_of_day():
                    self.trade_manager.end_of_day_cleanup()
                    print("\n📊 Trading day ended. See you tomorrow!")
                    self.day_initialized = False
                    time.sleep(3600)  # Wait an hour before checking again
                    continue
                
                # Print status
                self.print_status()
                
                # Monitor positions and check for trades
                if self.day_initialized:
                    self.trade_manager.monitor_positions()
                
                # Wait before next check
                time.sleep(config.CHECK_INTERVAL_SECONDS)
                
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # Wait a minute before retrying
        
        print("\n👋 Bot stopped. Goodbye!")


def main():
    """Entry point"""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
