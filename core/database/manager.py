import os
import sqlite3
import threading
from typing import List, Tuple, Dict
from models.telemetry import TraceBurst

class DatabaseManager:
    """Manages SQLite database storage for sessions, trace bursts, and system events."""
    
    def __init__(self, config=None):
        db_dir = config.sqlite_database_directory if config else os.path.abspath(os.getcwd())
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.db_path = os.path.join(db_dir, "telemetry.db")
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        self._init_db()

    def _init_db(self):
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            cursor = self.conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                burst_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                source_type TEXT,
                notes TEXT
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trace_bursts (
                burst_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                burst_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                peak_voltage REAL,
                fall_time_us REAL,
                avg_fall_time_us REAL,
                channel INTEGER DEFAULT 0,
                trace_data TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL
            )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bursts_session ON trace_bursts(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bursts_time ON trace_bursts(timestamp)')
            
            self.conn.commit()

    def create_session(self, session_id: str, source_type: str, name: str = None):
        from datetime import datetime
        with self._lock:
            start_time = datetime.now().isoformat()
            self.conn.execute(
                "INSERT INTO sessions (session_id, name, start_time, source_type) VALUES (?, ?, ?, ?)",
                (session_id, name or session_id, start_time, source_type)
            )
            self.conn.commit()

    def end_session(self, session_id: str, status: str = 'completed'):
        from datetime import datetime
        with self._lock:
            end_time = datetime.now().isoformat()
            self.conn.execute(
                "UPDATE sessions SET end_time = ?, status = ? WHERE session_id = ?",
                (end_time, status, session_id)
            )
            self.conn.commit()

    def insert_burst(self, session_id: str, burst: TraceBurst):
        with self._lock:
            trace_json = burst.trace_to_json()
            self.conn.execute('''
                INSERT INTO trace_bursts (
                    session_id, burst_index, timestamp, peak_voltage, 
                    fall_time_us, avg_fall_time_us, channel, trace_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, burst.burst_id, burst.timestamp.isoformat(), 
                burst.peak_voltage, burst.fall_time_us, burst.avg_fall_time_us,
                burst.channel, trace_json
            ))
            self.conn.execute(
                "UPDATE sessions SET burst_count = burst_count + 1 WHERE session_id = ?",
                (session_id,)
            )
            self.conn.commit()

    def get_all_sessions(self, search_term: str = None) -> List[Tuple]:
        with self._lock:
            cursor = self.conn.cursor()
            if search_term:
                cursor.execute(
                    "SELECT * FROM sessions WHERE name LIKE ? OR session_id LIKE ? ORDER BY start_time DESC",
                    (f"%{search_term}%", f"%{search_term}%")
                )
            else:
                cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            return cursor.fetchall()

    def get_session_display_list(self) -> List[str]:
        sessions = self.get_all_sessions()
        return [f"{s[1]} ({s[0]})" for s in sessions]

    def get_session_bursts(self, session_id: str) -> List[TraceBurst]:
        from datetime import datetime
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM trace_bursts WHERE session_id = ? ORDER BY burst_index ASC", (session_id,))
            rows = cursor.fetchall()
            
            bursts = []
            for row in rows:
                burst = TraceBurst(
                    burst_id=row[2],
                    timestamp=datetime.fromisoformat(row[3]),
                    trace_points=TraceBurst.trace_from_json(row[8]),
                    peak_voltage=row[4],
                    fall_time_us=row[5],
                    avg_fall_time_us=row[6],
                    channel=row[7]
                )
                bursts.append(burst)
            return bursts

    def get_session_by_id(self, session_id: str) -> Dict:
        with self._lock:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            self.conn.row_factory = None
            return dict(row) if row else None

    def rename_session(self, session_id: str, new_name: str):
        with self._lock:
            self.conn.execute("UPDATE sessions SET name = ? WHERE session_id = ?", (new_name, session_id))
            self.conn.commit()

    def delete_session(self, session_id: str):
        with self._lock:
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            self.conn.commit()

    def log_event(self, event_type: str, message: str):
        from datetime import datetime
        with self._lock:
            self.conn.execute(
                "INSERT INTO system_events (timestamp, event_type, message) VALUES (?, ?, ?)",
                (datetime.now().isoformat(), event_type, message)
            )
            self.conn.commit()

    def close(self):
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None
