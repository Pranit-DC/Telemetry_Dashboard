# 4. Concurrency & the Acquisition Service

Covers `core/services/acquisition.py` — the piece that sits between the background data
sources and the single-threaded GUI.

---

## 4.1 The problem: Tkinter is single-threaded

Serial reads, BLE notifications, and the simulator all run on background threads (see
`02_DATA_SOURCES.md`). But Tkinter widgets — and Matplotlib canvases embedded in them —
can only safely be touched from the main thread. Calling a Tkinter method from a
background thread is a reliable way to crash or corrupt the app.

The fix used throughout this codebase is a **producer/consumer queue**:

```
[ background thread ]  --burst_queue.put(burst)-->  [ queue.Queue ]  --get_nowait()-->  [ main thread, every 100ms ]
```

`queue.Queue` is already thread-safe internally, so no extra locking is needed around it.
The background thread only ever *puts*; the main thread (via a Tkinter `.after()` timer
in `app.py`) only ever *polls and gets*.

## 4.2 What `AcquisitionService` actually does

It's the single object that owns:

- The currently active `DataSource` (created by `set_source(...)`).
- The current session id, if a recording is in progress.
- The shared `burst_queue`.
- Callbacks the GUI registers to be notified of new bursts / state changes.

```python
service.set_source('ble')          # creates a BLESource, wires its state callback
service.connect()                  # tells the active source to connect

service.start_session('Run 1')     # creates a DB session, starts the source streaming
...                                 # bursts flow into burst_queue in the background
service.poll_queue()               # called every 100ms from the GUI thread — drains
                                    # the queue, writes each burst to DB + CSV, and
                                    # fires the GUI's on_burst callback

service.pause_session()            # stops the stream but leaves the DB session open
service.resume_session()           # restarts the stream into the SAME session_id
service.stop_session()             # stops the stream AND finalizes (closes) the session
```

### Start / Pause / Resume / Stop

The sidebar's single "Start" button doubles as Start, Pause, and Resume depending on the
current run state (`stopped` / `running` / `paused`) — see `05_GUI_AND_VISUALIZATION.md`.
Pausing stops the underlying source but keeps the same session id open in the database;
resuming restarts the source without creating a new session. Only the separate "Stop"
button actually finalizes the session (`db.end_session(..., status='completed')`).

### `poll_queue()` never blocks

```python
def poll_queue(self):
    bursts = []
    while not self._burst_queue.empty():
        try:
            burst = self._burst_queue.get_nowait()
            bursts.append(burst)
            self._process_burst(burst)
        except Exception:
            break
    return bursts
```

It always uses `get_nowait()` inside a loop bounded by `empty()`, so if the queue has
nothing pending, it returns immediately instead of freezing the UI waiting for data.

### Routing a burst (`_process_burst`)

For every burst pulled off the queue:
1. `self._burst_count` is incremented.
2. If a session is active, the burst is written to SQLite (`DatabaseManager.insert_burst`)
   and to the daily CSV (`RollingCSVLogger.log_burst`).
3. The registered `on_burst` callback is invoked so the GUI can update its chart and
   metric cards.

If no session is active (e.g. the source is connected but the user hasn't pressed Start),
bursts are **not** persisted — they're effectively discarded after passing through
(nothing subscribes without a session in the current GUI flow).

## 4.3 Switching sources cleans up after itself

`set_source()` disconnects and stops whatever source was previously active before
creating the new one, so exactly one `DataSource` is ever live. `cleanup()` (called on
app shutdown) stops and disconnects the active source and closes the CSV logger and
database connection, so no threads or file handles are left dangling when the window
closes.