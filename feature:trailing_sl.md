# **Trailing Stop-Loss Strategy (20% Activation)**

This document outlines the logic and execution process for a momentum-based trading strategy focused on profit protection.  
The core principle is to activate a tight, aggressive trailing stop-loss only after the trade has secured a significant profit, thereby maximizing potential return while securing gains.

---

## **1. Key Variables**

| **Variable** | **Description** | **Value** | **Type** |
|---------------|-----------------|------------|-----------|
| **Entry Price (EP)** | The price at which the asset was purchased. | N/A | Price |
| **Initial Stop-Loss (SL)** | The original fixed stop-loss set upon entry (risk management). | 10% below EP | Percentage/Price |
| **Profit Activation Threshold** | The required profit percentage to begin trailing. | 20% | Percentage |
| **Trailing Stop Percentage** | The distance the stop-loss trails behind the highest price. | 10% | Percentage |
| **Trailing Stop-Loss (TSL)** | The dynamic stop-loss, calculated while active. | Dynamic | Price |
| **High Water Mark (HWM)** | The highest price the asset has reached since activation. | Dynamic | Price |

---

## **2. Strategy Logic**

The strategy operates in three distinct phases: **Setup**, **Activation**, and **Trailing/Exit**.

---

### **Phase 1: Setup**
- **Entry:** Execute the long trade at the Entry Price (EP).  
- **Initial Risk Management:** Immediately set a fixed Initial Stop-Loss (SL) at `EP × 0.90`. The trailing stop-loss is inactive.  
- **Monitoring:** The system monitors the Current Price (CP) against the Initial SL and the Profit Activation Threshold.

---

### **Phase 2: Activation**
The activation phase begins when the 20% profit threshold is met.

- **Check:** Is the Current Price (CP) ≥ Entry Price (EP) × 1.20?  
- **Initial Action:** If **YES**, the **Trailing Stop-Loss (TSL)** is **activated**.  
  - The **High Water Mark (HWM)** is immediately set to the current price (CP).  
  - The first TSL is calculated:  
    `TSL = HWM × (1 - 0.10)` → `HWM × 0.90`.  
- **Risk Replacement:** Once activated, the Initial SL is now irrelevant. The TSL becomes the only stop-loss mechanism.

---

### **Phase 3: Trailing and Exit**
Once active, the system aggressively trails the price using the 10% distance.

- **New High Check:** Is the Current Price (CP) > High Water Mark (HWM)?  
  - **YES (New High):** The market is moving in our favor.  
    - Update `HWM = Current Price (CP)`.  
    - Recalculate `TSL = New HWM × 0.90`. (The stop is moved up.)  
  - **NO (Pullback/Consolidation):** The HWM and the TSL remain unchanged. (The stop is held.)  
- **Exit Condition:** Is the Current Price (CP) ≤ Trailing Stop-Loss (TSL)?  
  - **YES:** The price has fallen 10% or more from its peak since activation. The trade is immediately **closed** to lock in the secured profit.  
  - **NO:** The trade remains open, continuing the monitoring and trailing loop.

---

## **3. Calculation Example**

| **Action/State** | **Current Price (CP)** | **Entry Price (EP)** | **HWM** | **TSL (HWM × 0.90)** | **Result** |
|------------------|-----------------------:|---------------------:|--------:|---------------------:|-------------|
| **Entry** | $100.00 | $100.00 | N/A | N/A | Initial SL is set at $90.00. |
| **Activation** | $120.00 | $100.00 | $120.00 | $108.00 | Trailing Activated (20% Profit). |
| **Trailing 1** | $130.00 | $100.00 | $130.00 | $117.00 | New High, TSL moves up. |
| **Trailing 2** | $125.00 | $100.00 | $130.00 | $117.00 | Price dropped, but > $117.00. TSL holds. |
| **Trailing 3** | $140.00 | $100.00 | $140.00 | $126.00 | New High, TSL moves up. |
| **Exit** | $125.90 | $100.00 | $140.00 | $126.00 | TSL HIT. Trade closed at $126.00, locking in 26% profit. |

---
