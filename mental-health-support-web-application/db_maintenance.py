import sqlite3
import time

def cleanup_dbs():
    # Clean rate limit database
    with sqlite3.connect('rate_limit.db') as conn:
        conn.execute('''DELETE FROM rate_limits 
                      WHERE timestamp < ?''',
                   (time.time() - 86400,))  # 24h retention

    # Clean security database
    with sqlite3.connect('security.db') as conn:
        conn.execute('''DELETE FROM blocked_ips 
                      WHERE expires < ?''',
                   (time.time(),))
        conn.execute('''DELETE FROM failed_attempts 
                      WHERE timestamp < ?''',
                   (time.time() - 604800))  # 1 week retention

if __name__ == '__main__':
    cleanup_dbs()