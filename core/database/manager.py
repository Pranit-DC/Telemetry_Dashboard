# SQLite database manager for telemetry session storage.
# Handles all database read/write operations in one place.

import sqlite3
import os
from datetime import datetime
import config


class DatabaseManager:
    """Manages the SQLite database that stores telemetry sessions and settings.

    Uses a single persistent connection (instead of opening/closing per call)
    with WAL journal mode for safe multi-thread access.
    """

    def __init__(self, db_name="telemetry_archive.db"):
        # Build the full path to the database file
        db_dir = getattr(config, 'SQLITE_DATABASE_DIRECTORY', os.getcwd())
        if not os.path.isabs(db_dir):
            db_dir = os.path.abspath(os.path.join(os.getcwd(), db_dir))

        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, db_name)

        # Open ONE connection and keep it alive for the app's lifetime.
        # check_same_thread=False lets the simulator thread and GUI thread
        # both use this connection safely.
        # WAL mode allows concurrent reads while a write is happening.
        self._conn = sqlite3.connect(
            self.db_path, timeout=10.0, check_same_thread=False
        )
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")

        self._create_tables()
        self._frame_batch = []

    def _create_tables(self):
        """Create all required tables if they don't already exist."""
        cursor = self._conn.cursor()

        # Session metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_sessions (
                session_id TEXT PRIMARY KEY,
                custom_name TEXT,
                created_at TEXT NOT NULL,
                total_records INTEGER DEFAULT 0
            )
        """)

        # Telemetry data table (linked to sessions via foreign key)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pulse_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                elapsed_seconds REAL NOT NULL,
                ch1_voltage REAL NOT NULL,
                ch2_voltage REAL NOT NULL,
                ch3_voltage REAL NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES telemetry_sessions(session_id)
                    ON DELETE CASCADE ON UPDATE CASCADE
            )
        """)

        # Settings table (key-value pairs for UI preferences)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Event log table (alarm events like saturation warnings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)

        # Indexes for faster queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_elapsed "
            "ON pulse_telemetry(elapsed_seconds)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_session "
            "ON pulse_telemetry(session_id)"
        )
        self._conn.commit()

    # -- Session operations --

    def insert_session_metadata(self, session_id, created_at, custom_name=None):
        """Record that a new telemetry session has started."""
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO telemetry_sessions "
                "(session_id, custom_name, created_at, total_records) "
                "VALUES (?, ?, ?, 0)",
                (session_id, custom_name, created_at),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"Session insert failed: {e}")

    def insert_frame(self, session_id, timestamp, elapsed, channel_data):
        """Queue one telemetry frame. Flushes to disk every 10 frames."""
        self._frame_batch.append((
            session_id, timestamp, elapsed,
            channel_data.get("Channel 1", 0.0),
            channel_data.get("Channel 2", 0.0),
            channel_data.get("Channel 3", 0.0)
        ))
        if len(self._frame_batch) >= 10:
            self.flush_frames()

    def flush_frames(self):
        """Write all queued frames to the database in one transaction."""
        if not self._frame_batch:
            return
        batch = list(self._frame_batch)
        self._frame_batch.clear()

        try:
            cursor = self._conn.cursor()
            cursor.executemany(
                "INSERT INTO pulse_telemetry "
                "(session_id, timestamp, elapsed_seconds, "
                "ch1_voltage, ch2_voltage, ch3_voltage) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
            # Count how many rows per session and update totals
            counts = {}
            for row in batch:
                counts[row[0]] = counts.get(row[0], 0) + 1
            for s_id, count in counts.items():
                cursor.execute(
                    "UPDATE telemetry_sessions SET total_records = total_records + ? "
                    "WHERE session_id = ?",
                    (count, s_id),
                )
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"Batch frame insert failed: {e}")

    def get_all_sessions(self, search_term=None):
        """Fetch all sessions, optionally filtered by a search string."""
        try:
            cursor = self._conn.cursor()
            if search_term:
                term = f"%{search_term}%"
                cursor.execute(
                    "SELECT session_id, COALESCE(custom_name, ''), "
                    "created_at, total_records "
                    "FROM telemetry_sessions "
                    "WHERE session_id LIKE ? OR custom_name LIKE ? "
                    "ORDER BY created_at DESC",
                    (term, term),
                )
            else:
                cursor.execute(
                    "SELECT session_id, COALESCE(custom_name, ''), "
                    "created_at, total_records "
                    "FROM telemetry_sessions ORDER BY created_at DESC"
                )
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def get_session_display_list(self):
        """Get session labels formatted for the dropdown menu."""
        sessions = self.get_all_sessions()
        labels = []
        for s_id, custom_name, _, _ in sessions:
            label = f"{custom_name} ({s_id})" if custom_name else s_id
            labels.append(label)
        return labels

    def get_session_data(self, display_label):
        """Load all telemetry data for a session given its dropdown label."""
        session_id = display_label
        if "(" in display_label and display_label.endswith(")"):
            session_id = display_label.split("(")[-1][:-1]

        try:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT elapsed_seconds, ch1_voltage, ch2_voltage, ch3_voltage "
                "FROM pulse_telemetry WHERE session_id = ? "
                "ORDER BY elapsed_seconds ASC",
                (session_id,),
            )
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def rename_session(self, session_id, new_name):
        """Update the custom display name for a session."""
        try:
            self._conn.execute(
                "UPDATE telemetry_sessions SET custom_name = ? WHERE session_id = ?",
                (new_name, session_id),
            )
            self._conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_session(self, session_id):
        """Delete a session and all its telemetry data (cascading delete)."""
        try:
            self._conn.execute(
                "DELETE FROM telemetry_sessions WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()
            return True
        except sqlite3.Error:
            return False

    # -- Settings operations --

    def save_setting(self, key, value):
        """Store a key-value setting (overwrites if key already exists)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        self._conn.commit()

    def get_setting(self, key, default=None):
        """Read a setting value by key, returning default if not found."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        except sqlite3.Error:
            return default

    # -- Event logging --

    def log_alarm_event(self, event_type, message):
        """Record an alarm event with a timestamp."""
        try:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._conn.execute(
                "INSERT INTO system_events (timestamp, event_type, message) "
                "VALUES (?, ?, ?)",
                (stamp, event_type, message),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"Event log failed: {e}")

    def close(self):
        """Flush pending data and close the database connection."""
        self.flush_frames()
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
