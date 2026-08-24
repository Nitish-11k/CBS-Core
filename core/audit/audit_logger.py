"""
Audit Logger module.
Records every mapping change, transformation run, validation run, and export action.
Maintains an append-only log in a separate SQLite database or file.
"""
import sqlite3
import datetime
import getpass
import os
from threading import Lock

class AuditLogger:
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._lock = Lock()
        self._init_db()

    def _init_db(self):
        """Initializes the audit table if it doesn't exist."""
        # Ensure dir exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_table TEXT,
                    row_count INTEGER,
                    status TEXT,
                    details TEXT
                )
            ''')
            conn.commit()
            conn.close()

    def log_action(self, action_type: str, status: str, target_table: str = None, row_count: int = None, details: str = None):
        """
        Logs an action securely.
        Never log full row contents of sensitive columns here.
        """
        timestamp = datetime.datetime.now().isoformat()
        try:
            username = getpass.getuser()
        except Exception:
            username = "unknown"
            
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_log (timestamp, username, action_type, target_table, row_count, status, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, username, action_type, target_table, row_count, status, details))
            conn.commit()
            conn.close()
