# Zerodha API Limits vs Our Usage - Gap Analysis
**Date**: October 24, 2025  
**Official Limits**: From https://kite.trade/docs/connect/v3/exceptions/#api-rate-limit

---

## 📋 OFFICIAL ZERODHA API RATE LIMITS

| Endpoint Type | Rate Limit | Additional Notes |
|---------------|------------|------------------|
| **Quote API** | **1 req/second** | Can fetch up to 1000 instruments per call |
| **Historical Candle** | **3 req/second** | - |
| **Order Placement** | **10 req/second** | Max 200/minute, 3000/day |
| **All Other Endpoints** | **10 req/second** | Includes orders, positions, portfolio, margins, etc. |

**Note**: 429 HTTP error indicates rate limiting

---

## 🔍 OUR CURRENT USAGE vs LIMITS

### 1. **QUOTE API** (Limit: 1/second = 3,600/hour)

| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| **When IDLE**: 0-360/hour | 3,600/hour | 0-10% | **90-100% unused** ⚠️ |
| **In POSITION**: 3,600/hour | 3,600/hour | 100% | ✅ **Fully utilized** |

**Current Implementation**:
- Idle: Check every 10s = 360/hour (only Nifty spot from Yahoo)
- In Position: Check every 1s = 3,600/hour (option LTP from Zerodha)

**Opportunities**:
- ⚠️ When idle, we could fetch quotes every 1s instead of relying on Yahoo
- ⚠️ We could batch fetch multiple strikes in single call (up to 1000 instruments)

---

### 2. **ORDER PLACEMENT** (Limit: 10/second, 200/minute)

| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| 2-4 orders/day | 10/sec (36,000/hour) | **0.001%** | **99.999% unused** ⚠️ |

**Current Implementation**:
- Entry: 1 order
- Exit: 1 order
- Total: 2-4 orders/day

**Opportunities**:
- ⚠️ Could place bracket orders (SL + Target as separate orders)
- ⚠️ Could use GTT (Good Till Triggered) orders
- ⚠️ Could implement multiple entry strategies
- ⚠️ Could add trailing stop loss orders

---

### 3. **ALL OTHER ENDPOINTS** (Limit: 10/second = 36,000/hour)

#### A. **Order History** ✅ Using
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| 10/day | 36,000/hour | **0.001%** | **99.999% unused** |

**Current**: Poll 5× per order
**Opportunity**: Could poll more aggressively or check order status more frequently

---

#### B. **Positions** ✅ Using
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| 120/day (2/min) | 36,000/hour | **0.3%** | **99.7% unused** ⚠️ |

**Current**: Check every 30s when in position
**Opportunity**: Could check every 1s (3,600× more frequent!)

---

#### C. **Orders (All)** ❌ NOT USING
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| **0/day** | 36,000/hour | **0%** | **100% unused** ⚠️ |

**Current**: NOT CALLED
**Opportunity**: Could fetch all orders periodically to track order flow

---

#### D. **Trades** ❌ NOT USING
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| **0/day** | 36,000/hour | **0%** | **100% unused** ⚠️ |

**Current**: NOT CALLED
**Opportunity**: Could fetch all trades to analyze execution quality

---

#### E. **Holdings** ❌ NOT USING
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| **0/day** | 36,000/hour | **0%** | **100% unused** |

**Current**: NOT CALLED (N/A for intraday options)

---

#### F. **Margins** ❌ NOT USING
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| **0/day** | 36,000/hour | **0%** | **100% unused** ⚠️ |

**Current**: NOT CALLED
**Opportunity**: Could check available margin before orders

---

#### G. **Instruments** ✅ Using (Cached)
| Our Usage | Limit | Utilization | Gap |
|-----------|-------|-------------|-----|
| 1/day | Unlimited | Minimal | N/A |

**Current**: Cached for 24 hours
**Status**: Optimally used ✅

---

## 🚀 MAJOR OPPORTUNITIES TO USE MORE API CALLS

### **PRIORITY 1: High-Frequency Position Monitoring**

**Current**: `kite.positions()` every 30s (2/min)  
**Limit**: 10/second = 600/minute  
**Opportunity**: **300× more frequent!**

```python
# CURRENT
RECONCILE_INTERVAL = 30  # Every 30 seconds

# COULD BE
RECONCILE_INTERVAL = 1   # Every 1 second = 3,600/hour
```

