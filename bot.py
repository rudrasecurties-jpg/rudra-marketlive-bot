"""
Indian Market Signal Bot
Platform: Railway.app (Free Deploy)
Run: python bot.py
"""

import logging
import os
import asyncio
from datetime import datetime, time as dtime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from dotenv import load_dotenv
import yfinance as yf

# ── Env load karo ─────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")   # @yourchannel  (optional)
ADMIN_ID    = int(os.getenv("ADMIN_ID", "0"))

IST = pytz.timezone("Asia/Kolkata")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Subscribers store (in-memory) ─────────────────────────────────────────────
subscribers: set[int] = set()

# ── Watchlist ─────────────────────────────────────────────────────────────────
WATCHLIST = {
    "NIFTY 50":  "^NSEI",
    "SENSEX":    "^BSESN",
    "RELIANCE":  "RELIANCE.NS",
    "TCS":       "TCS.NS",
    "HDFCBANK":  "HDFCBANK.NS",
    "INFY":      "INFY.NS",
    "BAJFINANCE":"BAJFINANCE.NS",
    "ICICIBANK": "ICICIBANK.NS",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_market_data(symbol: str) -> dict | None:
    """Yahoo Finance se live price fetch karo"""
    try:
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="2d", interval="1d")
        info   = ticker.fast_info

        if hist.empty:
            return None

        price  = round(info.last_price, 2)
        prev   = round(hist["Close"].iloc[-2], 2) if len(hist) >= 2 else price
        change = round(price - prev, 2)
        pct    = round((change / prev) * 100, 2) if prev else 0

        return {
            "price":  price,
            "prev":   prev,
            "change": change,
            "pct":    pct,
        }
    except Exception as e:
        log.warning(f"Data fetch error ({symbol}): {e}")
        return None


def signal_from_data(name: str, data: dict) -> str:
    """Simple signal generate karo price movement se"""
    pct = data["pct"]
    if pct >= 1.5:
        sig, emoji = "STRONG BUY 🟢🟢", "📈"
    elif pct >= 0.3:
        sig, emoji = "BUY 🟢", "📈"
    elif pct <= -1.5:
        sig, emoji = "STRONG SELL 🔴🔴", "📉"
    elif pct <= -0.3:
        sig, emoji = "SELL 🔴", "📉"
    else:
        sig, emoji = "NEUTRAL ⚪", "➡️"

    direction = "▲" if data["change"] >= 0 else "▼"
    now = datetime.now(IST).strftime("%d %b %Y • %I:%M %p")

    return (
        f"{emoji} <b>{name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price:    <code>₹{data['price']}</code>\n"
        f"📊 Change:   <code>{direction} {abs(data['change'])} ({data['pct']}%)</code>\n"
        f"📌 Signal:   <b>{sig}</b>\n"
        f"🕐 Time:     {now}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Educational purpose only. SEBI ke rules follow karo.</i>"
    )


def is_market_open() -> bool:
    """Check karo market open hai ya nahi (IST 9:15 AM – 3:30 PM, Mon–Fri)"""
    now = datetime.now(IST)
    if now.weekday() >= 5:          # Saturday / Sunday
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Signals dekho",   callback_data="signals")],
        [InlineKeyboardButton("🔔 Subscribe karo",  callback_data="sub"),
         InlineKeyboardButton("🔕 Unsubscribe",     callback_data="unsub")],
        [InlineKeyboardButton("📈 Market Status",   callback_data="mstatus")],
        [InlineKeyboardButton("❓ Help",             callback_data="help")],
    ])
    await update.message.reply_html(
        f"🙏 <b>Namaste {user.first_name}!</b>\n\n"
        "📈 <b>Indian Market Signal Bot</b>\n\n"
        "Yeh bot aapko NSE/BSE ke <b>live signals</b> deta hai.\n"
        "Neeche buttons se koi bhi kaam karo 👇",
        reply_markup=kb,
    )


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Data fetch kar raha hoon...")
    text = "<b>📊 LIVE MARKET SIGNALS</b>\n\n"

    for name, sym in WATCHLIST.items():
        data = get_market_data(sym)
        if data:
            text += signal_from_data(name, data) + "\n\n"
        else:
            text += f"❌ <b>{name}</b> — data nahi mila\n\n"

    await msg.edit_text(text, parse_mode="HTML")


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in subscribers:
        await update.message.reply_text("✅ Aap pehle se subscribed hain!")
        return
    subscribers.add(uid)
    await update.message.reply_html(
        "🔔 <b>Subscribe ho gaye!</b>\n\n"
        "Ab aapko market hours mein <b>har ghante</b> signals milenge.\n"
        "Band karne ke liye: /unsubscribe"
    )


