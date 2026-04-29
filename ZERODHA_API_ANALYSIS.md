# Zerodha API Request Analysis

## Current Request Pattern

### Main Loop (Every 10 seconds)
- Runs `monitor_positions()` every 10 seconds (CONFIG: `CHECK_INTERVAL_SECONDS = 10`)

### Zerodha API Calls

#### 1. **When Bot Starts (One-time)**
- `kite.profile()` - Get user profile (once at startup)
- `kite.instruments("NFO")` - Get all instruments list (once at startup for expiry calculation)

#### 2. **During Trading Hours (Every 10 seconds)**

**When NO Position:**
- **0 Zerodha calls** - Only Yahoo Finance for Nifty spot price
- Only checks Yahoo Finance: `get_current_price()` to detect breakouts

**When Position ACTIVE:**
- `kite.instruments("NFO")` - Fetch instruments (for symbol lookup) - **1 call**
- `kite.quote("NFO:SYMBOL")` - Get option LTP for exit monitoring - **1 call**
- **Total: 2 Zerodha calls every 10 seconds** while in position

#### 3. **On Trade Entry (When Breakout Detected)**
- `kite.instruments("NFO")` - Fetch instruments (for expiry) - **1 call**
- `kite.instruments("NFO")` - Fetch instruments (for symbol) - **1 call**
- `kite.quote("NFO:SYMBOL")` - Get option price - **1 call**
- `kite.place_order(...)` - Place buy order - **1 call**
- **Total: 4 calls per entry**

#### 4. **On Trade Exit (SL/Target/EOD)**
- `kite.instruments("NFO")` - Fetch instruments (for symbol) - **1 call**
- `kite.quote("NFO:SYMBOL")` - Get current price - **1 call**
- `kite.place_order(...)` - Place sell order - **1 call**
- **Total: 3 calls per exit**

---

## ⚠️ CRITICAL ISSUES IDENTIFIED

### Issue 1: NOT Using Zerodha Position Data
**Current Behavior:**
- Bot tracks positions internally in `trade_state.json`
- Does NOT call `kite.positions()` to verify actual positions
- Relies solely on order placement confirmation

**Risk:**
- If order fails/rejects, bot doesn't know
- If partial fill occurs, bot doesn't know
- If position is manually closed, bot doesn't know
- State mismatch between bot and actual Kite positions

**Function Exists But NOT Used:**
```python
def get_positions(self) -> List[Dict]:
    """Get current positions"""
    positions = self.kite.positions()
    return positions['day']  # Intraday positions
```
❌ This function is NEVER called in the codebase!

---

### Issue 2: Excessive `instruments()` Calls
**Current Behavior:**
- Fetches entire NFO instruments list (~15,000+ instruments) on EVERY:
  - Entry signal
  - Exit check (every 10s when in position)
  - Symbol lookup

**Performance Impact:**
- Each `instruments()` call returns 15MB+ of data
- Called 2 times every 10 seconds when in position = **12 calls/minute**
- Unnecessary network overhead
- Slow response time

**Solution:**
- Cache instruments list (refresh once per day or on-demand)
- Store expiries separately

---

### Issue 3: Not Monitoring Order Status
**Current Behavior:**
- Places order, assumes it's filled
- Doesn't check if order is COMPLETE, REJECTED, or PENDING

**Function Exists But NOT Used:**
```python
def get_order_status(self, order_id: str) -> Optional[Dict]:
    """Get order status"""
    # Returns order details
```
❌ This function is NEVER called after placing orders!

**Risk:**
- Order rejected → Bot thinks it's in position
- Order pending → Bot waits for SL/Target that will never trigger
- Partial fill → Bot doesn't know actual quantity

---

## Request Frequency Summary

| Scenario | Yahoo Finance | Zerodha API | Notes |
|----------|--------------|-------------|-------|
| **No Position** | Every 10s | 0 | Only spot price check |
| **In Position** | Every 10s | 2 calls/10s | LTP monitoring |
| **Entry** | Once | 4 calls | Order placement |
| **Exit** | Once | 3 calls | Order closure |

