#!/usr/bin/env python3
"""
Crypto Telegraph API
- Fetches crypto prices from Bitpin & Frankfurter
- Publishes auto-updated pages on telegra.ph (with Telegram Instant View)
- REST API for monitor management
- Runs on alwaysdata via WSGI
"""

import os
import sys
import json
import logging
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.insert(0, os.path.dirname(__file__))
import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============== Telegraph API ==============

TELEGRAPH_API = "https://api.telegra.ph"

def telegraph_request(method, params=None):
    """Make a request to the Telegraph API"""
    url = f"{TELEGRAPH_API}/{method}"
    if params:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return result.get("result")
            else:
                logger.error(f"Telegraph API error: {result}")
                return None
    except Exception as e:
        logger.error(f"Telegraph request failed: {e}")
        return None

def create_telegraph_account(short_name, author_name="Crypto Price"):
    """Create a new Telegraph account and return auth_token"""
    result = telegraph_request("createAccount", {
        "short_name": short_name,
        "author_name": author_name
    })
    return result  # returns dict with access_token, auth_url, etc.

def create_telegraph_page(title, content, auth_token, author_name="Crypto Price", author_url=""):
    """Create a new Telegraph page, returns page object with url"""
    result = telegraph_request("createPage", {
        "access_token": auth_token,
        "title": title,
        "author_name": author_name,
        "author_url": author_url,
        "content": content,  # JSON-serialized array of Node
        "return_content": False
    })
    return result  # returns dict with url, path, etc.

def edit_telegraph_page(path, title, content, auth_token, author_name="Crypto Price", author_url=""):
    """Edit an existing Telegraph page"""
    result = telegraph_request("editPage", {
        "access_token": auth_token,
        "path": path,
        "title": title,
        "author_name": author_name,
        "author_url": author_url,
        "content": content,
        "return_content": False
    })
    return result

# ============== Content Builder ==============

def build_telegraph_content(monitors, prices):
    """Build Telegraph-compatible content (list of nodes) from prices"""
    from message_formatter import format_number
    
    nodes = []
    
    # Header
    nodes.append({
        "tag": "h3",
        "children": ["📊 قیمت‌های لحظه‌ای"]
    })
    
    # Timestamp
    nodes.append({
        "tag": "em",
        "children": [f"آخرین به‌روزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    })
    
    nodes.append({"tag": "hr"})
    
    # Price lines
    for m in monitors:
        mid = m["id"]
        if mid not in prices:
            continue
        
        p = prices[mid]
        price = p.get("price", 0)
        change = p.get("change", 0)
        
        extra = m.get("extra", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except:
                extra = {}
        
        decimals = extra.get("decimals", 0)
        unit = extra.get("unit", "")
        show_change = extra.get("show_change", True)
        
        price_str = format_number(price, decimals)
        if unit:
            price_str += f" {unit}"
        
        if change > 0:
            change_text = f"🟢 +{change:.2f}%"
        elif change < 0:
            change_text = f"🔴 {change:.2f}%"
        else:
            change_text = f"⚪ 0%"
        
        if show_change:
            text = f"<b>{m['label']}</b>: {price_str} <i>({change_text})</i>"
        else:
            text = f"<b>{m['label']}</b>: {price_str}"
        
        nodes.append({
            "tag": "p",
            "children": [text]
        })
    
    nodes.append({"tag": "hr"})
    nodes.append({
        "tag": "em",
        "children": ["🔄 هر ۲ ساعت به‌روزرسانی می‌شود"]
    })
    
    return nodes

# ============== Price Fetcher ==============

async def update_prices():
    """Fetch latest prices and update cache"""
    monitors = db.get_monitors(enabled_only=True)
    if not monitors:
        return {}
    
    from price_fetcher import fetch_all
    prices = await fetch_all(monitors)
    
    now = datetime.now().timestamp()
    for mid, data in prices.items():
        db.set_cache(mid, data, now)
    
    return prices

def update_prices_sync():
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(update_prices())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"update_prices_sync error: {e}")
        return {}

# ============== Auto-publish to Telegraph ==============

def update_telegraph_page():
    """Fetch prices and update/create Telegraph page"""
    auth_token = db.get_setting("telegraph_token")
    page_path = db.get_setting("telegraph_path")
    
    if not auth_token:
        logger.warning("No Telegraph token set - skipping page update")
        return
    
    monitors = db.get_monitors(enabled_only=True)
    if not monitors:
        return
    
    # Get prices
    prices = update_prices_sync()
    if not prices:
        logger.warning("Could not fetch prices")
        return
    
    # Build content
    content = build_telegraph_content(monitors, prices)
    
    title = "📊 قیمت‌های لحظه‌ای ارز دیجیتال"
    
    try:
        if page_path:
            # Edit existing page
            result = edit_telegraph_page(
                path=page_path,
                title=title,
                content=content,
                auth_token=auth_token
            )
        else:
            # Create new page
            result = create_telegraph_page(
                title=title,
                content=content,
                auth_token=auth_token
            )
            if result and "path" in result:
                db.set_setting("telegraph_path", result["path"])
                logger.info(f"Created new Telegraph page: {result['url']}")
        
        if result:
            db.set_setting("telegraph_url", result.get("url", ""))
            logger.info(f"Telegraph page updated: {result.get('url')}")
        else:
            logger.error("Telegraph page update failed")
    except Exception as e:
        logger.error(f"Telegraph update error: {e}")

# ============== Scheduler ==============

scheduler = None

def start_scheduler():
    global scheduler
    if scheduler:
        return
    
    interval = int(db.get_setting("update_interval_minutes", "120"))
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_telegraph_page, "interval", minutes=interval, id="telegraph_update")
    scheduler.start()
    logger.info(f"Scheduler started: every {interval} minutes")

def stop_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None

def restart_scheduler():
    stop_scheduler()
    start_scheduler()

# ============== Flask API ==============

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "crypto-telegraph-secret")

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "scheduler_running": scheduler is not None and scheduler.running
    })

