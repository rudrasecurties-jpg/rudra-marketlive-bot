import os
@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot Running"})


@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        if data.get("secret") != TV_SECRET:
            return jsonify({"error": "Invalid Secret"}), 403

        signal = {
            "name": data.get("index", "NIFTY"),
            "direction": data.get("type", "CE"),
            "strike": int(float(data.get("strike", 0))),
            "entry": int(float(data.get("entry", 0))),
            "sl": int(float(data.get("sl", 0))),
            "target": int(float(data.get("target", 0))),
            "price": float(data.get("spot", 0)),
            "confidence": int(data.get("confidence", 80)),
            "reason": data.get("reason", "TradingView Alert"),
        }

        async def send():
            await post_signal(signal)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send())
        loop.close()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════
# RUN FLASK
# ═══════════════════════════════════════
def run_flask():
    flask_app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════
def main():
    threading.Thread(target=run_flask, daemon=True).start()

    log.info("🚀 Bot Started Successfully")

    app.run_polling()


if __name__ == "__main__":
    main()
