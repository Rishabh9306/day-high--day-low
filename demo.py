#!/usr/bin/env python3
"""
Demo script to understand how the trading system works
This simulates the bot's decision-making process
"""
from datetime import datetime
import pytz
from data_fetcher import DataFetcher
from kite_broker import KiteBroker

def main():
    print("\n" + "="*70)
    print("🎓 NIFTY 50 BREAKOUT TRADING SYSTEM - DEMO")
    print("="*70)
    
    # Initialize
    fetcher = DataFetcher()
    broker = KiteBroker()
    ist = pytz.timezone('Asia/Kolkata')
    
    print("\n📋 STEP 1: Fetch Previous Day Data")
    print("-" * 70)
    prev_high, prev_low = fetcher.get_previous_day_high_low()
    
    if not prev_high or not prev_low:
        print("❌ Could not fetch previous day data")
        return
    
    print(f"✅ Previous Day High: {prev_high}")
    print(f"✅ Previous Day Low: {prev_low}")
    print(f"   Range: {prev_high - prev_low:.2f} points")
    
    print("\n📋 STEP 2: Get Current Market Price")
    print("-" * 70)
    current_price = fetcher.get_current_price()
    
    if not current_price:
        print("❌ Could not fetch current price")
        return
    
    print(f"✅ Current Nifty: {current_price}")
    
    print("\n📋 STEP 3: Analyze Breakout Conditions")
    print("-" * 70)
    
    # Calculate distances
    distance_from_high = current_price - prev_high
    distance_from_low = current_price - prev_low
    
    print(f"Distance from Previous High: {distance_from_high:+.2f} points")
    print(f"Distance from Previous Low: {distance_from_low:+.2f} points")
    
    # Check conditions
    high_breakout = current_price > prev_high
    low_breakout = current_price < prev_low
    
    print("\n🔍 Breakout Status:")
    print(f"   High Breakout (CE Entry): {'✅ YES' if high_breakout else '❌ NO'}")
    print(f"   Low Breakout (PE Entry):  {'✅ YES' if low_breakout else '❌ NO'}")
    
    print("\n📋 STEP 4: Option Strike Selection")
    print("-" * 70)
    
    atm_strike = broker.get_atm_strike(current_price)
    expiry = broker.get_nearest_expiry()
    
    print(f"✅ ATM Strike: {atm_strike}")
    print(f"✅ Nearest Expiry: {expiry}")
    
    # Generate option symbols
    ce_symbol = broker.get_option_symbol(atm_strike, "CE", expiry)
    pe_symbol = broker.get_option_symbol(atm_strike, "PE", expiry)
    
    print(f"   CE Symbol: {ce_symbol}")
    print(f"   PE Symbol: {pe_symbol}")
    
    print("\n📋 STEP 5: Calculate Entry/Exit Levels")
    print("-" * 70)
    
    # Assume option price is 2% of spot (approximation)
    assumed_option_price = current_price * 0.02
    
    stop_loss_price = assumed_option_price * 0.80  # 20% below entry
    target_price = assumed_option_price * 1.40     # 40% above entry
    
    print(f"Assumed Option Entry: ₹{assumed_option_price:.2f}")
    print(f"Stop Loss (20%):      ₹{stop_loss_price:.2f}")
    print(f"Target (40%):         ₹{target_price:.2f}")
    
    stop_loss_points = assumed_option_price - stop_loss_price
    target_points = target_price - assumed_option_price
    
    print(f"\nRisk:Reward Ratio: 1:{target_points/stop_loss_points:.2f}")
    
    print("\n📋 STEP 6: Position Sizing")
    print("-" * 70)
    
    LOT_SIZE = 50
    capital = 50000
    
    lots = capital // (assumed_option_price * LOT_SIZE)
    quantity = lots * LOT_SIZE
    total_investment = assumed_option_price * quantity
    
    print(f"Capital Available: ₹{capital:,.0f}")
    print(f"Lot Size: {LOT_SIZE}")
    print(f"Number of Lots: {int(lots)}")
    print(f"Total Quantity: {quantity}")
    print(f"Total Investment: ₹{total_investment:,.2f}")
    
    # Calculate P&L scenarios
    print("\n💰 P&L Scenarios:")
    
    sl_loss = (stop_loss_price - assumed_option_price) * quantity
    target_profit = (target_price - assumed_option_price) * quantity
    
    print(f"   If Stop Loss Hit:  ₹{sl_loss:,.2f} ({sl_loss/total_investment*100:.1f}%)")
    print(f"   If Target Hit:     ₹{target_profit:,.2f} ({target_profit/total_investment*100:.1f}%)")
    
    print("\n📋 STEP 7: Trading Decision")
    print("-" * 70)
    
    if high_breakout:
        print("🚀 SIGNAL: BUY CE (Call Option)")
        print(f"   Reason: Price {current_price} crossed above previous high {prev_high}")
        print(f"   Action: Enter {ce_symbol} at market price")
    elif low_breakout:
        print("📉 SIGNAL: BUY PE (Put Option)")
        print(f"   Reason: Price {current_price} crossed below previous low {prev_low}")
        print(f"   Action: Enter {pe_symbol} at market price")
    else:
        print("⏳ SIGNAL: WAIT")
        print(f"   Reason: Price {current_price} is within previous day range")
        print(f"   Need: Price > {prev_high} for CE or Price < {prev_low} for PE")
    
    print("\n📋 STEP 8: Risk Management Summary")
    print("-" * 70)
    print("✅ Intraday Only: All positions squared off at 3:15 PM")
    print("✅ Stop Loss: Automatic exit at 20% loss")
    print("✅ Target: Automatic exit at 40% profit")
    print("✅ Max Trades: 2 per day (1 CE + 1 PE)")
    print("✅ Position Sizing: Based on available capital")
    
    print("\n" + "="*70)
    print("Demo Complete! Run 'python main.py' to start the bot.")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
