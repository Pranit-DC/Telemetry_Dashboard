# 3. Storage — SQLite Database & CSV Logging

Covers `core/database/manager.py` and `core/logging/csv_logger.py`.

---

## 3.1 Why SQLite, and why one persistent connection

Every burst that comes in during a recording session needs to be saved. SQLite was
chosen because it's serverless (one file, `telemetry.db`, no separate database process
to install or configure — important in an offline environment) and still gives proper
transactions, indexes, and SQL.

A common mistake with SQLite from multiple threads is opening a fresh connection for
every write. Under a steady stream of bursts, that causes lock contention and
`sqlite3.OperationalError: database is locked` crashes. `DatabaseManager` avoids this by:

- Opening **one** connection for the whole life of the app (`check_same_thread=False`,
  since acquisition and the GUI may both touch it).
- Enabling `PRAGMA journal_mode=WAL`, which lets reads happen concurrently with writes.
- Wrapping every query in a `threading.Lock()`, so two threads never issue SQL at the
  same instant.

## 3.2 Schema

Three tables, created automatically on first run if they don't exist:

**`sessions`** — one row per recording run.

| Column | Type | Notes |
|---|---|---|
| `session_id` | TEXT (PK) | e.g. `RUN_20260716_100532` |
| `name` | TEXT | Friendly label; defaults to the session_id if not set |
| `start_time` | TEXT | ISO timestamp |
| `end_time` | TEXT | ISO timestamp, set when the session is stopped |
| `burst_count` | INTEGER | Incremented on every insert |
| `status` | TEXT | `running` → `completed` |
| `source_type` | TEXT | `simulator` / `serial` / `ble` |
| `notes` | TEXT | Reserved, not currently written to by the app |

**`trace_bursts`** — one row per burst.

| Column | Type | Notes |
|---|---|---|
| `burst_id` | INTEGER (PK, autoincrement) | Internal SQLite row id |
| `session_id` | TEXT (FK → sessions) | Cascades on delete |
| `burst_index` | INTEGER | The burst's own id from the parser/source |
| `timestamp` | TEXT | ISO timestamp of when it was received |
| `peak_voltage` | REAL | |
| `fall_time_us` | REAL | |
| `avg_fall_time_us` | REAL | Rolling average at the time |
| `channel` | INTEGER | Currently always `0` — reserved for future multi-channel support |
| `trace_data` | TEXT | The full 700-point trace, as a JSON string |

**`system_events`** — a general-purpose event log table (`timestamp`, `event_type`,
`message`). The `DatabaseManager.log_event()` method exists to write to it, but nothing
in the current codebase calls it yet — it's available for future diagnostics logging.

### Why the full trace is stored as one JSON string, not 700 rows

Inserting 700 individual rows per burst (at ~4 bursts/second) would be extremely slow and
would bloat the database with hundreds of millions of rows over a long session. Instead,
`TraceBurst.trace_to_json()` packs the whole `trace_points` list into one compact JSON
array, stored in the single `trace_data` column — one row write per burst, and it decodes
back into a full list of `TracePoint`s with `TraceBurst.trace_from_json()` when a session
is loaded.

## 3.3 What `DatabaseManager` exposes

```python
create_session(session_id, source_type, name=None)
end_session(session_id, status='completed')
insert_burst(session_id, burst)               # also bumps sessions.burst_count
get_all_sessions(search_term=None)             # for the Session Manager list/search
get_session_display_list()                     # "Name (session_id)" strings
get_session_bursts(session_id)                 # loads a full session back into TraceBursts
get_session_by_id(session_id)                  # single session's metadata as a dict
rename_session(session_id, new_name)
delete_session(session_id)                     # cascades to its trace_bursts
log_event(event_type, message)                 # reserved, unused today
close()
```

## 3.4 Daily rolling CSV logs (`core/logging/csv_logger.py`)

Alongside SQLite, `RollingCSVLogger` writes a lightweight summary row per burst to a
per-day CSV file, so results can be opened directly in Excel/MATLAB/etc. without touching
the database at all.

- Filename pattern: `telemetry_metrics_YYYYMMDD.csv` in the configured logs directory.
- Header: `Timestamp, Burst_ID, Peak_Voltage_V, Fall_Time_us, Avg_Fall_Time_us`.
- Automatically rolls over to a new file when the date changes.
- Automatically deletes CSV files older than **7 days**.

Separately, `export_session_csv(bursts, filepath)` (also in this module) is what powers
the sidebar's "Export CSV" button — it writes the **full raw trace** (every sample of
every burst in the current buffer, not just the summary metrics) to a chosen file.

> **Note:** the sample CSV files that ship in the `logs/` folder of this project are
> named `telemetry_daily_YYYY-MM-DD.csv`, which doesn't match the `telemetry_metrics_*`
> pattern the current code actually writes. Those files are leftovers from an earlier
> version of the logger; a fresh run of the current code will produce
> `telemetry_metrics_YYYYMMDD.csv` files instead.

## 3.5 Configurable paths

Both the database location and the logs directory are configurable (Settings → File
Paths), backed by `AppConfig.sqlite_database_directory` and
`AppConfig.system_logs_directory`. Both default to the current working directory (and
`./logs` respectively) if not set.