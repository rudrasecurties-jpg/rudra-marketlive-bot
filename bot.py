"""
Indian Market Signal Bot — v2.0
Fixes:
  • Channel commands working (effective_message instead of message)
  • TradingView webhook receiver (Flask + threading)
  • RSI + EMA + MACD + Volume confluence for high-accuracy signals
  • Real-time signals — koi fixed interval nahi, signal tabhi aata hai
    jab actual setup milti hai
Platform: Railway.app
"""

import logging, os, threading, json, hashlib, hmac
from datetime import datetime, time as dtime
from flask import Flask, request, abort
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, filters,
)
from dotenv import load_dotenv
import asyncio

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")        # @yourchannel ya -100xxxx
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
TV_SECRET  = os.getenv("TV_SECRET", "mysecret") # TradingView webhook secret
PORT       = int(os.getenv("PORT", "8080"))

IST = pytz.timezone("Asia/Kolkata")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

subscribers: set[int] = set()

# ── Watchlist ─────────────────────────────────────────────────────────────────
WATCHLIST = {
    "NIFTY 50":   "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "SENSEX":     "^BSESN",
    "RELIANCE":   "RELIANCE.NS",
    "TCS":        "TCS.NS",
    "HDFCBANK":   "HDFCBANK.NS",
    "INFY":       "INFY.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "ICICIBANK":  "ICICIBANK.NS",
    "SBIN":       "SBIN.NS",
    "ADANIENT":   "ADANIENT.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
}

# ── Telegram app (global, set in main) ────────────────────────────────────────
tg_app: Application = None


# ══════════════════════════════════════════════════════════════════════════════
# TECHNICAL ANALYSIS — RSI + EMA + MACD + Volume
# ══════════════════════════════════════════════════════════════════════════════

def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def compute_macd(series: pd.Series):
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return round(float(macd.iloc[-1]), 4), \
           round(float(signal.iloc[-1]), 4), \
           round(float(hist.iloc[-1]), 4)