@app.route("/api/monitors")
def get_monitors():
    monitors = db.get_monitors()
    result = []
    for m in monitors:
        m_dict = dict(m)
        m_dict["extra"] = json.loads(m_dict.get("extra", "{}"))
        data, updated_at = db.get_cache(m["id"])
        m_dict["cached_price"] = data
        m_dict["cached_at"] = updated_at
        result.append(m_dict)
    return jsonify(result)

@app.route("/api/monitors", methods=["POST"])
def add_monitor():
    data = request.json
    required = ["name", "source", "code", "label"]
    if not all(data.get(f) for f in required):
        return jsonify({"error": "Missing fields"}), 400
    
    db.add_monitor(
        name=data["name"],
        source=data["source"],
        code=data["code"],
        label=data["label"],
        fmt=data.get("format", "{}"),
        sort_order=data.get("sort_order", 0),
        extra=data.get("extra", {})
    )
    return jsonify({"success": True})

@app.route("/api/monitors/<int:mid>", methods=["DELETE"])
def delete_monitor(mid):
    db.delete_monitor(mid)
    return jsonify({"success": True})

@app.route("/api/monitors/<int:mid>", methods=["PUT"])
def edit_monitor(mid):
    data = request.json
    allowed = ["name", "source", "code", "label", "format", "enabled", "sort_order", "extra"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if "extra" in updates and isinstance(updates["extra"], dict):
        updates["extra"] = json.dumps(updates["extra"])
    db.update_monitor(mid, **updates)
    return jsonify({"success": True})

@app.route("/api/toggle/<int:mid>", methods=["POST"])
def toggle_monitor(mid):
    data = request.json
    db.update_monitor(mid, enabled=1 if data.get("enabled") else 0)
    return jsonify({"success": True})

@app.route("/api/prices")
def get_prices():
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
    prices = update_prices_sync()
    return jsonify({"success": True, "count": len(prices)})

@app.route("/api/telegraph/status")
def telegraph_status():
    token = db.get_setting("telegraph_token")
    path = db.get_setting("telegraph_path")
    url = db.get_setting("telegraph_url")
    
    return jsonify({
        "configured": bool(token),
        "has_page": bool(path),
        "url": url or None,
        "path": path or None
    })

@app.route("/api/telegraph/create_account", methods=["POST"])
def telegraph_create_account():
    data = request.json
    short_name = data.get("short_name", "cryptoprice")
    result = create_telegraph_account(short_name, "Crypto Price")
    
    if result:
        db.set_setting("telegraph_token", result["access_token"])
        return jsonify({
            "success": True,
            "auth_url": result.get("auth_url"),
            "token": result["access_token"]
        })
    return jsonify({"error": "Failed to create account"}), 500

@app.route("/api/telegraph/update", methods=["POST"])
def telegraph_update():
    update_telegraph_page()
    return jsonify({
        "success": True,
        "url": db.get_setting("telegraph_url")
    })

@app.route("/api/settings")
def get_settings():
    return jsonify(db.get_all_settings())

@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json
    for k, v in data.items():
        db.set_setting(k, str(v))
    if "update_interval_minutes" in data:
        restart_scheduler()
    return jsonify({"success": True})

@app.route("/api/bot/start", methods=["POST"])
def bot_start():
    start_scheduler()
    return jsonify({"success": True})

@app.route("/api/bot/stop", methods=["POST"])
def bot_stop():
    stop_scheduler()
    return jsonify({"success": True})

# ============== Defaults ==============

def init_defaults():
    monitors = db.get_monitors()
    if monitors:
        return
    
    defaults = [
        {"name": "usdt_irt", "source": "bitpin", "code": "USDT_IRT", "label": "تتر",
         "sort_order": 1, "extra": {"decimals": 0, "unit": "تومان", "show_change": True}},
        {"name": "trx_irt", "source": "bitpin", "code": "TRX_IRT", "label": "ترون",
         "sort_order": 2, "extra": {"decimals": 0, "unit": "تومان", "show_change": True}},
        {"name": "paxg_usdt", "source": "bitpin", "code": "PAXG_USDT", "label": "طلای دیجیتال",
         "sort_order": 3, "extra": {"decimals": 2, "unit": "تتر", "show_change": True}},
        {"name": "xau_usd", "source": "frankfurter", "code": "XAU", "label": "انس طلا",
         "sort_order": 4, "extra": {"decimals": 4, "unit": "دلار/انس", "show_change": False}},
        {"name": "gbp_usd", "source": "frankfurter", "code": "GBP", "label": "پوند انگلیس",
         "sort_order": 5, "extra": {"decimals": 4, "unit": "دلار", "show_change": False}},
        {"name": "cny_usd", "source": "frankfurter", "code": "CNY", "label": "یوان چین",
         "sort_order": 6, "extra": {"decimals": 4, "unit": "دلار", "show_change": False}},
    ]
    for m in defaults:
        db.add_monitor(m["name"], m["source"], m["code"], m["label"], "{}", m["sort_order"], m["extra"])
    logger.info("Defaults initialized")

# ============== Main ==============

def main():
    db.init_db()
    init_defaults()
    start_scheduler()
    update_prices_sync()
    
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
