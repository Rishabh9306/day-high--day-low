# API Calls Analysis - Complete Breakdown
**Date**: October 24, 2025  
**Branch**: vix-integration

---

## ✅ ZERODHA KITE CONNECT API CALLS

### 1. **INITIALIZATION** (Once at startup)
| Method | Endpoint | When Called | Frequency |
|--------|----------|-------------|-----------|
| `kite.profile()` | User Profile | Bot startup | 1× per session |
| `kite.instruments("NFO")` | Instruments List | First call or 8:30 AM | **1× per day** (cached) ✅ |

---

### 2. **POSITION MONITORING** (During Trading Hours)

#### A. **Option Price Quotes** ✅ YES - USING ZERODHA
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `kite.quote(f"NFO:{symbol}")` | Every monitoring cycle | **1/second when in position** ✅ |
|  | Called in: `get_option_ltp()` | 10/second when idle |
|  | Used by: `check_exit_conditions()` | Check SL/Target |
|  | Used by: `enter_trade()` | Get entry price |
|  | Used by: `place_option_order_verified()` | Pre-order verification (2 calls) |

**Where used:**
- ✅ Line 168: `broker.get_option_ltp(symbol)` - Before entry
- ✅ Line 310: `broker.get_option_ltp(symbol)` - Exit monitoring
- ✅ Line 430: `broker.get_option_ltp(symbol)` - End of day
- ✅ Line 289 (in `place_option_order_verified`): Fresh quote before order

**API Usage**: Up to **3600 calls/hour** when in position (1/second) ✅

---

#### B. **Position Data from Zerodha** ✅ YES - RECONCILING POSITIONS
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `kite.positions()` | Every 30 seconds when in position | **120 calls/day** ✅ |
|  | Called in: `reconcile_position()` | Position reconciliation |
|  | Used by: `check_exit_conditions()` | Verify actual entry price |

**Where used:**
- ✅ Line 335: `broker.reconcile_position(symbol)` - Called every 30s
- ✅ Line 395 in kite_broker.py: `self.kite.positions()` - Gets net positions
- ✅ Compares actual entry price with bot's entry price
- ✅ Auto-corrects if mismatch detected

**API Usage**: **2 calls/minute** when in position ✅

---

### 3. **ORDER MANAGEMENT**

#### A. **Order Placement** ✅ YES - PLACING ORDERS
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `kite.place_order()` | Entry/Exit signals | **2-4/day** (1 entry, 1 exit per trade) |
|  | Called in: `place_option_order()` | Buy order |
|  | Called in: `exit_position()` | Sell order |

**Where used:**
- ✅ Line 208: Entry order placement
- ✅ Line 336: Exit order placement

**API Usage**: **2-4 calls/day** ✅

---

#### B. **Order Verification** ✅ YES - VERIFYING FILLS
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `kite.order_history(order_id)` | After every order placement | **5 attempts × 2 orders = 10/day** |
|  | Called in: `verify_order_fill()` | Polls 5× with 200ms gap |
|  | Used by: `place_option_order_verified()` | Get actual fill price |

**Where used:**
- ✅ Line 244: `self.kite.order_history(order_id)` - Poll for fill status
- ✅ Extracts `average_price` from order details
- ✅ Returns actual fill price within 1 second

**API Usage**: **10 calls/day** (5 per order × 2 orders) ✅

---

#### C. **Order Status** (Legacy - Not Used Currently)
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `kite.orders()` | ❌ NOT CALLED | 0/day |
|  | Method exists but unused | - |

**Where defined:**
- Line 361: `get_order_status()` method exists but **NEVER CALLED**

---

### 4. **INSTRUMENTS & SYMBOLS**

#### A. **Instrument Lookup** ✅ USING CACHED DATA
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `get_instruments("NFO")` | Before every order/quote | Uses cache - **1 API call/day** ✅ |
|  | Called in: `get_option_symbol()` | Symbol lookup |
|  | Called in: `get_nearest_expiry()` | Expiry lookup |

**Where used:**
- ✅ Line 89: `instruments = self.get_instruments("NFO")` - Uses cache
- ✅ Line 127: `instruments = self.get_instruments("NFO")` - Uses cache
- ✅ Cache refreshes only once at 8:30 AM

**API Usage**: **1 call/day** (rest served from cache) ✅

---

## ✅ YAHOO FINANCE API CALLS

### 1. **PREVIOUS DAY HIGH/LOW** ✅ YES - USING YAHOO
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `yf.Ticker(^NSEI).history()` | Day initialization (before 9:15 AM) | **1× per day** |
|  | Called in: `get_previous_day_high_low()` | Fetch historical data |
|  | Used by: `initialize_day()` | Set prev_high, prev_low |

**Where used:**
- ✅ Line 27-28 in data_fetcher.py: Fetch 5 days of data
- ✅ Filters to get yesterday's completed data
- ✅ Called once at market open

**API Usage**: **1 call/day** ✅

---

### 2. **CURRENT NIFTY PRICE** ✅ YES - USING YAHOO
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `yf.Ticker(^NSEI).history()` | Every monitoring cycle | **Up to 360/hour** (every 10s idle) |
|  | Called in: `get_current_price()` | Current spot price |
|  | Used by: `check_entry_conditions()` | Breakout detection |
|  | Used by: `print_status()` | Display current price |

