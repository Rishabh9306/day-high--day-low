#!/usr/bin/env python3
"""
Test script to verify weekly expiry fetching
"""
from kite_broker import KiteBroker
from datetime import datetime
import pytz

print("="*70)
print("🧪 TESTING WEEKLY EXPIRY LOGIC")
print("="*70)
print()

broker = KiteBroker()
ist = pytz.timezone('Asia/Kolkata')

# Current date and day
today = datetime.now(ist)
print(f"📅 Current Date: {today.strftime('%Y-%m-%d %A')}")
print(f"⏰ Current Time: {today.strftime('%H:%M:%S IST')}")
print()

# Get nearest expiry
print("🔍 Fetching nearest expiry...")
expiry = broker.get_nearest_expiry()
print()

# Parse and display expiry details
expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
print(f"✅ Nearest Expiry: {expiry} ({expiry_date.strftime('%A')})")
print()

# Calculate days until expiry
days_to_expiry = (expiry_date.date() - today.date()).days
print(f"📆 Days to Expiry: {days_to_expiry}")
print()

# Verify it's a Monday (weekly expiry)
if expiry_date.weekday() == 0:  # Monday
    print("✅ VERIFIED: Expiry is on MONDAY (correct for weekly)")
else:
    print(f"⚠️ WARNING: Expiry is on {expiry_date.strftime('%A')} (expected Monday)")
print()

# Get all available expiries if connected
if broker.kite:
    print("📊 Fetching all available Nifty expiries...")
    instruments = broker.kite.instruments("NFO")
    nifty_options = [i for i in instruments if i['name'] == 'NIFTY' and i['instrument_type'] == 'CE']
    
    expiries = sorted(list(set([i['expiry'].strftime('%Y-%m-%d') for i in nifty_options])))
    
    print(f"\n📋 Next 10 Available Expiries:")
    print("-" * 70)
    for i, exp in enumerate(expiries[:10], 1):
        exp_dt = datetime.strptime(exp, '%Y-%m-%d')
        day_name = exp_dt.strftime('%A')
        days_away = (exp_dt.date() - today.date()).days
        
        # Mark the nearest expiry
        marker = "👉 " if exp == expiry else "   "
        
        # Identify if it's weekly (Monday) or monthly (Thursday)
        exp_type = "Weekly" if exp_dt.weekday() == 0 else "Monthly" if exp_dt.weekday() == 3 else "Special"
        
        print(f"{marker}{i}. {exp} ({day_name:9s}) - {days_away:2d} days - {exp_type}")
    
    print()

# Test option symbol generation
print("🔧 Testing Option Symbol Generation...")
print("-" * 70)

# Use current ATM
from data_fetcher import DataFetcher
fetcher = DataFetcher()
spot = fetcher.get_current_price()
atm_strike = broker.get_atm_strike(spot)

print(f"Spot Price: ₹{spot}")
print(f"ATM Strike: {atm_strike}")
print()

# Generate symbols
ce_symbol = broker.get_option_symbol(atm_strike, "CE", expiry)
pe_symbol = broker.get_option_symbol(atm_strike, "PE", expiry)

print(f"CE Symbol: {ce_symbol}")
print(f"PE Symbol: {pe_symbol}")
print()

# Get option prices
if broker.kite:
    print("💰 Current Option Prices:")
    print("-" * 70)
    
    ce_price = broker.get_option_ltp(ce_symbol)
    pe_price = broker.get_option_ltp(pe_symbol)
    
    print(f"ATM {atm_strike} CE: ₹{ce_price}")
    print(f"ATM {atm_strike} PE: ₹{pe_price}")
    print()
    
    # Show nearby strikes
    print("📊 Nearby Strikes:")
    print("-" * 70)
    for offset in [-100, -50, 0, 50, 100]:
        strike = atm_strike + offset
        sym = broker.get_option_symbol(strike, "CE", expiry)
        try:
            price = broker.get_option_ltp(sym)
            otm_itm = "OTM" if offset > 0 else "ITM" if offset < 0 else "ATM"
            print(f"{strike} CE ({otm_itm}): ₹{price}")
        except:
            print(f"{strike} CE: N/A")

print()
print("="*70)
print("✅ TEST COMPLETE")
print("="*70)
print()
print("Summary:")
print(f"  • Nearest Expiry: {expiry} ({expiry_date.strftime('%A')})")
print(f"  • Days to Expiry: {days_to_expiry}")
print(f"  • ATM Strike: {atm_strike}")
print(f"  • CE Symbol: {ce_symbol}")
print(f"  • PE Symbol: {pe_symbol}")
if broker.kite:
    print(f"  • CE Price: ₹{ce_price}")
    print(f"  • PE Price: ₹{pe_price}")
print()
