#!/usr/bin/env python3
"""
Crypto Paragraph API - WSGI entry point for alwaysdata
alwaysdata uses Passenger (WSGI) to serve Python apps.
"""

import os
import sys
import threading
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add app directory to path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# Environment
os.environ.setdefault("FLASK_ENV", "production")

def start_background_services():
    """Start scheduler and telegram bot in background threads"""
    import database as db
    from main import start_scheduler, update_prices_sync, run_telegram_bot
    
    logger.info("Initializing database...")
    db.init_db()
    
    from main import init_default_monitors
    init_default_monitors()
    
    logger.info("Starting scheduler...")
    start_scheduler()
    
    # Initial price fetch
    update_prices_sync()
    
    # Start telegram bot in daemon thread
    logger.info("Starting telegram bot thread...")
    tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    tg_thread.start()
    
    logger.info("All background services started")

# Start background services when the WSGI app loads
_start_done = False
_lock = threading.Lock()

def ensure_started():
    global _start_done
    if not _start_done:
        with _lock:
            if not _start_done:
                try:
                    start_background_services()
                except Exception as e:
                    logger.error(f"Failed to start background services: {e}")
                _start_done = True

# Import Flask app and wrap with startup
from main import app as _flask_app

class AppWrapper:
    """WSGI wrapper that starts background services on first request"""
    def __init__(self, app):
        self.app = app
        self.started = False
    
    def __call__(self, environ, start_response):
        if not self.started:
            ensure_started()
            self.started = True
        return self.app(environ, start_response)

# The WSGI application object
application = AppWrapper(_flask_app)

# For direct testing
if __name__ == "__main__":
    ensure_started()
    _flask_app.run(host="0.0.0.0", port=5000)