**Daily Zerodha API Usage (Worst Case):**
- 1 entry + 1 exit per day = 7 calls
- Position monitoring (6 hours * 360 checks) = 720 * 2 = 1,440 calls
- **Total: ~1,450 calls per trading day**

---

## Recommended Improvements

### 1. **Add Position Reconciliation (CRITICAL)**
```python
def reconcile_positions(self):
    """Verify bot state matches Kite positions"""
    kite_positions = self.broker.get_positions()
    
    # Check if bot thinks it has position but Kite doesn't
    if self.current_position and not kite_positions:
        print("⚠️ Position mismatch! Bot has position but Kite doesn't")
        self.reset_position()
    
    # Check if Kite has position but bot doesn't
    if not self.current_position and kite_positions:
        print("⚠️ Unknown position detected in Kite!")
        # Handle accordingly
```

Call this:
- Every 5 minutes during trading hours
- Before placing new orders
- After EOD square-off

---

### 2. **Cache Instruments Data**
```python
class KiteBroker:
    def __init__(self):
        self.instruments_cache = None
        self.cache_timestamp = None
        
    def get_instruments(self, force_refresh=False):
        """Get instruments with caching"""
        # Refresh once per day or on force_refresh
        if not self.instruments_cache or force_refresh:
            self.instruments_cache = self.kite.instruments("NFO")
            self.cache_timestamp = datetime.now()
        return self.instruments_cache
```

**Benefit:** Reduces 1,440 calls/day → ~10 calls/day

---

### 3. **Verify Order Execution**
```python
def place_option_order_verified(self, strike, option_type, quantity):
    """Place order and verify execution"""
    order_id = self.place_option_order(strike, option_type, quantity)
    
    if not order_id:
        return None
    
    # Wait and verify
    time.sleep(2)
    order_status = self.get_order_status(order_id)
    
    if order_status and order_status['status'] == 'COMPLETE':
        return order_id
    else:
        print(f"⚠️ Order {order_id} status: {order_status['status']}")
        return None
```

---

### 4. **Add Rate Limiting**
```python
from time import sleep
from functools import wraps

def rate_limit(calls_per_second=3):
    """Decorator to limit API calls"""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(calls_per_second=2)
def get_option_ltp(self, symbol):
    # ... existing code
```

**Benefit:** Prevents API throttling

---

## Data Sources Currently Used

### Yahoo Finance
- **Symbol:** `^NSEI` (Nifty 50 spot)
- **Usage:** Spot price for breakout detection
- **Frequency:** Every 10 seconds
- **Data:** Current price, Previous day high/low

### Yahoo Finance (VIX)
- **Symbol:** `^INDIAVIX`
- **Usage:** Dynamic SL/Target calculation
- **Frequency:** Once at trade entry
- **Data:** Current VIX percentage

### Zerodha Kite
- **Usage:** 
  - Option chain data (instruments)
  - Option LTP (live price)
  - Order placement/execution
- **NOT Using:**
  - Position data (should use!)
  - Order status verification (should use!)
  - Margin check
  - Holdings/funds

---

## Zerodha API Rate Limits (FYI)

From Kite Connect documentation:
- **Quote API:** 1 request/second for upto 500 instruments
- **Orders API:** 10 requests/second
- **Positions API:** 1 request/second
- **Instruments:** No official limit (but heavy, use sparingly)

**Current Usage:**
- ✅ Orders: Well within limits
- ⚠️ Instruments: Should cache (15MB+ file downloaded repeatedly)
- ❌ Positions: Not being used (should be!)
- ❌ Quote: Could optimize with caching

---

## Action Items

1. ✅ **Implement position reconciliation** - Verify bot state matches Kite
2. ✅ **Cache instruments data** - Reduce API calls by 99%
3. ✅ **Add order status verification** - Ensure orders are filled
4. ⚠️ **Add error handling** - Handle API failures gracefully
5. ⚠️ **Add rate limiting** - Prevent throttling
6. ⚠️ **Add margin check** - Verify sufficient margin before trading

---

**Priority:**
1. Position reconciliation (prevents loss of control)
2. Instruments caching (improves performance)
3. Order verification (ensures accuracy)

**Status:** Analysis complete - improvements needed
**Date:** October 23, 2025