**Benefits**:
- ✅ Instant detection of position changes
- ✅ Real-time P&L updates
- ✅ Immediate detection of auto-square-offs
- ✅ Faster entry price reconciliation (1s vs 30s)

**API Impact**: 120/day → 3,600/day (still only 0.4% of limit!)

---

### **PRIORITY 2: Batch Quote Fetching**

**Current**: Fetch 1 option at a time  
**Limit**: Can fetch up to 1000 instruments in single call  
**Opportunity**: Fetch multiple strikes simultaneously

```python
# CURRENT - Single Strike
quote = kite.quote("NFO:NIFTY26000CE")

# COULD BE - Multiple Strikes (Same API call!)
quotes = kite.quote([
    "NFO:NIFTY26000CE",  # ATM
    "NFO:NIFTY26050CE",  # ATM+1
    "NFO:NIFTY26100CE",  # ATM+2
    "NFO:NIFTY25950CE",  # ATM-1
    "NFO:NIFTY25900CE",  # ATM-2
    "NFO:NIFTY26000PE",  # ATM PE
    "NFO:NIFTY25950PE",  # ATM-1 PE
])
```

**Benefits**:
- ✅ Better strike selection (see option chain)
- ✅ Hedge opportunities (simultaneous CE/PE)
- ✅ Better entry price (choose best strike)
- ✅ NO additional API calls needed!

---

### **PRIORITY 3: Order Book Monitoring**

**Current**: Not using `kite.orders()`  
**Limit**: 10/second  
**Opportunity**: Monitor all orders every second

```python
def monitor_all_orders(self):
    """Check all orders every second"""
    orders = self.kite.orders()
    
    # Detect:
    # - Pending orders
    # - Rejected orders
    # - Partial fills
    # - Order modifications by exchange
```

**Benefits**:
- ✅ Detect exchange modifications
- ✅ Track partial fills
- ✅ Monitor rejected orders
- ✅ Better order flow visibility

**API Impact**: 3,600/hour (still only 10% of limit!)

---

### **PRIORITY 4: Trade Execution Analysis**

**Current**: Not using `kite.trades()`  
**Limit**: 10/second  
**Opportunity**: Analyze execution quality

```python
def analyze_execution(self):
    """Get all trades and analyze slippage"""
    trades = self.kite.trades()
    
    for trade in trades:
        # Track:
        # - Fill prices vs quotes
        # - Average execution price
        # - Slippage patterns
        # - Execution time
```

**Benefits**:
- ✅ Better slippage analysis
- ✅ Execution quality metrics
- ✅ Multiple fill detection
- ✅ Improved entry/exit timing

**API Impact**: Can call every minute = 1,440/day (minimal!)

---

### **PRIORITY 5: Margin Monitoring**

**Current**: Not checking available margin  
**Limit**: 10/second  
**Opportunity**: Check margin before every order

```python
def get_available_margin(self):
    """Check margin availability"""
    margins = self.kite.margins()
    
    available = margins['equity']['available']['live_balance']
    used = margins['equity']['used']['live_balance']
    
    return available, used
```

**Benefits**:
- ✅ Prevent order rejection due to insufficient funds
- ✅ Know exact available capital
- ✅ Better position sizing
- ✅ Margin utilization tracking

**API Impact**: 2-4 calls/day (before each order)

---

### **PRIORITY 6: Pre-Trade Quote Verification**

**Current**: Check quote 2× before order (500ms gap)  
**Opportunity**: Check 10× in same second (100ms gap)

```python
# CURRENT
ltp1 = get_quote()
time.sleep(0.5)
ltp2 = get_quote()

# COULD BE
ltps = []
for i in range(10):
    ltps.append(get_quote())
    time.sleep(0.1)  # 100ms

# Use median/latest for better entry
```

**Benefits**:
- ✅ Better price discovery
- ✅ Reduced slippage
- ✅ Detect rapid price movements
- ✅ Still within 1/sec limit

---

### **PRIORITY 7: Historical Data Analysis**

**Current**: Not using historical candle API  
**Limit**: 3/second  
**Opportunity**: Analyze option price patterns

