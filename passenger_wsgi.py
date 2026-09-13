#!/usr/bin/env python3
"""WSGI entry point for alwaysdata"""

import os
import sys
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

os.environ.setdefault("FLASK_ENV", "production")

def start_background():
    import database as db
    from main import start_scheduler, init_defaults, update_prices_sync
    
    db.init_db()
    init_defaults()
    start_scheduler()
    update_prices_sync()
    logger.info("Background services started")

_start_done = False
_lock = threading.Lock()

def ensure_started():
    global _start_done
    if not _start_done:
        with _lock:
            if not _start_done:
                try:
                    start_background()
                except Exception as e:
                    logger.error(f"Start failed: {e}")
                _start_done = True

from main import app as _flask_app

class Wrapper:
    def __init__(self, app):
        self.app = app
        self.started = False
    
    def __call__(self, environ, start_response):
        if not self.started:
            ensure_started()
            self.started = True
        return self.app(environ, start_response)

application = Wrapper(_flask_app)

if __name__ == "__main__":
    ensure_started()
    _flask_app.run(host="0.0.0.0", port=5000)
