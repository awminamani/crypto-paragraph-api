#!/usr/bin/env python3
"""
Crypto Price Paragraph API
Runs on alwaysdata free plan.
Provides REST API for the dashboard (Vercel) and runs the scheduler + telegram bot.
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# Add parent to path
sys.path.insert(0, os.path.dirname(__file__))

import database as db
from price_fetcher import fetch_all
from message_formatter import build_full_message

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "crypto-bot-secret-key-change-me")

# Global state
scheduler = None
bot_instance = None

def get_update_callback():
    """Get the telegram update callback"""
    import __main__
    return getattr(__main__, 'TG_UPDATE_CALLBACK', None)

async def update_prices():
    """Fetch latest prices and update cache"""
    monitors = db.get_monitors(enabled_only=True)
    if not monitors:
        return {}
    
    prices = await fetch_all(monitors)
    
    now = datetime.now().timestamp()
    for mid, data in prices.items():
        db.set_cache(mid, data, now)
    
    return prices

def update_prices_sync():
    """Synchronous wrapper for update_prices"""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(update_prices())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"update_prices_sync error: {e}")
        return {}

def update_telegram_message():
    """Update the Telegram message with latest prices"""
    callback = get_update_callback()
    if not callback:
        logger.warning("No telegram callback set")
        return
    
    try:
        monitors = db.get_monitors(enabled_only=True)
        prices = {}
        
        for m in monitors:
            data, updated_at = db.get_cache(m["id"])
            if data:
                prices[m["id"]] = data
        
        if not prices:
            prices = update_prices_sync()
        
        template = db.get_setting("template", "▫️ {label}: {price} ({change})")
        message = build_full_message(monitors, prices, template)
        
        callback(message)
        logger.info(f"Telegram message updated at {datetime.now()}")
    except Exception as e:
        logger.error(f"Error updating telegram message: {e}")

# ============== Scheduler ==============

def start_scheduler():
    """Start the background scheduler"""
    global scheduler
    if scheduler:
        return
    
    interval = int(db.get_setting("update_interval_minutes", "120"))
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_telegram_message, "interval", minutes=interval, id="update_job")
    scheduler.start()
    logger.info(f"Scheduler started with {interval} minute interval")

def stop_scheduler():
    """Stop the scheduler"""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")

def restart_scheduler():
    """Restart the scheduler with new interval"""
    stop_scheduler()
    start_scheduler()

# ============== Default Monitors ==============

def init_default_monitors():
    """Initialize default monitors if none exist"""
    monitors = db.get_monitors()
    if monitors:
        return
    
    defaults = [
        {
            "name": "usdt_irt",
            "source": "bitpin",
            "code": "USDT_IRT",
            "label": "تتر",
            "format": "{}",
            "sort_order": 1,
            "extra": {"decimals": 0, "unit": "تومان", "show_change": True}
        },
        {
            "name": "trx_irt",
            "source": "bitpin",
            "code": "TRX_IRT",
            "label": "ترون",
            "format": "{}",
            "sort_order": 2,
            "extra": {"decimals": 0, "unit": "تومان", "show_change": True}
        },
        {
            "name": "paxg_usdt",
            "source": "bitpin",
            "code": "PAXG_USDT",
            "label": "طلای دیجیتال",
            "format": "{}",
            "sort_order": 3,
            "extra": {"decimals": 2, "unit": "تتر", "show_change": True}
        },
        {
            "name": "xau_usd",
            "source": "frankfurter",
            "code": "XAU",
            "label": "انس طلا",
            "format": "{}",
            "sort_order": 4,
            "extra": {"decimals": 4, "unit": "دلار/انس", "show_change": False}
        },
        {
            "name": "gbp_usd",
            "source": "frankfurter",
            "code": "GBP",
            "label": "پوند انگلیس",
            "format": "{}",
            "sort_order": 5,
            "extra": {"decimals": 4, "unit": "دلار", "show_change": False}
        },
        {
            "name": "cny_usd",
            "source": "frankfurter",
            "code": "CNY",
            "label": "یوان چین",
            "format": "{}",
            "sort_order": 6,
            "extra": {"decimals": 4, "unit": "دلار", "show_change": False}
        },
    ]
    
    for m in defaults:
        db.add_monitor(
            name=m["name"],
            source=m["source"],
            code=m["code"],
            label=m["label"],
            fmt=m["format"],
            sort_order=m["sort_order"],
            extra=m["extra"]
        )
    
    logger.info(f"Initialized {len(defaults)} default monitors")

# ============== API Routes ==============

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "scheduler_running": scheduler is not None and scheduler.running
    })

@app.route("/api/monitors", methods=["GET"])
def get_monitors_api():
    """Get all monitors with their cached prices"""
    monitors = db.get_monitors()
    result = []
    for m in monitors:
        data, updated_at = db.get_cache(m["id"])
        m_dict = dict(m)
        m_dict["extra"] = json.loads(m_dict.get("extra", "{}"))
        m_dict["cached_price"] = data
        m_dict["cached_at"] = updated_at
        result.append(m_dict)
    return jsonify(result)

@app.route("/api/monitors", methods=["POST"])
def add_monitor_api():
    """Add a new monitor"""
    data = request.json
    name = data.get("name")
    source = data.get("source")
    code = data.get("code")
    label = data.get("label")
    fmt = data.get("format", "{}")
    extra = data.get("extra", {})
    sort_order = data.get("sort_order", 0)
    
    if not all([name, source, code, label]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    
    db.add_monitor(name, source, code, label, fmt, sort_order, extra)
    
    # Fetch new prices immediately
    update_prices_sync()
    
    return jsonify({"success": True})

@app.route("/api/monitors/<int:monitor_id>", methods=["PUT"])
def update_monitor_api(monitor_id):
    """Update a monitor"""
    data = request.json
    allowed = ["name", "source", "code", "label", "format", "enabled", "sort_order", "extra"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if "extra" in updates and isinstance(updates["extra"], dict):
        updates["extra"] = json.dumps(updates["extra"])
    db.update_monitor(monitor_id, **updates)
    return jsonify({"success": True})

@app.route("/api/monitors/<int:monitor_id>", methods=["DELETE"])
def delete_monitor_api(monitor_id):
    """Delete a monitor"""
    db.delete_monitor(monitor_id)
    return jsonify({"success": True})

@app.route("/api/toggle/<int:monitor_id>", methods=["POST"])
def toggle_monitor_api(monitor_id):
    """Toggle monitor enabled state"""
    data = request.json
    enabled = data.get("enabled", False)
    db.update_monitor(monitor_id, enabled=1 if enabled else 0)
    return jsonify({"success": True})

@app.route("/api/prices", methods=["GET"])
def get_prices():
    """Get all current prices (from cache)"""
    monitors = db.get_monitors(enabled_only=True)
    result = {}
    for m in monitors:
        data, updated_at = db.get_cache(m["id"])
        if data:
            result[m["code"]] = {
                "label": m["label"],
                "source": m["source"],
                "code": m["code"],
                "price": data.get("price"),
                "change": data.get("change"),
                "updated_at": updated_at,
                "extra": json.loads(m.get("extra", "{}"))
            }
    return jsonify(result)

@app.route("/api/prices/refresh", methods=["POST"])
def refresh_prices():
    """Force refresh all prices"""
    prices = update_prices_sync()
    return jsonify({"success": True, "count": len(prices)})

@app.route("/api/message", methods=["GET"])
def get_message():
    """Get the formatted message that would be sent to Telegram"""
    monitors = db.get_monitors(enabled_only=True)
    prices = {}
    
    for m in monitors:
        data, updated_at = db.get_cache(m["id"])
        if data:
            prices[m["id"]] = data
    
    template = db.get_setting("template", "▫️ {label}: {price} ({change})")
    message = build_full_message(monitors, prices, template)
    return jsonify({"message": message})

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Get all settings"""
    return jsonify(db.get_all_settings())