**Where used:**
- ✅ Line 66-69 in data_fetcher.py: Get 1-minute data
- ✅ Line 389 in trade_manager.py: Check breakout levels
- ✅ Called in main loop for status display

**API Usage**: **360 calls/hour** (every 10 seconds) ✅

---

### 3. **INDIA VIX** ✅ YES - USING YAHOO
| Method | When Called | Frequency |
|--------|-------------|-----------|
| `yf.Ticker(^INDIAVIX).history()` | On entry + reconciliation | **2-3/day** |
|  | Called in: `get_india_vix()` | Fetch VIX for SL/Target |
|  | Used by: `enter_trade()` | Calculate dynamic SL/Target |
|  | Used by: `reconcile_position()` | Recalculate if entry mismatch |

**Where used:**
- ✅ Line 109-112 in data_fetcher.py: Fetch current VIX
- ✅ Line 182 in trade_manager.py: Entry calculation
- ✅ Line 355 in trade_manager.py: Reconciliation recalculation

**API Usage**: **2-3 calls/day** ✅

---

## 📊 COMPLETE API USAGE SUMMARY

### **ZERODHA KITE CONNECT**

| API Call | Daily Frequency | Rate Limit | Status |
|----------|----------------|------------|--------|
| **Profile** | 1 | 10/sec | ✅ OK |
| **Instruments (NFO)** | 1 (cached) | Unlimited | ✅ OPTIMIZED |
| **Quote (Options LTP)** | 3,600 - 21,600 | 1/sec | ✅ Within limit |
| **Positions** | 120 | 10/sec | ✅ Within limit |
| **Place Order** | 2-4 | 10/sec | ✅ Within limit |
| **Order History** | 10 | 10/sec | ✅ Within limit |
| **TOTAL ZERODHA** | **~25,000/day** | - | ✅ **All within limits** |

---

### **YAHOO FINANCE**

| API Call | Daily Frequency | Purpose |
|----------|----------------|---------|
| **Previous Day Data** | 1 | Day initialization |
| **Current Nifty Price** | 360/hour = 2,160/day | Breakout detection |
| **India VIX** | 2-3 | Dynamic SL/Target |
| **TOTAL YAHOO** | **~2,165/day** | - |

---

## 🔍 CRITICAL VERIFICATION

### ✅ **ARE WE REQUESTING DATA FROM ZERODHA?**
**YES!** We are making the following calls:

1. ✅ **Instruments**: 1/day (cached)
2. ✅ **Quotes**: 3,600-21,600/day (1/sec when in position)
3. ✅ **Positions**: 120/day (every 30s when in position)
4. ✅ **Orders**: 2-4/day (entry + exit)
5. ✅ **Order History**: 10/day (verification)

---

### ✅ **ARE WE TAKING POSITION DATA FROM ZERODHA?**
**YES!** Implemented on Oct 23, 2025:

**Method**: `reconcile_position(symbol)` in kite_broker.py (Line 388-417)

**What it does**:
1. ✅ Calls `kite.positions()` every 30 seconds
2. ✅ Fetches `net` positions from Zerodha
3. ✅ Compares `average_price` with bot's `entry_price`
4. ✅ If mismatch > ₹0.50, auto-corrects SL/Target
5. ✅ Logs real-time P&L from Zerodha

**Called from**: `check_exit_conditions()` in trade_manager.py (Line 307)

**Frequency**: Every 30 seconds when in position (120 calls/day)

---

## 🎯 KEY IMPROVEMENTS SINCE OCT 23

### Before Optimization:
❌ Instruments: 1,440 calls/day  
❌ No order verification  
❌ No position reconciliation  
❌ No actual fill price  
❌ 10-second monitoring only  

### After Optimization:
✅ Instruments: **1 call/day** (99.9% reduction)  
✅ Order verification: **10 calls/day** (actual fill price)  
✅ Position reconciliation: **120 calls/day** (every 30s)  
✅ Actual fill price: **Verified within 1s**  
✅ Monitoring: **1-second when in position** (10× faster)  

---

## 📈 API USAGE BY TIME

### **Market Open (9:00-9:15 AM)**
- Yahoo: Previous day data (1 call)
- Zerodha: Instruments cache (1 call)
- Yahoo: VIX fetch (1 call)

### **Idle (No Position)**
- Yahoo: Current price every 10s (360/hour)
- Zerodha: Quotes for breakout check (0-360/hour)

### **In Position (1-6 hours)**
- Zerodha: Option quotes every 1s (3,600/hour)
- Zerodha: Positions every 30s (120/hour)
- Yahoo: Current price every 10s (360/hour)

### **Entry/Exit Events**
- Zerodha: Quote pre-order (2 calls)
- Zerodha: Order placement (1 call)
- Zerodha: Order verification (5 calls)
- Yahoo: VIX for SL/Target (1 call)

### **End of Day (3:15 PM)**
- Zerodha: Exit order (1 call)
- Zerodha: Order verification (5 calls)

---

## ✅ CONCLUSION

**YES to both questions:**

1. ✅ **We ARE requesting data from Zerodha**
   - Quotes: Real-time option prices
   - Positions: Actual holdings & P&L
   - Orders: Placement & verification
   - Instruments: Symbol lookup (cached)

2. ✅ **We ARE taking position data from Zerodha**
   - Reconciliation every 30 seconds
   - Actual entry price verification
   - Real-time P&L tracking
   - Auto-correction if mismatch

**All API calls are within official Zerodha rate limits!** ✅
