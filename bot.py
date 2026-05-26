"""
RUDRA SECURITIES — Indian Market Signal Bot v6.1.1

FIX v6.1.1:
  • Button callback fixed (effective_message → message)
  • Manual scan button now works perfectly
  • Price Action Priority System
  • Score threshold: 1 | Cooldown: 5 min
  • NSE + MCX both segments
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

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — NSE + MCX
# ══════════════════════════════════════════════════════════════════════════════

INDICES = {
    "NIFTY": {
        "yf": "^NSEI", "step": 50, "lot": 75,
        "prem_min": 80, "prem_max": 200,
        "target_pts": 15, "sl_pts": 10, "segment": "NSE",
        "market_start": dtime(9, 15), "market_end": dtime(15, 30),
        "min_move_pct": 0.03,
    },
    "BANKNIFTY": {
        "yf": "^NSEBANK", "step": 100, "lot": 15,
        "prem_min": 150, "prem_max": 400,
        "target_pts": 15, "sl_pts": 10, "segment": "NSE",
        "market_start": dtime(9, 15), "market_end": dtime(15, 30),
        "min_move_pct": 0.04,
    },
    "SENSEX": {
        "yf": "^BSESN", "step": 100, "lot": 10,
        "prem_min": 100, "prem_max": 300,
        "target_pts": 15, "sl_pts": 10, "segment": "NSE",
        "market_start": dtime(9, 15), "market_end": dtime(15, 30),
        "min_move_pct": 0.03,
    },
    "CRUDEOIL": {
        "yf": "CL=F", "step": 50, "lot": 100,
        "prem_min": 30, "prem_max": 80,
        "target_pts": 10, "sl_pts": 7, "segment": "MCX",
        "market_start": dtime(9, 0), "market_end": dtime(23, 30),
        "min_move_pct": 0.05,
    },
    "NATURALGAS": {
        "yf": "NG=F", "step": 10, "lot": 1250,
        "prem_min": 5, "prem_max": 20,
        "target_pts": 3, "sl_pts": 2, "segment": "MCX",
        "market_start": dtime(9, 0), "market_end": dtime(23, 30),
        "min_move_pct": 0.08,
    },
    "GOLD": {
        "yf": "GC=F", "step": 100, "lot": 1,
        "prem_min": 100, "prem_max": 300,
        "target_pts": 20, "sl_pts": 15, "segment": "MCX",
        "market_start": dtime(9, 0), "market_end": dtime(23, 30),
        "min_move_pct": 0.04,
    },
}

DEMO_TRADES = [
    {"name": "NIFTY", "direction": "CE", "strike": 23850, "entry": 110, "sl": 95, "target": 130,
     "price": 23847.5, "confidence": 82, "score": 6, "segment": "NSE", "reasons": ["RSI Oversold", "EMA Bullish", "🕯️ Hammer"], "demo": True},
    {"name": "BANKNIFTY", "direction": "PE", "strike": 51500, "entry": 175, "sl": 165, "target": 195,
     "price": 51523.0, "confidence": 78, "score": 5, "segment": "NSE", "reasons": ["RSI Overbought", "EMA Bearish"], "demo": True},
    {"name": "CRUDEOIL", "direction": "CE", "strike": 6200, "entry": 55, "sl": 48, "target": 65,
     "price": 6185.0, "confidence": 80, "score": 5, "segment": "MCX", "reasons": ["Volume Surge", "🕯️ Bullish Engulfing"], "demo": True},
    {"name": "NATURALGAS", "direction": "PE", "strike": 180, "entry": 8, "sl": 6, "target": 11,
     "price": 182.5, "confidence": 75, "score": 4, "segment": "MCX", "reasons": ["RSI Overbought"], "demo": True},
    {"name": "GOLD", "direction": "CE", "strike": 74200, "entry": 180, "sl": 165, "target": 200,
     "price": 74150.0, "confidence": 76, "score": 4, "segment": "MCX", "reasons": ["EMA Bullish", "Price > VWAP"], "demo": True},
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_market_open_for(cfg: dict) -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return cfg["market_start"] <= t <= cfg["market_end"]


def nearest_strike(price: float, step: int) -> int:
    return int(round(price / step) * step)


def r2(x) -> float:
    return round(float(x), 2)


# ══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def rsi(s: pd.Series, n=14) -> float:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    v = (100 - 100 / (1 + rs)).iloc[-1]
    return r2(v) if not np.isnan(v) else 50.0


def ema(s: pd.Series, n: int) -> float:
    return r2(s.ewm(span=n, adjust=False).mean().iloc[-1])


def macd_hist(s: pd.Series) -> float:
    e12 = s.ewm(span=12, adjust=False).mean()
    e26 = s.ewm(span=26, adjust=False).mean()
    m = e12 - e26
    sig = m.ewm(span=9, adjust=False).mean()
    v = (m - sig).iloc[-1]
    return r2(v) if not np.isnan(v) else 0.0


def vol_ratio(volume: pd.Series, n=20) -> float:
    avg = volume.rolling(n).mean().iloc[-1]
    cur = volume.iloc[-1]
    return r2(cur / avg) if avg > 0 else 1.0


def vwap_val(df: pd.DataFrame) -> float:
    d = df.tail(50).copy()
    tp = (d["High"] + d["Low"] + d["Close"]) / 3
    v = (tp * d["Volume"]).cumsum() / d["Volume"].cumsum()
    return r2(v.iloc[-1]) if not np.isnan(v.iloc[-1]) else float(df["Close"].iloc[-1])


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL ENGINE — PRICE ACTION PRIORITY
# ══════════════════════════════════════════════════════════════════════════════

def analyze_index(name: str, cfg: dict) -> list[dict]:
    if not is_market_open_for(cfg):
        return []

    try:
        df = yf.download(cfg["yf"], period="5d", interval="5m", progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            df = yf.download(cfg["yf"], period="10d", interval="15m", progress=False, auto_adjust=True)
        if df is None or len(df) < 15:
            return []
    except Exception as e:
        log.error(f"{name}: {e}")
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    price = r2(close.iloc[-1])
    rsi_v = rsi(close)
    ema9_v = ema(close, 9)
    ema21_v = ema(close, 21)
    macd_v = macd_hist(close)
    vol_r  = vol_ratio(volume)
    vwap_v = vwap_val(df)

    c1, c2, c3 = close.iloc[-1], close.iloc[-2], close.iloc[-3]
    c10 = close.iloc[-10] if len(close) >= 10 else close.iloc[0]

    pct_5min = ((c1 - close.iloc[-5]) / close.iloc[-5] * 100) if len(close) >= 5 else 0
    pct_10min = ((c1 - c10) / c10 * 100) if c10 != 0 else 0
    pct_3candles = ((c1 - c3) / c3 * 100) if c3 != 0 else 0

    highest_10 = high.iloc[-10:-1].max() if len(high) >= 10 else high.max()
    lowest_10  = low.iloc[-10:-1].min() if len(low) >= 10 else low.min()
    breakout_up = price > highest_10
    breakdown_down = price < lowest_10

    ema_bullish = ema9_v > ema21_v
    ema_bearish = ema9_v < ema21_v
    price_above_ema9 = price > ema9_v
    price_below_ema9 = price < ema9_v

    high_volume = vol_r >= 1.2

    log.info(f"{name} [{cfg['segment']}] | Price={price} | RSI={rsi_v} | "
             f"5min%={r2(pct_5min)}% | 10min%={r2(pct_10min)}% | "
             f"Breakout={'UP' if breakout_up else 'DOWN' if breakdown_down else 'NO'} | Vol={vol_r}x")

    results = []
    for direction in ["CE", "PE"]:
        bull = (direction == "CE")
        score = 0
        reasons = []
        min_move = cfg.get("min_move_pct", 0.05)

        # TIER 1: PRICE ACTION
        if bull and breakout_up:
            score += 4; reasons.append("🚀 Breakout! Price > 10-candle high")
        elif not bull and breakdown_down:
            score += 4; reasons.append("📉 Breakdown! Price < 10-candle low")

        if bull and pct_3candles > min_move:
            score += 3; reasons.append(f"⚡ +{r2(pct_3candles)}% in 3 candles")
        elif not bull and pct_3candles < -min_move:
            score += 3; reasons.append(f"⚡ {r2(pct_3candles)}% in 3 candles")

        if bull and pct_5min > min_move * 0.7:
            score += 2; reasons.append(f"📈 +{r2(pct_5min)}% in 5min")
        elif not bull and pct_5min < -min_move * 0.7:
            score += 2; reasons.append(f"📉 {r2(pct_5min)}% in 5min")

        if bull and pct_10min > min_move:
            score += 2; reasons.append(f"📈 +{r2(pct_10min)}% in 10min")
        elif not bull and pct_10min < -min_move:
            score += 2; reasons.append(f"📉 {r2(pct_10min)}% in 10min")

        # TIER 2: INDICATORS
        if bull:
            if rsi_v < 50:    score += 1; reasons.append(f"RSI {rsi_v} (Bullish)")
            if rsi_v < 35:    score += 1; reasons.append("RSI Oversold")
        else:
            if rsi_v > 50:    score += 1; reasons.append(f"RSI {rsi_v} (Bearish)")
            if rsi_v > 65:    score += 1; reasons.append("RSI Overbought")

        if bull and ema_bullish:
            score += 1; reasons.append("EMA Bullish (9>21)")
            if price_above_ema9: score += 1; reasons.append("Price > EMA9")
        elif not bull and ema_bearish:
            score += 1; reasons.append("EMA Bearish (9<21)")
            if price_below_ema9: score += 1; reasons.append("Price < EMA9")

        if bull and macd_v > 0:
            score += 1; reasons.append(f"MACD +{macd_v}")
        elif not bull and macd_v < 0:
            score += 1; reasons.append(f"MACD {macd_v}")

        if bull and price > vwap_v:
            score += 1; reasons.append("Price > VWAP")
        elif not bull and price < vwap_v:
            score += 1; reasons.append("Price < VWAP")

        if high_volume:
            score += 1; reasons.append(f"🔥 Vol {vol_r}x")

        # TIER 3: CANDLE DIRECTION
        last_bullish = close.iloc[-1] > close.iloc[-2]
        last_bearish = close.iloc[-1] < close.iloc[-2]

        if bull and last_bullish:
            score += 1; reasons.append("Last candle Bullish ✅")
        elif not bull and last_bearish:
            score += 1; reasons.append("Last candle Bearish ✅")

        two_up = close.iloc[-1] > close.iloc[-2] > close.iloc[-3]
        two_down = close.iloc[-1] < close.iloc[-2] < close.iloc[-3]

        if bull and two_up:
            score += 1; reasons.append("2 Consecutive Bullish")
        elif not bull and two_down:
            score += 1; reasons.append("2 Consecutive Bearish")

        log.info(f"  {name} {direction}: SCORE={score} | Reasons={len(reasons)}")

        if score < 1:
            continue

        key = f"{name}_{direction}"
        last = last_signal.get(key)
        if last:
            diff = (datetime.now(IST) - last).total_seconds()
            if diff < 300:
                log.info(f"  ⏱ Cooldown: {key} ({int(diff)}s)")
                continue
        last_signal[key] = datetime.now(IST)

        if cfg["segment"] == "MCX" and name == "GOLD":
            price_inr = round(price * 240, 2)
        else:
            price_inr = price

        strike = nearest_strike(price_inr, cfg["step"])
        entry = int(round((cfg["prem_min"] + cfg["prem_max"]) / 2 / 5) * 5)
        target = entry + cfg["target_pts"]
        sl = entry - cfg["sl_pts"]
        conf = min(95, 40 + score * 6)

        results.append({
            "name": name, "direction": direction, "segment": cfg["segment"],
            "strike": strike, "entry": entry, "target": target, "sl": sl,
            "price": price_inr, "confidence": conf, "score": score,
            "rsi": rsi_v, "ema9": ema9_v, "ema21": ema21_v,
            "macd": macd_v, "vol_r": vol_r, "vwap": vwap_v,
            "atr": 0, "reasons": reasons, "demo": False,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE FORMAT
# ══════════════════════════════════════════════════════════════════════════════

def format_alert(sig: dict) -> str:
    now = datetime.now(IST).strftime("%d %b %Y | %I:%M %p")
    arrow = "📈" if sig["direction"] == "CE" else "📉"
    demo_line = "\n🔸 [DEMO TRADE — Real nahi hai]" if sig.get("demo") else ""
    segment_tag = f" [{sig.get('segment', 'NSE')}]"

    header = (
        "╔══════════════════════════╗\n"
        "   🔔 RUDRA SECURITIES\n"
        "       TRADING ALERT\n"
        "╚══════════════════════════╝"
    )

    trade_info = (
        f"{demo_line}\n"
        f"{arrow} Index: {sig['name']}{segment_tag}\n"
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
        return False
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=format_alert(sig), parse_mode="HTML")
        log.info(f"✅ Channel: {sig['name']} {sig['direction']} [{sig.get('segment','')}] Score={sig['score']}")
        return True
    except Exception as e:
        log.error(f"❌ Channel FAIL: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PRE‑MARKET
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
                df = yf.download(cfg["yf"], period="5d", interval="1d", progress=False, auto_adjust=True)
                if df is None or len(df) < 3: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                cs = df["Close"].squeeze(); os_ = df["Open"].squeeze()
                yc = round(float(cs.iloc[-2]), 2); yo = round(float(os_.iloc[-2]), 2)
                pc = round(float(cs.iloc[-3]), 2); gap = round(yo - pc, 2)
                emoji = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
                lines.append(f"━━━ {name} [{cfg['segment']}] ━━━")
                lines.append(f"   Open: {yo:,.2f} | Close: {yc:,.2f} | Gap: {emoji} {gap:+} pts\n")
            except: pass
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <i>For reference only.</i>")
        await ctx.bot.send_message(chat_id=CHANNEL_ID, text="\n".join(lines), parse_mode="HTML")
    except Exception as e:
        log.error(f"Pre-market: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO SCAN
# ══════════════════════════════════════════════════════════════════════════════

async def smart_scan(ctx: ContextTypes.DEFAULT_TYPE):
    total = 0
    for name, cfg in INDICES.items():
        for sig in analyze_index(name, cfg):
            await post_to_channel(ctx.bot, sig)
            total += 1
            await asyncio.sleep(1)
    if total > 0:
        log.info(f"🔍 {total} signals posted")


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def safe_reply(update: Update, text: str, **kwargs):
    msg = update.effective_message
    if msg:
        try: await msg.reply_html(text, **kwargs)
        except Exception as e: log.error(f"Reply error: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧪 Test Trade", callback_data="test")],
        [InlineKeyboardButton("📊 Manual Scan", callback_data="scan")],
        [InlineKeyboardButton("📈 Status", callback_data="status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await safe_reply(update,
        "🔔 <b>RUDRA SECURITIES v6.1.1</b>\n\n"
        "🚀 <b>Price Action Priority System</b>\n"
        "• Breakout/Breakdown detection\n"
        "• Move % based instant signals\n"
        "• Score threshold: 1\n"
        "• 5-min cooldown only\n\n"
        "📊 NSE + ⛽ MCX — Live\n\n"
        "/test — demo trade\n"
        "📊 Manual Scan — abhi try karo!",
        reply_markup=kb)


async def cmd_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg: return
    sig = random.choice(DEMO_TRADES).copy()
    await msg.reply_html("🧪 <b>TEST MODE</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nChannel mein bhi post ho raha hai...")
    posted = await post_to_channel(ctx.bot, sig)
    await msg.reply_html(format_alert(sig) + ("\n\n✅ Channel post OK" if posted else f"\n\n⚠️ FAIL\nCHANNEL_ID: {CHANNEL_ID}"))


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and ADMIN_ID and user.id != ADMIN_ID:
        await safe_reply(update, "❌ Sirf admin manual scan kar sakta hai.")
        return

    msg = update.effective_message
    if not msg: return

    wait = await msg.reply_text("⏳ Scanning all segments (NSE + MCX)...")
    total = 0

    for name, cfg in INDICES.items():
        sigs = analyze_index(name, cfg)
        for sig in sigs:
            posted = await post_to_channel(ctx.bot, sig)
            ch_txt = "✅" if posted else "⚠️"
            await msg.reply_html(format_alert(sig) + f"\n\nChannel: {ch_txt}")
            total += 1
            await asyncio.sleep(1)

    if total == 0:
        now = datetime.now(IST).strftime("%I:%M %p IST")
        await wait.edit_text(
            f"⚪ <b>Koi signal nahi mila</b>\n\n"
            f"🕐 {now}\n\n"
            f"• Price action + indicators align nahi hue\n"
            f"• Next auto scan in 1 min\n\n"
            f"/test — demo trade",
            parse_mode="HTML"
        )
    else:
        try: await wait.delete()
        except: pass


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(IST).strftime("%d %b %Y | %I:%M %p IST")
    ch = CHANNEL_ID if CHANNEL_ID else "⚠️ NOT SET"
    active = []
    for n, c in INDICES.items():
        if is_market_open_for(c):
            active.append(f"🟢 {n} [{c['segment']}]")
    if not active:
        active.append("🔴 No market open")
    
    await safe_reply(update,
        f"📡 <b>Bot Status v6.1.1</b>\n\n"
        f"🕐 {now}\n"
        f"📢 Channel: <code>{ch}</code>\n"
        f"⚡ Auto Scan: Every 1 min\n"
        f"⏱ Cooldown: 5 min\n"
        f"🎯 Score threshold: 1\n\n"
        f"<b>Active Markets:</b>\n" + "\n".join(active) + "\n\n"
        f"/test — demo trade\n"
        f"📊 /scan — manual scan"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update,
        "📖 <b>Help — v6.1.1</b>\n\n"
        "<b>Commands:</b>\n"
        "/start   — Bot info + buttons\n"
        "/test    — Demo trade\n"
        "/scan    — Manual scan all segments\n"
        "/status  — Market status\n"
        "/help    — Yeh message\n\n"
        "📊 <b>NSE:</b> NIFTY, BANKNIFTY, SENSEX\n"
        "⛽ <b>MCX:</b> CRUDEOIL, NATURALGAS, GOLD\n\n"
        "🚀 Price action priority signals\n"
        "⚠️ Educational purpose only."
    )


async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """FIXED: Button callback handler"""
    q = update.callback_query
    await q.answer()
    
    # Create a proper Update-like object for command functions
    # The issue was effective_message vs message attribute
    class FakeUpdate:
        effective_message = q.message
        effective_user = q.from_user
        callback_query = q
    
    fake = FakeUpdate()
    
    if q.data == "test":
        await cmd_test(fake, ctx)
    elif q.data == "scan":
        await cmd_scan(fake, ctx)
    elif q.data == "status":
        await cmd_status(fake, ctx)
    elif q.data == "help":
        await cmd_help(fake, ctx)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK
# ══════════════════════════════════════════════════════════════════════════════
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "version": "6.1.1"}, 200

@flask_app.route("/webhook", methods=["POST"])
def tv_webhook():
    try:
        data = request.get_json(force=True)
        if not data or data.get("secret") != TV_SECRET: abort(403)
        sig = {
            "name": data.get("index","NIFTY"), "direction": data.get("type","CE").upper(),
            "strike": int(data.get("strike",0)), "entry": int(data.get("entry",0)),
            "sl": int(data.get("sl",0)), "target": int(data.get("target",0)),
            "price": float(data.get("spot",0)), "confidence": int(data.get("confidence",80)),
            "segment": data.get("segment","NSE"), "score": 5, "reasons": ["TradingView"], "demo": False,
        }
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        loop.run_until_complete(post_to_channel(tg_app.bot, sig) if tg_app else None)
        loop.close()
        return {"status":"posted"}, 200
    except Exception as e:
        return {"error":str(e)}, 500

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global tg_app
    if not BOT_TOKEN: raise SystemExit("❌ BOT_TOKEN missing!")
    if not CHANNEL_ID: log.warning("⚠️ CHANNEL_ID missing!")

    tg_app = Application.builder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("test", cmd_test))
    tg_app.add_handler(CommandHandler("scan", cmd_scan))
    tg_app.add_handler(CommandHandler("status", cmd_status))
    tg_app.add_handler(CommandHandler("help", cmd_help))
    tg_app.add_handler(CallbackQueryHandler(button_cb))

    tg_app.job_queue.run_repeating(smart_scan, interval=60, first=10)
    tg_app.job_queue.run_daily(pre_market_post, time=dtime(hour=9, minute=10, tzinfo=IST), days=(0,1,2,3,4))

    threading.Thread(target=run_flask, daemon=True).start()
    log.info("✅ Rudra Securities v6.1.1 — LIVE (Buttons Fixed)")
    tg_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