```python
def get_option_historical(self, symbol, days=5):
    """Get historical option prices"""
    from_date = datetime.now() - timedelta(days=days)
    to_date = datetime.now()
    
    data = self.kite.historical_data(
        instrument_token=token,
        from_date=from_date,
        to_date=to_date,
        interval="minute"
    )
```

**Benefits**:
- ✅ Option premium decay analysis
- ✅ Better strike selection
- ✅ IV analysis
- ✅ Support/resistance levels

**API Impact**: 3/second limit allows 10,800/hour

---

## 📊 TOTAL UTILIZATION SUMMARY

| Endpoint | Limit (per hour) | Current Usage | % Used | Gap |
|----------|------------------|---------------|--------|-----|
| **Quote** | 3,600 | 0-3,600 | 0-100% | 0-100% idle time |
| **Orders (Place)** | 36,000 | <1 | 0.001% | 99.999% |
| **Orders (History)** | 36,000 | <1 | 0.001% | 99.999% |
| **Orders (All)** | 36,000 | **0** | 0% | 100% |
| **Trades** | 36,000 | **0** | 0% | 100% |
| **Positions** | 36,000 | 120/day | 0.3% | 99.7% |
| **Margins** | 36,000 | **0** | 0% | 100% |
| **Historical** | 10,800 | **0** | 0% | 100% |

---

## 🎯 RECOMMENDED IMPLEMENTATIONS

### **Phase 1: Immediate (Can Implement Now)**

1. ✅ **1-Second Position Reconciliation**
   - Change: `RECONCILE_INTERVAL = 1`
   - Impact: 30× faster position tracking
   - API: 3,600/day (still 0.4% of limit)

2. ✅ **Batch Quote Fetching**
   - Fetch 7 strikes in single call
   - Impact: Better strike selection
   - API: No increase (same calls)

3. ✅ **Margin Check Before Orders**
   - Call `kite.margins()` before order
   - Impact: Prevent rejections
   - API: 2-4/day (negligible)

---

### **Phase 2: Enhanced Monitoring**

4. ✅ **Order Book Monitoring**
   - Check `kite.orders()` every 5 seconds
   - Impact: Better order visibility
   - API: 720/hour (2% of limit)

5. ✅ **Trade Analysis**
   - Fetch `kite.trades()` every minute
   - Impact: Execution quality tracking
   - API: 1,440/day (minimal)

---

### **Phase 3: Advanced Features**

6. ✅ **Historical Analysis**
   - Fetch option history for IV analysis
   - Impact: Better strike selection
   - API: 3/second limit allows extensive analysis

7. ✅ **Multiple Quote Sampling**
   - Sample price 10× per second
   - Impact: Better entry timing
   - API: Still within 1/sec limit (averaged)

---

## 💡 KEY INSIGHTS

### **We are SEVERELY under-utilizing Zerodha's API:**

- **Quote API**: 0-100% used (idle periods wasted)
- **Order APIs**: 0.001% used (99.999% unused)
- **Position API**: 0.3% used (99.7% unused)
- **Other APIs**: 0% used (100% unused)

### **Biggest Opportunities:**

1. 🔥 **Position monitoring**: 30s → 1s (30× faster)
2. 🔥 **Batch quotes**: Get option chain data
3. 🔥 **Order tracking**: Real-time order status
4. 🔥 **Margin checks**: Prevent rejections
5. 🔥 **Trade analysis**: Better execution insights

### **Safe Implementations:**

All recommended changes stay well within rate limits:
- Positions every 1s = 0.4% of limit ✅
- Orders every 5s = 2% of limit ✅
- Trades every 1min = <0.1% of limit ✅
- Margin checks = negligible ✅

---

## 🚀 NEXT STEPS

**Priority order for implementation:**

1. **Immediate**: 1-second position reconciliation (trivial change)
2. **Immediate**: Margin check before orders (prevent rejections)
3. **Short-term**: Batch quote fetching (better strike selection)
4. **Short-term**: Order book monitoring (track order status)
5. **Medium-term**: Trade analysis (execution quality)
6. **Long-term**: Historical analysis (IV-based strategy)

**All implementations will stay well under 10% of Zerodha's rate limits!**

---

**Bottom Line**: We're using <1% of Zerodha's API capacity. We have room to make our bot **100× more aggressive** while staying within limits! 🚀
