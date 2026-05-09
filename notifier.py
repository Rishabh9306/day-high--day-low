"""
Telegram notification module for the Nifty 50 Breakout Trading Bot.

Uses Python's built-in urllib — zero external dependencies.
All calls are fire-and-forget: a failed notification will NEVER crash the bot.
"""
import urllib.request
import urllib.parse
import config


def send_telegram(message: str):
    """
    Send a message to Telegram. Fails silently (never crashes the bot).
    """
    if not config.ENABLE_TELEGRAM:
        return

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }).encode()

        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Never let notifications crash the bot


def notify_breakout(direction: str, current_price: float, level: float):
    """Breakout detected — before order placement"""
    emoji = "🚀" if direction == "HIGH" else "📉"
    send_telegram(
        f"{emoji} <b>{direction} BREAKOUT DETECTED</b>\n\n"
        f"Nifty: ₹{current_price}\n"
        f"Level: ₹{level}\n"
        f"Action: Entering {('CE' if direction == 'HIGH' else 'PE')} trade..."
    )


def notify_entry(option_type: str, strike: int, entry_price: float,
                 sl: float, target: float, quantity: int):
    """Order filled — position entered"""
    send_telegram(
        f"✅ <b>ORDER FILLED — {option_type} {strike}</b>\n\n"
        f"Entry: ₹{entry_price:.2f}\n"
        f"Qty: {quantity}\n"
        f"SL: ₹{sl:.2f}\n"
        f"Target: ₹{target:.2f}"
    )


def notify_trailing_sl(profit_pct: float, old_sl: float, new_sl: float,
                       step_threshold: int, step_lock: int):
    """Trailing SL moved up"""
    send_telegram(
        f"📈 <b>TRAILING SL MOVED</b>\n\n"
        f"Profit: +{profit_pct:.1f}%\n"
        f"Step: +{step_threshold}% → Lock +{step_lock}%\n"
        f"SL: ₹{old_sl:.2f} → ₹{new_sl:.2f}"
    )


def notify_trailing_exit(profit_pct: float, exit_price: float):
    """Trailing SL triggered hard exit at final step"""
    send_telegram(
        f"🎯 <b>TSL HARD EXIT — +{profit_pct:.1f}%</b>\n\n"
        f"Price crossed final TSL threshold\n"
        f"Exiting at ₹{exit_price:.2f}"
    )


def notify_exit(option_type: str, strike: int, entry_price: float,
                exit_price: float, pnl_pct: float, pnl_amount: float,
                reason: str):
    """Position exited"""
    emoji = "💰" if pnl_amount > 0 else "🔴"
    send_telegram(
        f"{emoji} <b>POSITION CLOSED — {reason}</b>\n\n"
        f"{option_type} {strike}\n"
        f"Entry: ₹{entry_price:.2f}\n"
        f"Exit: ₹{exit_price:.2f}\n"
        f"P&L: {pnl_pct:+.1f}% (₹{pnl_amount:+,.0f})"
    )


def notify_bot_started(prev_high: float, prev_low: float,
                       sl_pct: int, target_pct: int):
    """Bot started for the day"""
    send_telegram(
        f"🤖 <b>BOT STARTED</b>\n\n"
        f"Prev High: ₹{prev_high}\n"
        f"Prev Low: ₹{prev_low}\n"
        f"SL: {sl_pct}% | Target: {target_pct}%\n"
        f"TSL: {'ON' if config.ENABLE_TRAILING_SL else 'OFF'}"
    )


def notify_error(error_msg: str):
    """Critical error notification"""
    send_telegram(f"🚨 <b>BOT ERROR</b>\n\n{error_msg[:500]}")
