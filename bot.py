"""
RUDRA SECURITIES — Indian Market Signal Bot v5.3

Changes v5.3:
  • Auto scan interval reduced from 3 min → 1 min
  • Score threshold = 2 (relaxed)
  • Cooldown = 10 min per index+direction
  • Pre-Market Update daily 09:10 AM IST
  • Simplified alert format
"""

import logging, os, threading, asyncio
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import random

import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask, request, abort
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

tg_app: Application = None
last_signal: dict   = {}

INDICES = {
    "NIFTY": {
        "yf": "^NSEI", "step": 50, "lot": 75,
        "prem_min": 80, "prem_max": 200,
        "target_pts": 15, "sl_pts": 10,
    },
    "BANKNIFTY": {
        "yf": "^NSEBANK", "step": 100, "lot": 15,
        "prem_min": 150, "prem_max": 400,
        "target_pts": 15, "sl_pts": 10,
    },
    "SENSEX": {
        "yf": "^BSESN", "step": 100, "lot": 10,
        "prem_min": 100, "prem_max": 300,
        "target_pts": 15, "sl_pts": 10,
    },
}

# Demo trades
DEMO_TRADES = [
    {
        "name": "NIFTY", "direction": "CE",
        "strike": 23850, "entry": 110, "sl": 95, "target": 130,
        "price": 23847.5, "confidence": 82, "score": 6,
        "rsi": 38.4, "ema9": 23812.0, "ema21": 23798.0,
        "macd": 14.2, "vol_r": 1.6, "vwap": 23830.0, "atr": 45.0,
        "reasons": ["RSI Oversold", "EMA Bullish", "MACD Positive"],
        "demo": True,
    },
    {
        "name": "BANKNIFTY", "direction": "PE",
        "strike": 51500, "entry": 175, "sl": 165, "target": 195,
        "price": 51523.0, "confidence": 78, "score": 5,
        "rsi": 64.7, "ema9": 51540.0, "ema21": 51560.0,
        "macd": -22.5, "vol_r": 1.8, "vwap": 51550.0, "atr": 88.0,
        "reasons": ["RSI Overbought", "EMA Bearish", "MACD Negative"],
        "demo": True,
    },
    {
        "name": "SENSEX", "direction": "CE",
        "strike": 78400, "entry": 145, "sl": 130, "target": 165,
        "price": 78412.0, "confidence": 75, "score": 4,
        "rsi": 42.1, "ema9": 78390.0, "ema21": 78370.0,
        "macd": 8.9, "vol_r": 1.4, "vwap": 78395.0, "atr": 120.0,
        "reasons": ["RSI Neutral-Low", "EMA Bullish", "MACD Positive"],
        "demo": True,
    },
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
    return round(float(x), 2)


# ══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def rsi(s: pd.Series, n=14) -> float:
    d  = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    v  = (100 - 100 / (1 + rs)).iloc[-1]
    return r2(v) if not np.isnan(v) else 50.0


def ema(s: pd.Series, n: int) -> float:
    return r2(s.ewm(span=n, adjust=False).mean().iloc[-1])


def macd_hist(s: pd.Series) -> float:
    e12 = s.ewm(span=12, adjust=False).mean()
    e26 = s.ewm(span=26, adjust=False).mean()
    m   = e12 - e26
    sig = m.ewm(span=9, adjust=False).mean()
    v   = (m - sig).iloc[-1]
    return r2(v) if not np.isnan(v) else 0.0


def atr14(high, low, close) -> float:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    v = tr.rolling(14).mean().iloc[-1]
    return r2(v) if not np.isnan(v) else 0.0


def vol_ratio(volume: pd.Series, n=20) -> float:
    avg = volume.rolling(n).mean().iloc[-1]
    cur = volume.iloc[-1]
    if avg > 0:
        v = cur / avg
        return r2(v) if not np.isnan(v) else 1.0
    return 1.0


def vwap_val(df: pd.DataFrame) -> float:
    d  = df.tail(50).copy()
    tp = (d["High"] + d["Low"] + d["Close"]) / 3
    v  = (tp * d["Volume"]).cumsum() / d["Volume"].cumsum()
    val = v.iloc[-1]
    return r2(val) if not np.isnan(val) else float(df["Close"].iloc[-1])


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL ENGINE (score threshold = 2, cooldown = 10 min)
# ══════════════════════════════════════════════════════════════════════════════

def analyze_index(name: str, cfg: dict) -> list[dict]:
    try:
        df = yf.download(cfg["yf"], period="5d", interval="5m",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            df = yf.download(cfg["yf"], period="10d", interval="15m",
                             progress=False, auto_adjust=True)
        if df is None or len(df) < 20:
            log.warning(f"{name}: Data nahi mila")
            return []
    except Exception as e:
        log.error(f"{name} fetch error: {e}")
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    price  = r2(close.iloc[-1])
    rsi_v  = rsi(close)
    ema9_v = ema(close, 9)
    ema21_v= ema(close, 21)
    macd_v = macd_hist(close)
    vol_r  = vol_ratio(volume)
    vwap_v = vwap_val(df)

    c1, c2, c3 = close.iloc[-1], close.iloc[-2], close.iloc[-3]
    mom_up   = c1 > c2 > c3
    mom_down = c1 < c2 < c3

    c5 = close.iloc[-5] if len(close) >= 5 else close.iloc[0]
    pct_5min = ((c1 - c5) / c5) * 100 if c5 != 0 else 0

    ema_bullish = ema9_v > ema21_v
    ema_bearish = ema9_v < ema21_v

    log.info(f"{name} | Price={price} RSI={rsi_v} EMA9={ema9_v} EMA21={ema21_v} "
             f"MACD={macd_v} VolR={vol_r} VWAP={vwap_v} 5min%={r2(pct_5min)}%")

    results = []
    for direction in ["CE", "PE"]:
        bull  = (direction == "CE")
        score = 0
        reasons = []

        # RSI
        if bull:
            if rsi_v < 40:    score += 2; reasons.append(f"RSI Oversold ({rsi_v})")
            elif rsi_v < 50:  score += 1; reasons.append(f"RSI Low ({rsi_v})")
        else:
            if rsi_v > 60:    score += 2; reasons.append(f"RSI Overbought ({rsi_v})")
            elif rsi_v > 50:  score += 1; reasons.append(f"RSI High ({rsi_v})")

        # EMA
        if bull and ema_bullish:
            if price > ema9_v:
                score += 2; reasons.append("EMA Bullish + Price > EMA9")
            else:
                score += 1; reasons.append("EMA Bullish")
        elif not bull and ema_bearish:
            if price < ema9_v:
                score += 2; reasons.append("EMA Bearish + Price < EMA9")
            else:
                score += 1; reasons.append("EMA Bearish")

        # MACD
        if bull and macd_v > 0:
            score += 1; reasons.append(f"MACD Positive ({macd_v})")
        elif not bull and macd_v < 0:
            score += 1; reasons.append(f"MACD Negative ({macd_v})")

        # VWAP
        if bull and price > vwap_v:
            score += 1; reasons.append(f"Price > VWAP ({vwap_v})")
        elif not bull and price < vwap_v:
            score += 1; reasons.append(f"Price < VWAP ({vwap_v})")

        # Volume
        if vol_r >= 1.2:
            score += 1; reasons.append(f"Volume {vol_r}x")

        # 3-candle momentum
        if bull and mom_up:
            score += 2; reasons.append("3 Bullish Candles ↑")
        elif not bull and mom_down:
            score += 2; reasons.append("3 Bearish Candles ↓")

        # 5-candle momentum
        if bull and pct_5min > 0.15:
            score += 1; reasons.append(f"+{r2(pct_5min)}% in 5min")
        elif not bull and pct_5min < -0.15:
            score += 1; reasons.append(f"{r2(pct_5min)}% in 5min")

        log.info(f"  {name} {direction}: score={score}/10 | reasons={len(reasons)}")

        if score < 2:
            continue

        strike = nearest_strike(price, cfg["step"])
        prem   = (cfg["prem_min"] + cfg["prem_max"]) // 2
        entry  = int(round(prem / 5) * 5)
        target = entry + cfg["target_pts"]
        sl     = entry - cfg["sl_pts"]
        conf   = min(92, 45 + score * 7)

        key  = f"{name}_{direction}"
        last = last_signal.get(key)
        if last:
            diff = (datetime.now(IST) - last).total_seconds()
            if diff < 600:  # 10 min cooldown
                log.info(f"Cooldown skip: {key} ({int(diff)}s)")
                continue
        last_signal[key] = datetime.now(IST)

        results.append({
            "name": name, "direction": direction,
            "strike": strike, "entry": entry, "target": target, "sl": sl,
            "price": price, "confidence": conf, "score": score,
            "rsi": rsi_v, "ema9": ema9_v, "ema21": ema21_v,
            "macd": macd_v, "vol_r": vol_r, "vwap": vwap_v,
            "atr": atr14(high, low, close),
            "reasons": reasons, "demo": False,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE FORMAT
# ══════════════════════════════════════════════════════════════════════════════

def format_alert(sig: dict) -> str:
    now   = datetime.now(IST).strftime("%d %b %Y | %I:%M %p")
    arrow = "📈" if sig["direction"] == "CE" else "📉"
    demo_line = "\n🔸 [DEMO TRADE — Real nahi hai]" if sig.get("demo") else ""

    header = (
        "╔══════════════════════════╗\n"
        "   🔔 RUDRA SECURITIES\n"
        "       TRADING ALERT\n"
        "╚══════════════════════════╝"
    )

    trade_info = (
        f"{demo_line}\n"
        f"{arrow} Index: {sig['name']}\n"
        f"📌 Type: {sig['direction']}\n"
        f"💰 Entry Price: ₹{sig['entry']}\n"
        f"🎯 Strike: {sig['strike']}\n"
        f"🛑 Stop Loss: ₹{sig['sl']}\n"
        f"✅ Target: ₹{sig['target']}\n"
    )

    footer = (
        f"🎯 Confidence: {sig['confidence']}%\n"
        f"🕐 {now} IST\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Educational purpose only."
    )

    return header + "\n" + trade_info + "\n" + footer


# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL POST
# ══════════════════════════════════════════════════════════════════════════════

async def post_to_channel(bot, sig: dict) -> bool:
    if not CHANNEL_ID:
        log.warning("CHANNEL_ID set nahi hai!")
        return False
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=format_alert(sig),
            parse_mode="HTML",
        )
        log.info(f"✅ Channel post: {sig['name']} {sig['direction']} @ {sig['entry']}")
        return True
    except Exception as e:
        log.error(f"❌ Channel post FAIL: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PRE‑MARKET UPDATE
# ══════════════════════════════════════════════════════════════════════════════

async def pre_market_post(ctx: ContextTypes.DEFAULT_TYPE):
    if not CHANNEL_ID:
        return

    today = datetime.now(IST)
    if today.weekday() >= 5:
        return

    try:
        lines = [
            "╔══════════════════════════╗",
            "   📊 PRE‑MARKET UPDATE",
            "╚══════════════════════════╝",
            "",
            f"📅 <b>{today.strftime('%d %b %Y')}</b>",
            ""
        ]

        for name, cfg in INDICES.items():
            try:
                df = yf.download(cfg["yf"], period="5d", interval="1d",
                                 progress=False, auto_adjust=True)
                if df is None or len(df) < 3:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                close_s = df["Close"].squeeze()
                open_s  = df["Open"].squeeze()

                yc = round(float(close_s.iloc[-2]), 2)
                yo = round(float(open_s.iloc[-2]), 2)
                pc = round(float(close_s.iloc[-3]), 2)
                gap = round(yo - pc, 2)
                emoji = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"

                lines.append(f"━━━ {name} ━━━")
                lines.append(f"   Open:  {yo:,.2f}")
                lines.append(f"   Close: {yc:,.2f}")
                lines.append(f"   Gap:   {emoji} {gap:+} pts")
                lines.append("")
            except Exception as e:
                log.error(f"Pre-market {name}: {e}")

        # GIFT NIFTY
        try:
            gift = yf.Ticker("^GIFNIFTY")
            info = gift.info
            gp = info.get("regularMarketPrice") or info.get("previousClose")
            if gp:
                gp = round(float(gp), 2)
                ndf = yf.download("^NSEI", period="3d", interval="1d",
                                  progress=False, auto_adjust=True)
                if ndf is not None and len(ndf) >= 2:
                    if isinstance(ndf.columns, pd.MultiIndex):
                        ndf.columns = ndf.columns.get_level_values(0)
                    nyc = round(float(ndf["Close"].squeeze().iloc[-2]), 2)
                    egap = round(gp - nyc, 2)
                    eemoji = "🟢" if egap > 0 else "🔴" if egap < 0 else "⚪"
                    lines.append("━━━ Today's Expected (NIFTY) ━━━")
                    lines.append(f"   GIFT NIFTY: {gp}")
                    lines.append(f"   Expected Gap: {eemoji} {egap:+} pts")
                    lines.append("")
        except Exception as e:
            log.error(f"GIFT NIFTY: {e}")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ <i>Data may be delayed. For reference only.</i>")

        await ctx.bot.send_message(chat_id=CHANNEL_ID, text="\n".join(lines), parse_mode="HTML")
        log.info("✅ Pre-market posted")

    except Exception as e:
        log.error(f"Pre-market error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO SCAN (EVERY 1 MINUTE)
# ══════════════════════════════════════════════════════════════════════════════

async def smart_scan(ctx: ContextTypes.DEFAULT_TYPE):
    if not is_market_open():
        return
    log.info("🔍 Auto scan (1 min)...")
    total = 0
    for name, cfg in INDICES.items():
        for sig in analyze_index(name, cfg):
            await post_to_channel(ctx.bot, sig)
            total += 1
            await asyncio.sleep(1)
    log.info(f"🔍 Scan done — {total} signals")


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def safe_reply(update: Update, text: str, **kwargs):
    msg = update.effective_message
    if msg:
        try:
            await msg.reply_html(text, **kwargs)
        except Exception as e:
            log.error(f"Reply error: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧪 Test Trade",     callback_data="test")],
        [InlineKeyboardButton("📊 Manual Scan",    callback_data="scan")],
        [InlineKeyboardButton("📈 Market Status",  callback_data="status")],
        [InlineKeyboardButton("❓ Help",            callback_data="help")],
    ])
    await safe_reply(update,
        "🔔 <b>RUDRA SECURITIES BOT v5.3</b>\n\n"
        "⚡ Auto scan every 1 minute\n"
        "✅ Score threshold: 2 (fast signals)\n"
        "✅ CE + PE dono side scan\n"
        "✅ NIFTY | BANKNIFTY | SENSEX\n"
        "✅ Daily 9:10 AM Pre-Market\n\n"
        "🧪 /test — demo trade",
        reply_markup=kb,
    )


async def cmd_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    sig = random.choice(DEMO_TRADES).copy()

    await msg.reply_html(
        "🧪 <b>TEST MODE — Demo Trade</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Channel mein bhi post ho raha hai...\n"
    )

    posted = await post_to_channel(ctx.bot, sig)

    if posted:
        await msg.reply_html(
            format_alert(sig) + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Channel mein post ho gaya!</b>"
        )
    else:
        await msg.reply_html(
            format_alert(sig) + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ Channel post FAIL.\n"
            f"CHANNEL_ID: <code>{CHANNEL_ID or 'SET NAHI!'}</code>"
        )


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and ADMIN_ID and user.id != ADMIN_ID:
        await safe_reply(update, "❌ Sirf admin manual scan kar sakta hai.")
        return

    msg = update.effective_message
    if not msg:
        return

    wait = await msg.reply_text("⏳ Scanning...")
    total = 0

    for name, cfg in INDICES.items():
        for sig in analyze_index(name, cfg):
            posted = await post_to_channel(ctx.bot, sig)
            ch_txt = "✅" if posted else "⚠️"
            await msg.reply_html(format_alert(sig) + f"\n\nChannel: {ch_txt}")
            total += 1
            await asyncio.sleep(1)

    if total == 0:
        mkt = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        now = datetime.now(IST).strftime("%I:%M %p IST")
        await wait.edit_text(
            f"⚪ <b>Koi signal nahi mila</b>\n\n"
            f"Market: {mkt} | {now}\n\n"
            f"• Indicators align nahi hue\n"
            f"• Next auto scan in 1 min\n\n"
            f"/test — demo trade",
            parse_mode="HTML"
        )
    else:
        try:
            await wait.delete()
        except:
            pass


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mkt = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    now = datetime.now(IST).strftime("%d %b %Y | %I:%M %p IST")
    ch  = CHANNEL_ID if CHANNEL_ID else "⚠️ SET NAHI HAI"

    await safe_reply(update,
        f"📡 <b>Bot Status v5.3</b>\n\n"
        f"Market: {mkt}\n"
        f"🕐 {now}\n\n"
        f"📢 Channel: <code>{ch}</code>\n"
        f"⚡ Auto Scan: Har 1 minute\n"
        f"📊 Indices: NIFTY | BANKNIFTY | SENSEX\n"
        f"🎯 Target: ₹15 | SL: ₹10\n"
        f"📉 Score threshold: 2\n"
        f"🌅 Pre‑Market: Daily 09:10 AM\n\n"
        f"/test — demo trade"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update,
        "📖 <b>RUDRA SECURITIES — Help</b>\n\n"
        "<b>Commands (private chat):</b>\n"
        "/start   — Bot info + buttons\n"
        "/test    — Demo trade\n"
        "/scan    — Manual scan (admin)\n"
        "/status  — Bot + market status\n"
        "/help    — Yeh message\n\n"
        "⚡ Auto scan: Every 1 minute\n"
        "🌅 Daily 9:10 AM Pre-Market Update\n"
        "⚠️ <i>Educational purpose only.</i>"
    )


async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    class FU:
        effective_message = q.message
        effective_user    = q.from_user

    if q.data == "test":
        await cmd_test(FU(), ctx)
    elif q.data == "scan":
        await cmd_scan(FU(), ctx)
    elif q.data == "status":
        await cmd_status(FU(), ctx)
    elif q.data == "help":
        await cmd_help(FU(), ctx)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK
# ══════════════════════════════════════════════════════════════════════════════
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "version": "5.3"}, 200

@flask_app.route("/webhook", methods=["POST"])
def tv_webhook():
    try:
        data = request.get_json(force=True)
        if not data or data.get("secret") != TV_SECRET:
            abort(403)
        sig = {
            "name": data.get("index", "NIFTY"),
            "direction": data.get("type", "CE").upper(),
            "strike": int(data.get("strike", 0)),
            "entry": int(data.get("entry", 0)),
            "sl": int(data.get("sl", 0)),
            "target": int(data.get("target", 0)),
            "price": float(data.get("spot", 0)),
            "confidence": int(data.get("confidence", 80)),
            "score": 5, "rsi": "N/A", "ema9": "N/A", "ema21": "N/A",
            "macd": "N/A", "vol_r": "N/A", "vwap": "N/A", "atr": 0,
            "reasons": [data.get("reason", "TradingView Alert")], "demo": False,
        }
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def _s():
            if tg_app: await post_to_channel(tg_app.bot, sig)
        loop.run_until_complete(_s())
        loop.close()
        return {"status": "posted"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global tg_app
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN missing!")
    if not CHANNEL_ID:
        log.warning("⚠️  CHANNEL_ID set nahi hai!")

    tg_app = Application.builder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start",  cmd_start))
    tg_app.add_handler(CommandHandler("test",   cmd_test))
    tg_app.add_handler(CommandHandler("scan",   cmd_scan))
    tg_app.add_handler(CommandHandler("status", cmd_status))
    tg_app.add_handler(CommandHandler("help",   cmd_help))
    tg_app.add_handler(CallbackQueryHandler(button_cb))

    # ⚡ Auto scan every 1 minute (pehle 180 = 3 min tha)
    tg_app.job_queue.run_repeating(smart_scan, interval=60, first=10)

    # Pre-market daily at 09:10 AM IST
    tg_app.job_queue.run_daily(
        pre_market_post,
        time=dtime(hour=9, minute=10, tzinfo=IST),
        days=(0, 1, 2, 3, 4)
    )

    threading.Thread(target=run_flask, daemon=True).start()
    log.info(f"✅ Webhook port {PORT}")
    log.info("✅ Rudra Securities Bot v5.3 — Live! (1 min scan)")
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
