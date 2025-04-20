from flask_sqlalchemy import SQLAlchemy
from flask import current_app, request, session, redirect, url_for, render_template
from threading import Lock
import sqlite3
import time
import os
from functools import wraps

db = SQLAlchemy()

class RateLimiter:
    def __init__(self):
        self.storage_path = None
        self.lock = Lock()
        
    def init_app(self, app):
        self.storage_path = app.config['SQLALCHEMY_BINDS']['rate_limit'].replace('sqlite:///', '')
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS rate_limits
                          (key TEXT PRIMARY KEY, count INTEGER, timestamp REAL)''')

    def limit(self, rate_limit):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                rate, window = self._parse_rate(rate_limit)
                if None in (rate, window):
                    return f(*args, **kwargs)

                key = f"{request.endpoint}:{request.remote_addr}"

                with self.lock:
                    with sqlite3.connect(self.storage_path) as conn:
                        conn.execute('DELETE FROM rate_limits WHERE timestamp < ?', 
                                    (time.time() - window,))
                        cursor = conn.execute(
                            '''SELECT count, timestamp FROM rate_limits WHERE key = ?''',
                            (key,)
                        )
                        result = cursor.fetchone()
                        now = time.time()

                        if result:
                            count = result[0] + 1
                        else:
                            count = 1

                        conn.execute('''INSERT OR REPLACE INTO rate_limits 
                                    VALUES (?, ?, ?)''', (key, count, now))

                        if count > rate:
                            return render_template('rate_limit.html'), 429

                return f(*args, **kwargs)
            return wrapper
        return decorator

    def _parse_rate(self, rate_limit):
        try:
            rate, period = rate_limit.split('/', 1)
            return (int(rate.strip()), self._period_to_seconds(period.strip()))
        except:
            return (None, None)

    def _period_to_seconds(self, period):
        units = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        period = period.rstrip('s').lower()
        return next((v for k, v in units.items() if k in period), None)

class SecurityManager:
    def __init__(self):
        self.db_path = None
        self.lock = Lock()
        
    def init_app(self, app):
        self.db_path = app.config['SQLALCHEMY_BINDS']['security'].replace('sqlite:///', '')
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS blocked_ips
                          (ip TEXT PRIMARY KEY, expires REAL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS failed_attempts
                          (ip TEXT, timestamp REAL)''')

    def check_blocked(self):
        ip = request.remote_addr
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM blocked_ips WHERE expires <= ?', (time.time(),))
            cursor = conn.execute('SELECT expires FROM blocked_ips WHERE ip = ?', (ip,))
            return bool(cursor.fetchone())

    def track_failed_attempt(self, ip):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM failed_attempts WHERE timestamp < ?',
                          (time.time() - current_app.config['BLOCK_DURATION'],))
                conn.execute('INSERT INTO failed_attempts VALUES (?, ?)', (ip, time.time()))
                
                cursor = conn.execute('SELECT COUNT(*) FROM failed_attempts WHERE ip = ?', (ip,))
                if cursor.fetchone()[0] >= current_app.config['MAX_FAILED_ATTEMPTS']:
                    expires = time.time() + current_app.config['BLOCK_DURATION']
                    conn.execute('INSERT OR REPLACE INTO blocked_ips VALUES (?, ?)', (ip, expires))

    def reset_failed_attempts(self, ip):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM failed_attempts WHERE ip = ?', (ip,))
                conn.execute('DELETE FROM blocked_ips WHERE ip = ?', (ip,))

    def requires_captcha(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_app.config['CAPTCHA_ENABLED'] and not session.get('captcha_passed'):
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute('''SELECT COUNT(*) FROM failed_attempts 
                                          WHERE ip = ? AND timestamp > ?''',
                                      (request.remote_addr, time.time() - 3600))
                    if cursor.fetchone()[0] >= 2:
                        return redirect(url_for('captcha_challenge', next=request.url))
            return f(*args, **kwargs)
        return wrapper

# Initialize extensions
limiter = RateLimiter()
security = SecurityManager()