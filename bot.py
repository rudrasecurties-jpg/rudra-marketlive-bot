"""
RUDRA SECURITIES — Indian Market Signal Bot v6.0

ROOT CAUSE FIXES:
  1. asyncio loop bug fix — Flask thread se Telegram message properly bheja
  2. /test command — koi bhi time pe kaam karta hai, market hours nahi chahiye  
  3. TradingView webhook — sahi se receive + forward
  4. Bot private chat mein kaam karta hai — channel mein sirf post hota hai
  5. Agar kuch bhi nahi aata — /test se confirm karo bot live hai ya nahi

Platform: Railway.app
"""

import logging, os, threading, asyncio, random
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)
from dotenv import load_dotenv

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
load_dotenv()

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
TV_SECRET  = os.getenv("TV_SECRET", "rudra123")
PORT       = int(os.getenv("PORT", "8080"))

IST = ZoneInfo("Asia/Kolkata")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Global refs ────────────────────────────────────────────────────────────────
tg_app: Application = None
main_loop: asyncio.AbstractEventLoop = None   # Main thread ka event loop
last_signal: dict = {}

INDICES = {
    "NIFTY":     {"yf": "^NSEI",    "step": 50,  "lot": 75,
                  "prem_min": 80,  "prem_max": 200, "target_pts": 15, "sl_pts": 10},
    "BANKNIFTY": {"yf": "^NSEBANK", "step": 100, "lot": 15,
                  "prem_min": 150, "prem_max": 400, "target_pts": 15, "sl_pts": 10},
    "SENSEX":    {"yf": "^BSESN",   "step": 100, "lot": 10,
                  "prem_min": 100, "prem_max": 300, "target_pts": 15, "sl_pts": 10},
}

# Demo trades for /test command
DEMO_TRADES = [
    {"name": "NIFTY",     "direction": "CE", "strike": 23850, "entry": 110,
     "sl": 95, "target": 130, "price": 23847.5, "confidence": 82, "score": 6,
     "rsi": 38.4, "ema9": 23812.0, "ema21": 23798.0, "macd": 14.2,
     "vol_r": 1.6, "vwap": 23830.0, "atr": 45.0, "demo": True,
     "reasons": ["RSI Oversold (38.4)", "EMA Bullish Alignment",
                 "MACD Positive (14.2)", "Price above VWAP", "Volume Surge 1.6x"]},
    {"name": "BANKNIFTY", "direction": "PE", "strike": 51500, "entry": 175,
     "sl": 165, "target": 195, "price": 51523.0, "confidence": 78, "score": 5,
     "rsi": 64.7, "ema9": 51540.0, "ema21": 51560.0, "macd": -22.5,
     "vol_r": 1.8, "vwap": 51550.0, "atr": 88.0, "demo": True,
     "reasons": ["RSI Overbought (64.7)", "EMA Bearish Alignment",
                 "MACD Negative (-22.5)", "Price below VWAP", "Volume Surge 1.8x"]},
    {"name": "SENSEX",    "direction": "CE", "strike": 78400, "entry": 145,
     "sl": 130, "target": 165, "price": 78412.0, "confidence": 75, "score": 4,
     "rsi": 42.1, "ema9": 78390.0, "ema21": 78370.0, "macd": 8.9,
     "vol_r": 1.4, "vwap": 78395.0, "atr": 120.0, "demo": True,
     "reasons": ["RSI Neutral-Low (42.1)", "EMA Bullish",
                 "MACD Positive (8.9)", "Volume Surge 1.4x"]},
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 16) <= t <= dtime(15, 25)


def nearest_strike(price: float, step: int) -> int:
    return int(round(price / step) * step)


def r2(x) -> float:
    try:
        v = float(x)
        return round(v, 2) if not (np.isnan(v) or np.isinf(v)) else 0.0
    except:
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def calc_rsi(s: pd.Series, n=14) -> float:
    d  = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return r2((100 - 100 / (1 + rs)).iloc[-1])


def calc_ema(s: pd.Series, n: int) -> float:
    return r2(s.ewm(span=n, adjust=False).mean().iloc[-1])


