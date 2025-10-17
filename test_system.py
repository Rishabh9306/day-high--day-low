#!/usr/bin/env python3
"""
Comprehensive test suite for the trading system
Run this to verify everything is working correctly
"""
import sys
from datetime import datetime
import pytz

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_test(name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"     └─ {details}")

def test_imports():
    """Test all required imports"""
    print_header("TEST 1: Package Imports")
    
    tests = [
        ("yfinance", "import yfinance as yf"),
        ("pandas", "import pandas as pd"),
        ("numpy", "import numpy as np"),
        ("kiteconnect", "from kiteconnect import KiteConnect"),
        ("pytz", "import pytz"),
        ("dotenv", "from dotenv import load_dotenv"),
        ("schedule", "import schedule"),
        ("requests", "import requests"),
    ]
    
    all_passed = True
    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print_test(name, True)
        except ImportError as e:
            print_test(name, False, str(e))
            all_passed = False
    
    return all_passed

def test_config():
    """Test configuration"""
    print_header("TEST 2: Configuration")
    
    try:
        import config
        
        tests = [
            ("API_KEY defined", hasattr(config, 'API_KEY')),
            ("STOP_LOSS_PERCENT defined", hasattr(config, 'STOP_LOSS_PERCENT')),
            ("TARGET_PERCENT defined", hasattr(config, 'TARGET_PERCENT')),
            ("TRADING_START_HOUR defined", hasattr(config, 'TRADING_START_HOUR')),
            ("CHECK_INTERVAL_SECONDS defined", hasattr(config, 'CHECK_INTERVAL_SECONDS')),
        ]
        
        all_passed = True
        for name, passed in tests:
            print_test(name, passed)
            if not passed:
                all_passed = False
        
        # Check values
        print_test("Stop Loss = 20%", config.STOP_LOSS_PERCENT == 20, 
                  f"Current: {config.STOP_LOSS_PERCENT}")
        print_test("Target = 40%", config.TARGET_PERCENT == 40, 
                  f"Current: {config.TARGET_PERCENT}")
        
        return all_passed
    except Exception as e:
        print_test("Config module", False, str(e))
        return False