def analyze(symbol: str) -> dict | None:
    """
    Multi-indicator confluence analysis.
    Signals sirf tab deta hai jab 3+ indicators agree karein.
    Returns: dict with signal, confidence, entry, target, sl — ya None
    """
    try:
        df = yf.download(symbol, period="60d", interval="15m",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 50:
            # 15m data nahi mila, try daily
            df = yf.download(symbol, period="1y", interval="1d",
                             progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            return None

        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()

        # ── Indicators ────────────────────────────────────────────────────────
        rsi      = compute_rsi(close)
        ema9     = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
        ema21    = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50    = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        macd_v, macd_sig, macd_hist = compute_macd(close)

        # Volume surge (current vs 20-period avg)
        vol_avg   = float(volume.rolling(20).mean().iloc[-1])
        vol_curr  = float(volume.iloc[-1])
        vol_surge = (vol_curr / vol_avg) if vol_avg > 0 else 1.0

        price       = round(float(close.iloc[-1]), 2)
        prev_close  = round(float(close.iloc[-2]), 2)
        day_change  = round(((price - prev_close) / prev_close) * 100, 2)

        # ── ATR for SL/Target ─────────────────────────────────────────────────
        tr = pd.DataFrame({
            "hl": high - low,
            "hc": (high - close.shift()).abs(),
            "lc": (low  - close.shift()).abs(),
        }).max(axis=1)
        atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)

        # ── Confluence Scoring ────────────────────────────────────────────────
        bull_score = 0
        bear_score = 0
        reasons    = []

        # RSI
        if rsi < 35:
            bull_score += 2
            reasons.append(f"RSI Oversold ({rsi})")
        elif rsi < 45:
            bull_score += 1
            reasons.append(f"RSI Weak ({rsi})")
        elif rsi > 65:
            bear_score += 2
            reasons.append(f"RSI Overbought ({rsi})")
        elif rsi > 55:
            bear_score += 1
            reasons.append(f"RSI Strong ({rsi})")

        # EMA alignment
        if ema9 > ema21 > ema50:
            bull_score += 2
            reasons.append("EMA Bullish Alignment (9>21>50)")
        elif ema9 < ema21 < ema50:
            bear_score += 2
            reasons.append("EMA Bearish Alignment (9<21<50)")
        elif price > ema21:
            bull_score += 1
            reasons.append("Price above EMA21")
        elif price < ema21:
            bear_score += 1
            reasons.append("Price below EMA21")

        # MACD
        if macd_v > macd_sig and macd_hist > 0:
            bull_score += 2
            reasons.append("MACD Bullish Crossover")
        elif macd_v < macd_sig and macd_hist < 0:
            bear_score += 2
            reasons.append("MACD Bearish Crossover")

        # Volume confirmation
        if vol_surge >= 1.5:
            if bull_score > bear_score:
                bull_score += 1
                reasons.append(f"Volume Surge {vol_surge:.1f}x ✔")
            else:
                bear_score += 1
                reasons.append(f"Volume Surge {vol_surge:.1f}x ✔")

        # Price momentum
        if day_change >= 0.5:
            bull_score += 1
        elif day_change <= -0.5:
            bear_score += 1

        total_score = bull_score + bear_score
        if total_score == 0:
            return None

        # ── Signal decision — only if strong confluence ────────────────────────
        # Need at least score 4 (out of possible ~8) for high confidence
        if bull_score >= 4:
            direction  = "BUY"
            confidence = min(95, 60 + (bull_score * 5))
            entry      = price
            target     = round(price + (atr * 2.5), 2)
            sl         = round(price - (atr * 1.2), 2)
            rr         = round((target - entry) / (entry - sl), 2) if entry != sl else 0
        elif bear_score >= 4:
            direction  = "SELL"
            confidence = min(95, 60 + (bear_score * 5))
            entry      = price
            target     = round(price - (atr * 2.5), 2)
            sl         = round(price + (atr * 1.2), 2)
            rr         = round((entry - target) / (sl - entry), 2) if entry != sl else 0
        else:
            # No clear signal — skip
            return None

        return {
            "direction":  direction,
            "confidence": confidence,
            "entry":      entry,
            "target":     target,
            "sl":         sl,
            "rr":         rr,
            "rsi":        rsi,
            "ema9":       round(ema9, 2),
            "ema21":      round(ema21, 2),
            "macd_hist":  macd_hist,
            "vol_surge":  round(vol_surge, 2),
            "day_change": day_change,
            "atr":        atr,
            "reasons":    reasons,
            "price":      price,
            "bull_score": bull_score,
            "bear_score": bear_score,
        }

    except Exception as e:
        log.error(f"analyze() error {symbol}: {e}")
        return None


def format_signal(name: str, sym: str, a: dict, source: str = "Auto Scan") -> str:
    emoji     = "🟢" if a["direction"] == "BUY" else "🔴"
    conf_bar  = "█" * (a["confidence"] // 10) + "░" * (10 - a["confidence"] // 10)
    reasons_s = "\n".join(f"    • {r}" for r in a["reasons"])
    now       = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")

    return (
        f"{emoji} <b>{a['direction']} SIGNAL — {name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Confidence:</b> <code>{a['confidence']}%</code>  {conf_bar}\n"
        f"📌 <b>Source:</b> {source}\n\n"
        f"💰 <b>Entry:</b>    <code>₹{a['entry']}</code>\n"
        f"🎯 <b>Target:</b>   <code>₹{a['target']}</code>\n"
        f"🛑 <b>Stop Loss:</b><code>₹{a['sl']}</code>\n"
        f"⚖️ <b>R:R Ratio:</b> <code>{a['rr']}:1</code>\n\n"
        f"📊 <b>Indicators:</b>\n"
        f"    RSI: <code>{a['rsi']}</code> | "
        f"EMA9: <code>{a['ema9']}</code> | EMA21: <code>{a['ema21']}</code>\n"
        f"    MACD Hist: <code>{a['macd_hist']}</code> | "
        f"Vol: <code>{a['vol_surge']}x</code>\n\n"
        f"✅ <b>Reasons:</b>\n{reasons_s}\n\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Educational only. SEBI rules follow karo.</i>"
    )


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


# ══════════════════════════════════════════════════════════════════════════════
# REPLY HELPER — channel + private dono handle karta hai
# ══════════════════════════════════════════════════════════════════════════════

async def reply(update: Update, text: str, **kwargs):
    """
    Channel mein update.message None hota hai.
    effective_message hamesha available hota hai.
    """
    msg = update.effective_message
    if msg:
        await msg.reply_html(text, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Trader"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Live Signals",    callback_data="signals")],
        [InlineKeyboardButton("🔔 Subscribe",       callback_data="sub"),
         InlineKeyboardButton("🔕 Unsubscribe",     callback_data="unsub")],
        [InlineKeyboardButton("📈 Market Status",   callback_data="mstatus")],
        [InlineKeyboardButton("❓ Help",             callback_data="help")],
    ])
    await reply(update,
        f"🙏 <b>Namaste {name}!</b>\n\n"
        "📈 <b>Indian Market Signal Bot v2.0</b>\n\n"
        "✅ <b>Features:</b>\n"
        "• RSI + EMA + MACD + Volume confluence\n"
        "• TradingView webhook real-time alerts\n"
        "• High-accuracy signals (conf. 70%+)\n"
        "• Channel + Private dono mein kaam karta hai\n\n"
        "👇 Button se select karo:",
        reply_markup=kb,
    )


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    wait = await msg.reply_text("⏳ Live data + technical analysis kar raha hoon...")
    found = []

    for name, sym in WATCHLIST.items():
        a = analyze(sym)
        if a:
            found.append((name, sym, a))

    if not found:
        await wait.edit_text(
            "⚪ Abhi koi strong signal nahi hai.\n"
            "Market mein clarity nahi — sideline rehna best hai.\n\n"
            "Thodi der baad try karo ya /subscribe karo."
        )
        return

    await wait.delete()
    for name, sym, a in found:
        await msg.reply_html(format_signal(name, sym, a, "Manual Scan"))