async def cmd_unsubscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    subscribers.discard(uid)
    await update.message.reply_text("🔕 Unsubscribe ho gaye. Dobara: /subscribe")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    now    = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")
    await update.message.reply_html(
        f"📡 <b>Market Status: {status}</b>\n"
        f"🕐 {now}\n\n"
        f"⏰ Market Hours: Mon–Fri, 9:15 AM – 3:30 PM IST\n"
        f"👥 Subscribers: {len(subscribers)}"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "📖 <b>Commands List</b>\n\n"
        "/start       — Bot shuru karo\n"
        "/signal      — Abhi ke live signals dekho\n"
        "/subscribe   — Automatic hourly signals ON\n"
        "/unsubscribe — Automatic signals OFF\n"
        "/status      — Market open/closed check karo\n"
        "/help        — Yeh message\n\n"
        "⚠️ <i>Sirf educational purpose. Investment ke liye SEBI-registered advisor lo.</i>"
    )


# ── Inline button handler ──────────────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "signals":
        await q.message.reply_text("⏳ Signals fetch kar raha hoon...")
        fake_update = type("U", (), {"message": q.message, "effective_user": q.from_user})()
        await cmd_signal(fake_update, ctx)

    elif data == "sub":
        uid = q.from_user.id
        if uid in subscribers:
            await q.message.reply_text("✅ Aap pehle se subscribed hain!")
        else:
            subscribers.add(uid)
            await q.message.reply_html(
                "🔔 <b>Subscribe ho gaye!</b>\nHar ghante signals milenge market hours mein."
            )

    elif data == "unsub":
        subscribers.discard(q.from_user.id)
        await q.message.reply_text("🔕 Unsubscribe ho gaye.")

    elif data == "mstatus":
        status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        now    = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")
        await q.message.reply_html(f"📡 <b>Market: {status}</b>\n🕐 {now}")

    elif data == "help":
        await cmd_help(type("U", (), {"message": q.message, "effective_user": q.from_user})(), ctx)


# ── Scheduled broadcast ────────────────────────────────────────────────────────
async def scheduled_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    """Har ghante subscribers ko signal bhejo (market hours mein)"""
    if not is_market_open() or not subscribers:
        return

    log.info(f"Broadcast shuru — {len(subscribers)} subscribers")
    text = "🔔 <b>HOURLY MARKET SIGNALS</b>\n\n"

    for name, sym in list(WATCHLIST.items())[:4]:   # Top 4 stocks broadcast mein
        data = get_market_data(sym)
        if data:
            text += signal_from_data(name, data) + "\n\n"

    for uid in subscribers.copy():
        try:
            await ctx.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
        except Exception as e:
            log.warning(f"Broadcast fail {uid}: {e}")
            subscribers.discard(uid)   # Invalid user hata do


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN set nahi hai! .env file check karo.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands register karo
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("signal",      cmd_signal))
    app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Hourly broadcast schedule karo
    app.job_queue.run_repeating(
        scheduled_broadcast,
        interval=3600,   # Har 3600 seconds = 1 ghanta
        first=10,
    )

    log.info("✅ Bot chal raha hai! Ctrl+C se band karo.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
