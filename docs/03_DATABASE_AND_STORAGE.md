# Module 3: Thread-Safe SQLite WAL Storage & CSV Logging

Welcome to Module 3! In this module, you will build the data persistence layer. You will learn how to write a high-throughput, thread-safe SQLite database manager and a rolling CSV file logger.

---

## 🎯 Learning Objectives
By the end of this module, you will understand:
- Why opening/closing database connections repeatedly causes `OperationalError: database is locked`.
- How **Write-Ahead Logging (WAL)** mode in SQLite drastically improves concurrency.
- How to serialize complex nested arrays (`trace_points`) into compact JSON strings.
- How to implement automated daily CSV log rotation.

---

## 1. Problem Statement & The SQLite Lock Pitfall

### ⚠️ What caused the `database is locked` bug in older code?
In older versions, every time a new telemetry point arrived (10 times a second), the database manager opened a new `sqlite3.connect()`, wrote a row, and closed it.

On Linux, opening and closing SQLite connections rapidly causes file lock contention between threads. When 10 bursts per second hit the file system, SQLite throws `sqlite3.OperationalError: database is locked` and crashes your application!

### The Solution:
1. **Persistent Connection:** Maintain a **single open connection** `self.conn` for the entire life of the app.
2. **WAL Mode:** Enable `PRAGMA journal_mode=WAL` during setup. WAL allows concurrent reads while writes take place.
3. **Thread Locking:** Wrap all SQL queries inside `with self._lock:` using Python's `threading.Lock()`.

---

## 2. Step 1: Designing the Database Schema (`core/database/manager.py`)

We need two primary tables:
1. `sessions`: Stores metadata for each experimental run (`session_id`, `name`, `start_time`, `end_time`, `burst_count`, `source_type`).
2. `trace_bursts`: Stores each burst event (`burst_id`, `session_id`, `timestamp`, `peak_voltage`, `fall_time_us`, `avg_fall_time_us`, `trace_data`).

### 💡 Mentor's Tip on Storing High-Density Array Data
Don't create 151 separate rows in the database for 151 sample points! That would bloat your database with millions of rows per hour.

Instead, serialize the 151 points into a single compact JSON string `[[idx, time, voltage], ...]` and store it in the `trace_data TEXT` column of `trace_bursts`.

---

## 3. Step 2: Implementing `DatabaseManager`

### Tasks for you:
1. Create `core/database/manager.py`.
2. In `__init__()`, initialize `self._lock = threading.Lock()`.
3. Open `self.conn = sqlite3.connect(..., check_same_thread=False)`.
4. Execute `PRAGMA journal_mode=WAL;` and `PRAGMA foreign_keys=ON;`.
5. Write thread-safe methods:
   - `create_session(session_id, source_type, name)`
   - `end_session(session_id)`
   - `insert_burst(session_id, burst)`
   - `get_session_bursts(session_id)`
   - `delete_session(session_id)`
   - `close()`

---

## 4. Step 3: Rolling CSV Logger (`core/logging/csv_logger.py`)

### Why do we need a CSV Logger alongside SQLite?
In research labs like BARC, researchers often want raw CSV files they can open in Excel or MATLAB without querying SQLite.

Our `RollingCSVLogger`:
- Creates daily log files: `telemetry_metrics_20260723.csv`.
- Automatically rolls over to a new file when the date changes (`_check_rollover()`).
- Automatically deletes log files older than 7 days (`_cleanup_old_logs()`).
- Includes an `export_session_csv()` function to export full 151-point raw traces to CSV on demand.

---

## 5. Self-Test & Verification Check

Create `test_module3.py`:

```python
from datetime import datetime
from models.telemetry import TracePoint, TraceBurst
from core.database.manager import DatabaseManager

db = DatabaseManager()
session_id = "TEST_RUN_001"

# 1. Create session
db.create_session(session_id, source_type="simulator", name="Test Session")

# 2. Insert dummy burst
dummy_points = [TracePoint(i, i * 4.0, 2.5 - (i * 0.01)) for i in range(151)]
dummy_burst = TraceBurst(1, datetime.now(), dummy_points, 2.5, 120.0, 120.0)

db.insert_burst(session_id, dummy_burst)

# 3. Retrieve and verify
retrieved = db.get_session_bursts(session_id)
assert len(retrieved) == 1, "Failed: Should retrieve 1 burst"
assert len(retrieved[0].trace_points) == 151, "Failed: Should deserialize all 151 points"

# 4. Clean up
db.delete_session(session_id)
db.close()

print("✅ Module 3 Self-Test PASSED!")
```

---

## 📖 Reference Implementation

<details>
<summary>Click to view reference implementation for core/database/manager.py</summary>

```python
import os
import sqlite3
import threading
from typing import List, Tuple, Dict
from models.telemetry import TraceBurst

class DatabaseManager:
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

    def delete_session(self, session_id: str):
        with self._lock:
            self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            self.conn.commit()

    def close(self):
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None
```
</details>
