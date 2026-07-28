# Execution & Data Workflow

The full lifecycle of the app, from `python main.py` to window close.

---

## Phase 1 — Startup

```
main.py
  └─ TelemetryDashboard()                (gui/app.py)
       ├─ AppConfig()                    loads config_settings.json (or defaults)
       ├─ apply ui_scale                 ctk.set_widget_scaling / set_window_scaling
       ├─ DatabaseManager(config)        opens telemetry.db, WAL mode, creates tables
       ├─ RollingCSVLogger(config)       opens/creates today's CSV, prunes files >7 days old
       ├─ AcquisitionService(db, csv, config)
       ├─ _build_ui()                    Sidebar + DashboardPage widgets
       ├─ GraphRenderer(dashboard_page)
       ├─ service.set_source('simulator')   default source on launch
       ├─ service.connect()
       └─ _start_polling()               kicks off the 100ms queue-poll timer
  └─ app.mainloop()                      Tkinter event loop takes over
```

The app always starts on the **Simulator** source, so it's usable immediately with no
hardware attached. Switching to Serial or BLE happens later, through source selection
logic in `AcquisitionService` (currently driven by whichever source the app was
constructed with / switched to — there's no source-picker widget in the sidebar itself
today, so switching sources is done via `AcquisitionService.set_source()` in code, or by
extending the UI to expose it).

## Phase 2 — Live acquisition

Triggered by pressing **Start Acquisition**:

```
Sidebar "Start Acquisition"
  └─ app._on_start()
       └─ (no session running) → service.start_session()
            ├─ db.create_session(RUN_<timestamp>, source_type, name)
            └─ source.start()                     (background thread begins)
                  │
                  ▼ (background thread, continuously)
            Arduino/Simulator produces a burst
              → SerialSource/BLESource/SimulatorSource
              → parses/assembles it into a TraceBurst
              → burst_queue.put(burst)
                  │
                  ▼ (main thread, every 100ms via app._start_polling)
            service.poll_queue()
              ├─ db.insert_burst(session_id, burst)
              ├─ csv_logger.log_burst(burst)
              └─ on_burst callback → app appends to burst_history, calls
                                      renderer.refresh(latest_burst, burst_history)
                                        → chart + metric cards updated
```

Pressing the same button again **pauses** (stream stops, session stays open in the DB);
pressing it a third time **resumes** (stream restarts, same session id — no new DB row).
`burst_history` in memory is capped at 1000 bursts (oldest are trimmed) to avoid unbounded
memory growth during a long-running session; nothing already written to SQLite/CSV is
affected by that trim.

## Phase 3 — Stopping, and reviewing past sessions

Pressing **Stop**:
```
app._on_stop()
  └─ service.stop_session()
       ├─ source.stop()
       └─ db.end_session(session_id, status='completed')
```

Loading an old session (Session Manager → double-click, or Load Data):
```
app._on_load_session(choice)
  └─ db.get_session_bursts(session_id)      pulls every burst + decodes its JSON trace
       → replaces app.burst_history in memory
       → renderer.refresh(...) redraws the chart against the loaded session
```
Loading a session only affects what's in memory/on screen — it doesn't start acquiring
new data, and it doesn't touch the database.

## Phase 4 — Shutdown

Clicking the window's close ("X") button:
```
main.py: on_close()
  ├─ app.cleanup()
  │    ├─ service.cleanup()      stop + disconnect the active source
  │    ├─ csv_logger.close()     flush and close the open CSV file
  │    └─ db.close()             close the SQLite connection cleanly
  └─ app.destroy()               tear down all Tkinter/Matplotlib objects
```
This ordering matters: the source is stopped *before* the database/CSV are closed, so any
in-flight burst has somewhere to land before the files it needs are shut.