async def cmd_subscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    uid = user.id
    if uid in subscribers:
        await reply(update, "✅ Aap pehle se subscribed hain!")
        return
    subscribers.add(uid)
    await reply(update,
        "🔔 <b>Subscribe ho gaye!</b>\n\n"
        "Signals real-time aayenge jab bhi strong setup milega.\n"
        "Koi fixed time nahi — sirf genuine signals.\n\n"
        "Band karne ke liye: /unsubscribe"
    )


async def cmd_unsubscribe(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        subscribers.discard(user.id)
    await reply(update, "🔕 Unsubscribe ho gaye.\nDobara: /subscribe")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    now    = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")
    await reply(update,
        f"📡 <b>Market Status: {status}</b>\n"
        f"🕐 {now}\n\n"
        f"⏰ Hours: Mon–Fri, 9:15 AM – 3:30 PM IST\n"
        f"👥 Subscribers: <code>{len(subscribers)}</code>\n"
        f"📡 Webhook: Active (TradingView ready)"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await reply(update,
        "📖 <b>Commands</b>\n\n"
        "/start       — Bot shuru karo\n"
        "/signal      — Abhi scan karo (manual)\n"
        "/subscribe   — Real-time alerts ON\n"
        "/unsubscribe — Alerts OFF\n"
        "/status      — Market + bot status\n"
        "/help        — Yeh message\n\n"
        "🔔 <b>Auto Signals:</b>\n"
        "Subscribe karo — jab bhi RSI+EMA+MACD+Volume\n"
        "confluence milti hai, signal aayega.\n\n"
        "📡 <b>TradingView:</b>\n"
        "Webhook URL: <code>https://YOUR-URL/webhook</code>\n\n"
        "⚠️ <i>Educational only. SEBI rules follow karo.</i>"
    )


# ── Button callbacks ───────────────────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "signals":
        await q.message.reply_text("⏳ Scanning...")
        found = []
        for name, sym in WATCHLIST.items():
            a = analyze(sym)
            if a:
                found.append((name, sym, a))
        if not found:
            await q.message.reply_text("⚪ Koi strong signal nahi abhi. Thodi der baad try karo.")
        else:
            for name, sym, a in found:
                await q.message.reply_html(format_signal(name, sym, a, "Button Scan"))

    elif q.data == "sub":
        uid = q.from_user.id
        if uid in subscribers:
            await q.message.reply_text("✅ Pehle se subscribed hain!")
        else:
            subscribers.add(uid)
            await q.message.reply_html(
                "🔔 <b>Subscribed!</b>\nReal-time signals milenge jab setup milega."
            )

    elif q.data == "unsub":
        subscribers.discard(q.from_user.id)
        await q.message.reply_text("🔕 Unsubscribed.")

    elif q.data == "mstatus":
        status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        now    = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")
        await q.message.reply_html(f"📡 <b>Market: {status}</b>\n🕐 {now}")

    elif q.data == "help":
        await q.message.reply_html(
            "📖 <b>Commands</b>\n\n"
            "/signal — Manual scan\n/subscribe — Auto alerts\n/status — Status"
        )


# ── Scheduled scanner — koi fixed interval nahi, confluence milne par hi ──────
async def smart_scan(ctx: ContextTypes.DEFAULT_TYPE):
    """
    Har 5 minute mein scan karo.
    Signal sirf tabhi bhejo jab confidence >= 70%
    Subscribers + channel dono ko bhejo.
    """
    if not is_market_open():
        return

    for name, sym in WATCHLIST.items():
        a = analyze(sym)
        if not a or a["confidence"] < 70:
            continue

        text = format_signal(name, sym, a, "Auto Scan 🔍")

        # Channel ko bhejo
        if CHANNEL_ID:
            try:
                await ctx.bot.send_message(
                    chat_id=CHANNEL_ID, text=text, parse_mode="HTML"
                )
            except Exception as e:
                log.warning(f"Channel send fail: {e}")

        # Subscribers ko bhejo
        for uid in subscribers.copy():
            try:
                await ctx.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            except Exception as e:
                log.warning(f"Subscriber {uid} fail: {e}")
                subscribers.discard(uid)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK WEBHOOK — TradingView alerts receive karna
# ══════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)


@flask_app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "bot": "Indian Market Signal Bot v2.0"}, 200


@flask_app.route("/webhook", methods=["POST"])
def tradingview_webhook():
    """
    TradingView se alert aata hai yahan.
    
    TradingView Alert Message format (JSON):
    {
      "secret": "mysecret",
      "symbol": "RELIANCE",
      "action": "BUY",
      "price": 2850,
      "target": 2920,
      "sl": 2810,
      "timeframe": "15m",
      "message": "RSI Oversold + EMA Cross"
    }
    """
    try:
        data = request.get_json(force=True)
        if not data:
            abort(400)

        # Secret check karo
        if data.get("secret") != TV_SECRET:
            log.warning("Webhook: Wrong secret")
            abort(403)

        symbol   = data.get("symbol", "UNKNOWN")
        action   = data.get("action", "BUY").upper()
        price    = float(data.get("price", 0))
        target   = float(data.get("target", 0))
        sl       = float(data.get("sl", 0))
        tf       = data.get("timeframe", "15m")
        tv_msg   = data.get("message", "TradingView Alert")
        conf     = int(data.get("confidence", 80))

        rr = round((abs(target - price) / abs(price - sl)), 2) if price != sl else 0
        emoji = "🟢" if action == "BUY" else "🔴"
        now   = datetime.now(IST).strftime("%d %b %Y • %I:%M %p IST")

        text = (
            f"📡 <b>TRADINGVIEW ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{action} — {symbol}</b>\n"
            f"⏱ Timeframe: <code>{tf}</code>\n"
            f"🎯 Confidence: <code>{conf}%</code>\n\n"
            f"💰 Entry:    <code>₹{price}</code>\n"
            f"🎯 Target:   <code>₹{target}</code>\n"
            f"🛑 SL:       <code>₹{sl}</code>\n"
            f"⚖️ R:R:      <code>{rr}:1</code>\n\n"
            f"📝 {tv_msg}\n\n"
            f"🕐 {now}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>Educational only.</i>"
        )

        # Async context mein bhejo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def send_all():
            if CHANNEL_ID and tg_app:
                try:
                    await tg_app.bot.send_message(
                        chat_id=CHANNEL_ID, text=text, parse_mode="HTML"
                    )
                except Exception as e:
                    log.warning(f"TV webhook channel fail: {e}")
            for uid in subscribers.copy():
                try:
                    if tg_app:
                        await tg_app.bot.send_message(
                            chat_id=uid, text=text, parse_mode="HTML"
                        )
                except Exception as e:
                    log.warning(f"TV webhook user {uid} fail: {e}")

        loop.run_until_complete(send_all())
        loop.close()

        log.info(f"TV Webhook processed: {symbol} {action}")
        return {"status": "sent"}, 200

    except Exception as e:
        log.error(f"Webhook error: {e}")
        return {"error": str(e)}, 500


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    global tg_app

    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN set nahi hai!")

    tg_app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    tg_app.add_handler(CommandHandler("start",       cmd_start))
    tg_app.add_handler(CommandHandler("signal",      cmd_signal))
    tg_app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    tg_app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    tg_app.add_handler(CommandHandler("status",      cmd_status))
    tg_app.add_handler(CommandHandler("help",        cmd_help))
    tg_app.add_handler(CallbackQueryHandler(button_handler))

    # Smart scan — har 5 minute mein (sirf market hours mein kaam karega)
    tg_app.job_queue.run_repeating(smart_scan, interval=300, first=30)

    # Flask webhook — alag thread mein
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log.info(f"✅ Webhook server port {PORT} par ready!")

    log.info("✅ Bot polling shuru!")
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