@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Update settings"""
    data = request.json
    for key, value in data.items():
        db.set_setting(key, str(value))
    
    if "update_interval_minutes" in data:
        restart_scheduler()
    
    return jsonify({"success": True})

@app.route("/api/bot/start", methods=["POST"])
def start_bot():
    """Start the scheduler"""
    start_scheduler()
    return jsonify({"success": True})

@app.route("/api/bot/stop", methods=["POST"])
def stop_bot():
    """Stop the scheduler"""
    stop_scheduler()
    return jsonify({"success": True})

@app.route("/api/bot/status", methods=["GET"])
def bot_status():
    """Get bot status"""
    return jsonify({
        "scheduler_running": scheduler is not None and scheduler.running,
        "monitors_count": len(db.get_monitors(enabled_only=True)),
        "settings": db.get_all_settings()
    })

@app.route("/api/telegram/update", methods=["POST"])
def telegram_update():
    """Force update Telegram message"""
    update_telegram_message()
    return jsonify({"success": True})

# ============== Telegram Bot Integration ==============

def run_telegram_bot():
    """Run telegram bot in a separate thread"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set - telegram bot disabled")
        return
    
    try:
        from telegram import Update, Bot
        from telegram.ext import Application, CommandHandler, ContextTypes
        
        async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            existing_msg_id = db.get_setting(f"msg_id_{chat_id}")
            
            monitors = db.get_monitors(enabled_only=True)
            prices = {}
            
            for m in monitors:
                data, updated_at = db.get_cache(m["id"])
                if data:
                    prices[m["id"]] = data
            
            if not prices:
                # Run async update_prices in sync context
                import asyncio
                loop = asyncio.new_event_loop()
                prices = loop.run_until_complete(update_prices())
                loop.close()
            
            template = db.get_setting("template", "▫️ {label}: {price} ({change})")
            message = build_full_message(monitors, prices, template)
            
            if existing_msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=int(existing_msg_id),
                        text=message,
                        parse_mode="Markdown"
                    )
                    await update.effective_message.reply_text("✅ پیام قبلی به‌روزرسانی شد!")
                    return
                except Exception as e:
                    logger.warning(f"Could not edit message: {e}")
            
            sent_msg = await update.effective_message.reply_text(
                message, parse_mode="Markdown"
            )
            
            db.set_setting(f"msg_id_{chat_id}", str(sent_msg.message_id))
            db.set_setting(f"chat_id_{chat_id}", str(chat_id))
            
            logger.info(f"New price message sent to {chat_id}")
        
        async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Run sync update
            loop = asyncio.new_event_loop()
            loop.run_until_complete(update_prices())
            loop.close()
            update_telegram_message()
            await update.effective_message.reply_text("✅ قیمت‌ها به‌روزرسانی شد!")
        
        async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            monitors = db.get_monitors(enabled_only=True)
            status_text = f"📊 **وضعیت بات**\n\n🔄 مانیتورها: {len(monitors)}\n⏱ فاصله: {db.get_setting('update_interval_minutes', '120')} دقیقه"
            await update.effective_message.reply_text(status_text, parse_mode="Markdown")
        
        def message_update_callback(message_text: str):
            """Callback to update all stored telegram messages"""
            settings = db.get_all_settings()
            for key, value in settings.items():
                if key.startswith("chat_id_"):
                    chat_id = value
                    msg_id = settings.get(f"msg_id_{chat_id}")
                    if msg_id:
                        try:
                            # Use existing bot app to edit
                            import asyncio
                            async def do_edit():
                                from telegram import Bot as Bot2
                                bot2 = Bot2(token=token)
                                await bot2.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=int(msg_id),
                                    text=message_text,
                                    parse_mode="Markdown"
                                )
                            asyncio.run(do_edit())
                            logger.info(f"Updated telegram message for chat {chat_id}")
                        except Exception as e:
                            logger.error(f"Failed to update {chat_id}: {e}")
        
        # Set the callback in main module
        main_mod = sys.modules.get('__main__')
        if main_mod:
            setattr(main_mod, 'TG_UPDATE_CALLBACK', message_update_callback)
        
        # Build and run app
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("update", update_cmd))
        app.add_handler(CommandHandler("status", status_cmd))
        
        logger.info("Telegram bot thread starting...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")

# ============== Main ==============

def main():
    """Main entry point"""
    db.init_db()
    init_default_monitors()
    
    # Start scheduler
    start_scheduler()
    
    # Initial price fetch
    update_prices_sync()
    
    # Start telegram bot in background thread
    import threading
    tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    tg_thread.start()
    logger.info("Telegram bot thread started")
    
    # Get port from environment (alwaysdata uses specific port)
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting API server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)

if __name__ == "__main__":
    main()