def calc_macd_hist(s: pd.Series) -> float:
    m = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    return r2((m - m.ewm(span=9, adjust=False).mean()).iloc[-1])


def calc_vwap(df: pd.DataFrame) -> float:
    d  = df.tail(50).copy()
    tp = (d["High"] + d["Low"] + d["Close"]) / 3
    return r2((tp * d["Volume"]).cumsum().iloc[-1] / d["Volume"].cumsum().iloc[-1])


def calc_vol_ratio(vol: pd.Series, n=20) -> float:
    avg = vol.rolling(n).mean().iloc[-1]
    return r2(vol.iloc[-1] / avg) if avg > 0 else 1.0


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_index(name: str, cfg: dict) -> list[dict]:
    try:
        df = yf.download(cfg["yf"], period="5d", interval="5m",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            df = yf.download(cfg["yf"], period="10d", interval="15m",
                             progress=False, auto_adjust=True)
        if df is None or len(df) < 20:
            log.warning(f"{name}: Data fetch fail")
            return []
    except Exception as e:
        log.error(f"{name} data error: {e}")
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"].squeeze()
    price = r2(close.iloc[-1])
    if price == 0:
        return []

    rsi_v  = calc_rsi(close)
    ema9   = calc_ema(close, 9)
    ema21  = calc_ema(close, 21)
    macd   = calc_macd_hist(close)
    vol_r  = calc_vol_ratio(df["Volume"].squeeze())
    vwap   = calc_vwap(df)
    c1, c2, c3 = close.iloc[-1], close.iloc[-2], close.iloc[-3]
    mom_up   = bool(c1 > c2 > c3)
    mom_down = bool(c1 < c2 < c3)

    log.info(f"{name}|P={price} RSI={rsi_v} EMA9={ema9} EMA21={ema21} "
             f"MACD={macd} VOL={vol_r} VWAP={vwap}")

    results = []
    for direction in ["CE", "PE"]:
        bull    = direction == "CE"
        score   = 0
        reasons = []

        # RSI
        if bull:
            if rsi_v < 35:   score += 2; reasons.append(f"RSI Oversold ({rsi_v})")
            elif rsi_v < 45: score += 1; reasons.append(f"RSI Low ({rsi_v})")
        else:
            if rsi_v > 65:   score += 2; reasons.append(f"RSI Overbought ({rsi_v})")
            elif rsi_v > 55: score += 1; reasons.append(f"RSI High ({rsi_v})")

        # EMA
        if bull:
            if ema9 > ema21 and price > ema9:
                score += 2; reasons.append("EMA Bullish + Price > EMA9")
            elif price > ema21:
                score += 1; reasons.append("Price > EMA21")
        else:
            if ema9 < ema21 and price < ema9:
                score += 2; reasons.append("EMA Bearish + Price < EMA9")
            elif price < ema21:
                score += 1; reasons.append("Price < EMA21")

        # MACD
        if bull and macd > 0:   score += 1; reasons.append(f"MACD+ ({macd})")
        elif not bull and macd < 0: score += 1; reasons.append(f"MACD- ({macd})")

        # VWAP
        if bull and price > vwap:   score += 1; reasons.append(f"Price > VWAP ({vwap})")
        elif not bull and price < vwap: score += 1; reasons.append(f"Price < VWAP ({vwap})")

        # Volume
        if vol_r >= 1.3: score += 1; reasons.append(f"Vol Surge {vol_r}x")

        # Momentum
        if bull and mom_up:   score += 1; reasons.append("3 Bullish candles")
        elif not bull and mom_down: score += 1; reasons.append("3 Bearish candles")

        log.info(f"  {name} {direction}: score={score}/8")

        if score < 3:
            continue

        key  = f"{name}_{direction}"
        last = last_signal.get(key)
        if last and (datetime.now(IST) - last).total_seconds() < 900:
            log.info(f"  Duplicate skip: {key}")
            continue
        last_signal[key] = datetime.now(IST)

        strike = nearest_strike(price, cfg["step"])
        entry  = int(round(((cfg["prem_min"] + cfg["prem_max"]) // 2) / 5) * 5)
        results.append({
            "name": name, "direction": direction,
            "strike": strike, "entry": entry,
            "target": entry + cfg["target_pts"],
            "sl":     entry - cfg["sl_pts"],
            "price": price, "confidence": min(92, 50 + score * 6),
            "score": score, "rsi": rsi_v, "ema9": ema9, "ema21": ema21,
            "macd": macd, "vol_r": vol_r, "vwap": vwap, "atr": 0,
            "reasons": reasons, "demo": False,
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE FORMAT
# ══════════════════════════════════════════════════════════════════════════════

def format_alert(sig: dict) -> str:
    now      = datetime.now(IST).strftime("%d %b %Y | %I:%M %p")
    arrow    = "📈" if sig["direction"] == "CE" else "📉"
    demo_tag = "\n🔸 <b>[ DEMO TRADE ]</b>\n" if sig.get("demo") else "\n"
    reasons_s = "\n".join(f"  ✅ {r}" for r in sig["reasons"])

    return (
        f"╔══════════════════════════╗\n"
        f"   🔔 RUDRA SECURITIES\n"
        f"       TRADING ALERT\n"
        f"╚══════════════════════════╝"
        f"{demo_tag}"
        f"{arrow} <b>Index:</b>  {sig['name']}\n"
        f"📌 <b>Type:</b>   {sig['direction']}\n"
        f"💰 <b>Entry Price:</b> ₹{sig['entry']}\n"
        f"🎯 <b>Strike:</b>  {sig['strike']}\n"
        f"🛑 <b>Stop Loss:</b> ₹{sig['sl']}\n"
        f"✅ <b>Target:</b>  ₹{sig['target']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Spot: ₹{sig['price']} | RSI: {sig['rsi']}\n"
        f"   EMA9: {sig['ema9']} | VWAP: {sig['vwap']}\n"
        f"   Vol: {sig['vol_r']}x | Score: {sig['score']}/8\n\n"
        f"📝 <b>Reasons:</b>\n{reasons_s}\n\n"
        f"🎯 Confidence: {sig['confidence']}%\n"
        f"🕐 {now} IST\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>Educational purpose only.</i>"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL POST — thread-safe version
# ══════════════════════════════════════════════════════════════════════════════

async def post_to_channel(bot, sig: dict) -> bool:
    """Async — directly await this from async context"""
    if not CHANNEL_ID:
        log.warning("CHANNEL_ID not set!")
        return False
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=format_alert(sig),
            parse_mode="HTML",
        )
        log.info(f"✅ Channel: {sig['name']} {sig['direction']} ₹{sig['entry']}")
        return True
    except Exception as e:
        log.error(f"❌ Channel fail: {e}")
        return False


def post_from_thread(sig: dict):
    """
    Flask thread se call karo — main event loop mein schedule karta hai.
    asyncio.run_coroutine_threadsafe() — yahi sahi tarika hai.
    """
    global main_loop, tg_app
    if main_loop is None or tg_app is None:
        log.error("Bot not ready yet")
        return False
    try:
        future = asyncio.run_coroutine_threadsafe(
            post_to_channel(tg_app.bot, sig),
            main_loop
        )
        return future.result(timeout=15)
    except Exception as e:
        log.error(f"post_from_thread error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# AUTO SCAN
# ══════════════════════════════════════════════════════════════════════════════

async def smart_scan(ctx: ContextTypes.DEFAULT_TYPE):
    if not is_market_open():
        return
    log.info("🔍 Auto scan...")
    total = 0
    for name, cfg in INDICES.items():
        for sig in analyze_index(name, cfg):
            await post_to_channel(ctx.bot, sig)
            total += 1
            await asyncio.sleep(1)
    log.info(f"🔍 Done — {total} signals")


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def safe_reply(update: Update, text: str, **kw):
    msg = update.effective_message
    if msg:
        try:
            await msg.reply_html(text, **kw)
        except Exception as e:
            log.error(f"reply error: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧪 Test Trade",    callback_data="test")],
        [InlineKeyboardButton("📊 Manual Scan",   callback_data="scan")],
        [InlineKeyboardButton("📈 Market Status", callback_data="status")],
        [InlineKeyboardButton("❓ Help",           callback_data="help")],
    ])
    await safe_reply(update,
        "🔔 <b>RUDRA SECURITIES v6.0</b>\n\n"
        "✅ NIFTY | BANKNIFTY | SENSEX\n"
        "✅ CE + PE dono side\n"
        "✅ 15 rupees target\n"
        "✅ Har 3 min auto scan\n\n"
        "🧪 Pehle <b>/test</b> karo — bot + channel check hoga!\n\n"
        "⚠️ <i>Commands sirf yahan (private chat) kaam karti hain.\n"
        "Channel mein bot khud signal bhejta hai.</i>",
        reply_markup=kb,
    )


async def cmd_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Demo trade — private chat mein dikhao + channel mein post karo.
    Market hours ki zarurat NAHI hai.
    """
    msg = update.effective_message
    if not msg:
        return

    sig = random.choice(DEMO_TRADES).copy()

    # Pehle user ko batao
    wait = await msg.reply_text("🧪 Demo trade bhej raha hoon...")

    # Channel mein post karo
    ch_ok = await post_to_channel(ctx.bot, sig)

    await wait.delete()

    if ch_ok:
        ch_status = (
            "✅ <b>Channel mein bhi post ho gaya!</b>\n"
            "Ab apna channel check karo — wahan bhi yahi trade dikhega."
        )
    else:
        ch_status = (
            "❌ <b>Channel post FAIL hua.</b>\n\n"
            "<b>Fix karo:</b>\n"
            "1. Railway Variables mein <code>CHANNEL_ID</code> check karo\n"
            f"   Current value: <code>{CHANNEL_ID or 'EMPTY!'}</code>\n"
            "2. Format: <code>@channelname</code> ya <code>-100xxxxxxxxxx</code>\n"
            "3. Bot channel ka Admin hai? Full rights?\n"
            "4. Bot ne channel join kiya hai?"
        )

    await msg.reply_html(
        f"{format_alert(sig)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ch_status}"
    )


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and ADMIN_ID and user.id != ADMIN_ID:
        await safe_reply(update, "❌ Sirf admin kar sakta hai.")
        return
    msg = update.effective_message
    if not msg:
        return

    wait  = await msg.reply_text("⏳ NIFTY, BANKNIFTY, SENSEX scan kar raha hoon...")
    total = 0
    for name, cfg in INDICES.items():
        for sig in analyze_index(name, cfg):
            ok = await post_to_channel(ctx.bot, sig)
            await msg.reply_html(
                format_alert(sig) + "\n\n" +
                ("✅ Channel mein post hua!" if ok else "⚠️ Channel post fail")
            )
            total += 1
            await asyncio.sleep(1)

    if total == 0:
        mkt = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        await wait.edit_text(
            f"⚪ <b>Koi signal nahi mila</b>\n\n"
            f"Market: {mkt}\n"
            f"Indicators clear trend nahi dikha rahe.\n\n"
            f"Bot har 3 min mein auto scan karta hai.\n"
            f"Test ke liye: /test",
            parse_mode="HTML"
        )
    else:
        try: await wait.delete()
        except: pass


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mkt = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    now = datetime.now(IST).strftime("%d %b %Y | %I:%M %p IST")
    ch  = CHANNEL_ID or "⚠️ SET NAHI HAI"
    await safe_reply(update,
        f"📡 <b>Bot Status v6.0</b>\n\n"
        f"Market: {mkt}\n"
        f"🕐 {now}\n\n"
        f"📢 Channel: <code>{ch}</code>\n"
        f"⏱ Scan: Har 3 min (market hours)\n"
        f"📊 NIFTY | BANKNIFTY | SENSEX\n"
        f"🎯 Target ₹15 | SL ₹10\n\n"
        f"🧪 Bot test: /test"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update,
        "📖 <b>Commands (private chat mein):</b>\n\n"
        "/start  — Main menu\n"
        "/test   — Demo trade + channel test\n"
        "/scan   — Manual scan\n"
        "/status — Status\n"
        "/help   — Yeh message\n\n"
        "⚠️ <b>Channel mein commands kaam nahi karti.</b>\n"
        "Bot channel mein SEND karta hai, receive nahi.\n"
        "Commands sirf bot ke private chat mein likhein."
    )


async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    class FU:
        effective_message = q.message
        effective_user    = q.from_user

    mapping = {
        "test":   cmd_test,
        "scan":   cmd_scan,
        "status": cmd_status,
        "help":   cmd_help,
    }
    fn = mapping.get(q.data)
    if fn:
        await fn(FU(), ctx)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK — TradingView Webhook
# ══════════════════════════════════════════════════════════════════════════════
flask_app = Flask(__name__)


@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "6.0",
                    "service": "Rudra Securities Bot"}), 200


@flask_app.route("/webhook", methods=["POST"])
def tv_webhook():
    """
    TradingView Alert Message (JSON):
    {
      "secret":     "rudra123",
      "index":      "NIFTY",
      "type":       "CE",
      "strike":     23850,
      "entry":      110,
      "sl":         95,
      "target":     130,
      "spot":       23847,
      "confidence": 80,
      "reason":     "EMA Cross + RSI Oversold"
    }
    
    TradingView Alert URL: https://YOUR-RAILWAY-URL.railway.app/webhook
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            log.warning("Webhook: Empty body")
            return jsonify({"error": "empty body"}), 400

        secret = data.get("secret", "")
        if secret != TV_SECRET:
            log.warning(f"Webhook: Wrong secret '{secret}'")
            return jsonify({"error": "wrong secret"}), 403

        sig = {
            "name":       str(data.get("index", "NIFTY")).upper(),
            "direction":  str(data.get("type", "CE")).upper(),
            "strike":     int(data.get("strike", 0)),
            "entry":      int(data.get("entry", 0)),
            "sl":         int(data.get("sl", 0)),
            "target":     int(data.get("target", 0)),
            "price":      float(data.get("spot", 0)),
            "confidence": int(data.get("confidence", 80)),
            "score":      6,
            "rsi":        data.get("rsi", "N/A"),
            "ema9":       data.get("ema9", "N/A"),
            "ema21":      data.get("ema21", "N/A"),
            "macd":       data.get("macd", "N/A"),
            "vol_r":      data.get("vol", "N/A"),
            "vwap":       data.get("vwap", "N/A"),
            "atr":        0,
            "reasons":    [str(data.get("reason", "TradingView Alert"))],
            "demo":       False,
        }

        log.info(f"TV Webhook received: {sig['name']} {sig['direction']} entry={sig['entry']}")

        # Thread-safe post to channel
        ok = post_from_thread(sig)

        return jsonify({"status": "posted" if ok else "channel_fail"}), 200

    except Exception as e:
        log.error(f"Webhook exception: {e}")
        return jsonify({"error": str(e)}), 500


def run_flask():
    log.info(f"Flask starting on port {PORT}")
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    global tg_app, main_loop

    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN missing! Railway Variables check karo.")
    if not CHANNEL_ID:
        log.warning("⚠️  CHANNEL_ID set nahi — channel post nahi hoga!")

    # Main event loop capture karo (Flask thread issse use karega)
    main_loop = asyncio.get_event_loop()

    tg_app = Application.builder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start",  cmd_start))
    tg_app.add_handler(CommandHandler("test",   cmd_test))
    tg_app.add_handler(CommandHandler("scan",   cmd_scan))
    tg_app.add_handler(CommandHandler("status", cmd_status))
    tg_app.add_handler(CommandHandler("help",   cmd_help))
    tg_app.add_handler(CallbackQueryHandler(button_cb))

    tg_app.job_queue.run_repeating(smart_scan, interval=180, first=20)

    # Flask alag thread mein
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    log.info(f"✅ Flask webhook thread started (port {PORT})")
    log.info("✅ Rudra Securities Bot v6.0 starting polling...")

    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
