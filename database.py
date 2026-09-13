import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS monitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            source TEXT,
            code TEXT,
            label TEXT,
            format TEXT,
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            extra TEXT DEFAULT '{}'
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            monitor_id INTEGER PRIMARY KEY,
            data TEXT,
            updated_at REAL
        )
    """)
    
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_monitors(enabled_only=False):
    conn = get_db()
    c = conn.cursor()
    if enabled_only:
        c.execute("SELECT * FROM monitors WHERE enabled = 1 ORDER BY sort_order, id")
    else:
        c.execute("SELECT * FROM monitors ORDER BY sort_order, id")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_monitor(monitor_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_monitor(monitor_id, **kwargs):
    conn = get_db()
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [monitor_id]
    c.execute(f"UPDATE monitors SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()

def add_monitor(name, source, code, label, fmt, sort_order=0, extra=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO monitors (name, source, code, label, format, sort_order, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, source, code, label, fmt, sort_order, json.dumps(extra or {})))
    conn.commit()
    conn.close()

def delete_monitor(monitor_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM monitors WHERE id = ?", (monitor_id,))
    c.execute("DELETE FROM cache WHERE monitor_id = ?", (monitor_id,))
    conn.commit()
    conn.close()

def get_cache(monitor_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT data, updated_at FROM cache WHERE monitor_id = ?", (monitor_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0]), row[1]
    return None, None

def set_cache(monitor_id, data, updated_at):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cache (monitor_id, data, updated_at) VALUES (?, ?, ?)",
              (monitor_id, json.dumps(data), updated_at))
    conn.commit()
    conn.close()

def get_all_settings():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    rows = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    return rows