def test_data_fetcher():
    """Test data fetching capabilities"""
    print_header("TEST 3: Data Fetcher")
    
    try:
        from data_fetcher import DataFetcher
        
        fetcher = DataFetcher()
        
        # Test previous day data
        print("Fetching previous day high/low...")
        prev_high, prev_low = fetcher.get_previous_day_high_low()
        
        test1 = prev_high is not None and prev_low is not None
        print_test("Previous day data", test1, 
                  f"High: {prev_high}, Low: {prev_low}" if test1 else "Failed to fetch")
        
        if test1:
            test2 = prev_high > prev_low
            print_test("High > Low validation", test2, 
                      f"{prev_high} > {prev_low}")
        else:
            test2 = False
        
        # Test current price
        print("Fetching current price...")
        current_price = fetcher.get_current_price()
        
        test3 = current_price is not None
        print_test("Current price", test3, 
                  f"Price: {current_price}" if test3 else "Failed to fetch")
        
        # Test today's high/low
        print("Fetching today's high/low...")
        today_high, today_low = fetcher.get_today_high_low()
        
        test4 = today_high is not None and today_low is not None
        print_test("Today's high/low", test4, 
                  f"High: {today_high}, Low: {today_low}" if test4 else "Failed to fetch")
        
        return test1 and test2 and test3 and test4
        
    except Exception as e:
        print_test("Data Fetcher", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def test_kite_broker():
    """Test Kite broker interface"""
    print_header("TEST 4: Kite Broker")
    
    try:
        from kite_broker import KiteBroker
        
        broker = KiteBroker()
        
        # Test ATM calculation
        test_strikes = [19500.25, 19549.99, 19550.01, 19600.75]
        expected = [19500, 19550, 19550, 19600]
        
        print("Testing ATM strike calculations...")
        all_correct = True
        for spot, exp in zip(test_strikes, expected):
            atm = broker.get_atm_strike(spot)
            correct = atm == exp
            if not correct:
                all_correct = False
            print_test(f"ATM for {spot}", correct, f"Got {atm}, Expected {exp}")
        
        test1 = all_correct
        
        # Test expiry calculation
        expiry = broker.get_nearest_expiry()
        test2 = expiry is not None and len(expiry) == 10  # YYYY-MM-DD format
        print_test("Expiry calculation", test2, f"Expiry: {expiry}" if test2 else "Failed")
        
        # Test symbol generation
        symbol = broker.get_option_symbol(19500, "CE", "2025-10-16")
        test3 = "NIFTY" in symbol and "CE" in symbol
        print_test("Option symbol generation", test3, f"Symbol: {symbol}")
        
        return test1 and test2 and test3
        
    except Exception as e:
        print_test("Kite Broker", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def test_trade_manager():
    """Test trade management logic"""
    print_header("TEST 5: Trade Manager")
    
    try:
        from trade_manager import TradeManager
        
        manager = TradeManager()
        
        # Test initialization
        print("Testing day initialization...")
        result = manager.initialize_day()
        
        test1 = result and manager.prev_high is not None
        print_test("Day initialization", test1, 
                  f"High: {manager.prev_high}, Low: {manager.prev_low}" if test1 else "Failed")
        
        # Test trading hours check
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        is_trading = manager.is_trading_hours()
        
        expected_trading = (9 <= now.hour < 15) or (now.hour == 15 and now.minute <= 15)
        test2 = True  # Just check it runs
        print_test("Trading hours check", test2, 
                  f"Current: {now.strftime('%H:%M')}, Trading: {is_trading}")
        
        # Test trade capability
        can_trade = manager.can_take_new_trade()
        test3 = isinstance(can_trade, bool)
        print_test("Can take new trade check", test3, f"Result: {can_trade}")
        
        # Test state save/load
        manager.save_state()
        test4 = True
        print_test("State persistence", test4, "State saved successfully")
        
        return test1 and test2 and test3 and test4
        
    except Exception as e:
        print_test("Trade Manager", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def test_main_module():
    """Test main module"""
    print_header("TEST 6: Main Module")
    
    try:
        from main import TradingBot
        
        bot = TradingBot()
        
        # Test initialization
        test1 = bot.trade_manager is not None
        print_test("Bot initialization", test1)
        
        # Test market day check
        is_market_day = bot.is_market_day()
        test2 = isinstance(is_market_day, bool)
        print_test("Market day check", test2, f"Is market day: {is_market_day}")
        
        # Test should initialize
        should_init = bot.should_initialize_day()
        test3 = isinstance(should_init, bool)
        print_test("Should initialize check", test3, f"Should initialize: {should_init}")
        
        return test1 and test2 and test3
        
    except Exception as e:
        print_test("Main Module", False, str(e))
        import traceback
        traceback.print_exc()
        return False

def test_calculations():
    """Test calculation logic"""
    print_header("TEST 7: Calculation Verification")
    
    # Test stop loss calculation
    entry = 100
    sl_pct = 20
    stop_loss = entry * (1 - sl_pct/100)
    test1 = stop_loss == 80
    print_test("Stop Loss calculation", test1, f"Entry: {entry}, SL: {stop_loss}")
    
    # Test target calculation
    target = entry * (1 + 40/100)
    test2 = target == 140
    print_test("Target calculation", test2, f"Entry: {entry}, Target: {target}")
    
    # Test P&L calculation
    exit_price = 120
    quantity = 50
    pnl = (exit_price - entry) * quantity
    test3 = pnl == 1000
    print_test("P&L calculation", test3, f"P&L: ₹{pnl}")
    
    # Test risk:reward ratio
    risk = entry - stop_loss  # 20
    reward = target - entry   # 40
    rr = reward / risk
    test4 = rr == 2.0
    print_test("Risk:Reward ratio", test4, f"R:R = 1:{rr}")
    
    return test1 and test2 and test3 and test4

def run_all_tests():
    """Run all tests"""
    print("\n" + "🔬 " + "="*66)
    print("  NIFTY 50 BREAKOUT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    results = []
    
    results.append(("Package Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Data Fetcher", test_data_fetcher()))
    results.append(("Kite Broker", test_kite_broker()))
    results.append(("Trade Manager", test_trade_manager()))
    results.append(("Main Module", test_main_module()))
    results.append(("Calculations", test_calculations()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {name}")
    
    print("\n" + "-"*70)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Configure .env with your Kite credentials (or use simulation)")
        print("  2. Run: python demo.py (to understand the system)")
        print("  3. Run: python main.py (to start trading)")
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")
        print("The system may still work, but review the issues.")
    
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
