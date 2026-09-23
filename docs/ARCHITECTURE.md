# System Architecture —  Telemetry Dashboard

**Version described here:** the current codebase (sidebar shows `v5.0.0`), as of July 2026.

This document explains how the project is put together: what each folder does, how data
moves through the system, and how the pieces talk to each other. It replaces the older
architecture notes in this folder, which described an earlier design (different frame
markers, a 151-sample window, a second trend chart, drill-down clicking) that no longer
matches the code.

---

## 1. What the system actually does

The dashboard talks to an **Arduino GIGA R1** that watches a photodiode. Every ~250 ms the
firmware fires an LED, the photodiode signal decays, and the firmware captures **700 raw
ADC samples** (a full burst, spaced 4 µs apart — 2.8 ms total) at **250,000 samples/second**.

That whole 700-sample burst — not a smaller "decay-only" slice — is sent to the dashboard,
either as text over USB Serial or as binary packets over Bluetooth Low Energy (BLE). The
dashboard (or, for testing, a built-in simulator) turns each burst into a `TraceBurst`
object, works out the peak voltage and the exponential fall time, shows it on a live chart,
and saves it to a SQLite database and a daily CSV file.

Key facts worth remembering because older docs get them wrong:
- **700 samples per burst**, not 151.
- **Serial framing markers are `<<BEG>>` / `<<END>>`**, not `---BEGIN TRACE DATA---`.
- **BLE now uses a binary packet protocol** with per-sample retransmission, not text framing.
- The dashboard currently shows **one** live chart (the decay trace). A second "trend"
  chart and a "click to drill into an old burst" feature were removed at some point —
  they don't exist in the current code.
- The database file is `telemetry.db` (not `telemetry_archive.db`).

---

## 2. Folder-by-folder tour

```
Dashboard/
├── main.py                  # Entry point — creates the window, starts the Tk event loop
├── config.py                # AppConfig — typed access to config_settings.json
├── config_settings.json     # Saved user settings (ports, UI scale, folders, ...)
├── models/
│   └── telemetry.py         # TracePoint, TraceBurst — the shapes data is passed around in
├── core/
│   ├── parser/
│   │   ├── trace_parser.py       # Turns Serial text into TraceBurst objects
│   │   └── ble_binary_parser.py  # Assembles BLE binary packets into a burst
│   ├── sources/
│   │   ├── base.py            # DataSource — abstract interface all sources implement
│   │   ├── simulator.py       # Generates realistic fake bursts, for development/demo
│   │   ├── serial_source.py   # Talks to the Arduino over USB Serial
│   │   └── ble_source.py      # Talks to the Arduino over BLE
│   ├── analysis/
│   │   ├── fall_time.py       # The regression math — exact copy of the firmware's math
│   │   └── signal.py          # Standalone helper functions (peak/fall-time/stats) —
│   │                          #   not currently called by the GUI; kept for future analysis
│   ├── services/
│   │   └── acquisition.py     # AcquisitionService — the traffic controller (see §4)
│   ├── database/
│   │   └── manager.py         # DatabaseManager — SQLite storage
│   └── logging/
│       └── csv_logger.py      # RollingCSVLogger + CSV export helper
├── gui/
│   ├── app.py                  # TelemetryDashboard — the main window
│   ├── components/
│   │   ├── sidebar.py          # Left-hand control panel
│   │   ├── chart.py            # BaseChart — reusable Matplotlib-in-Tkinter widget
│   │   └── notification.py     # Simple popup dialog helper
│   ├── dashboard/
│   │   ├── page.py             # Main page layout (metric cards, chart, console)
│   │   └── graph_renderer.py   # Pushes new bursts into the chart and metric cards
│   ├── dialogs/
│   │   ├── settings.py         # Settings window
│   │   ├── manager.py          # Session Manager window
│   │   └── launcher.py         # Small helpers that open the dialogs above
│   └── analytics/
│       ├── window.py           # Analytics window (tab container)
│       ├── overview.py         # Tab: peak voltage per burst
│       ├── signal.py           # Tab: overlay of recent traces
│       ├── statistics.py       # Tab: fall-time histogram
│       └── reports.py          # Tab: summary table + PDF export
├── firmware/
│   └── arduino_firmware_updated.ino   # The Arduino GIGA R1 sketch
├── logs/                    # Daily CSV metric logs (auto-created)
└── tests/                   # pytest suite (see the "Testing" section of
                              # OFFLINE_DEVELOPMENT_GUIDE.md)
```

This is a fairly clean layered design:

- **`models/`** — plain data. No logic, no imports of anything else in the project.
- **`core/`** — all the non-UI logic: talking to hardware, parsing, math, storage.
- **`gui/`** — everything the user sees. GUI code never talks to the Arduino directly;
  it always goes through `AcquisitionService`.

---

## 3. The main pieces and what they're responsible for

- **`DataSource` (`core/sources/base.py`)** — an abstract base class. It defines the four
  methods every source must implement (`connect`, `start`, `stop`, `disconnect`,
  `send_command`) and a small state machine (`disconnected → connecting → connected →
  acquiring`, or `error`). `SimulatorSource`, `SerialSource`, and `BLESource` all implement
  it, so the rest of the app can use any of them interchangeably.

- **`TraceParser` (`core/parser/trace_parser.py`)** — used only by `SerialSource`. Buffers
  incoming text, watches for `<<BEG>>` / `<<END>>` markers, parses the CSV sample lines in
  between, and emits a complete `TraceBurst` once a frame closes. Because the firmware
  doesn't actually send a `---METRICS---` block over Serial, this parser computes
  peak voltage and fall time itself, using the same regression as the firmware.

- **`BLEBurstAssembler` (`core/parser/ble_binary_parser.py`)** — used only by `BLESource`.
  BLE drops packets sometimes, so instead of trusting a stream of text, each sample arrives
  as its own small binary packet carrying its index. The assembler tracks which indices it
  has, and once it sees the "END" packet it can tell exactly which samples (if any) are
  still missing.

- **`FallTimeCalculator` (`core/analysis/fall_time.py`)** — the regression math, ported
  line-for-line from the Arduino firmware so Python and hardware always agree. Used by
  `BLESource` and `SimulatorSource` (and mirrored inline inside `TraceParser` for Serial).

- **`AcquisitionService` (`core/services/acquisition.py`)** — sits between the data
  sources and the GUI. Owns the currently active `DataSource`, creates/ends sessions in
  the database, and drains a thread-safe queue of finished bursts, writing each one to
  SQLite and the CSV log and handing it to the GUI via a callback.

- **`DatabaseManager` (`core/database/manager.py`)** — one persistent SQLite connection
  (WAL mode) for the life of the app. Stores sessions and bursts (see
  `03_DATABASE_AND_STORAGE.md`).

- **`RollingCSVLogger` (`core/logging/csv_logger.py`)** — writes one summary row per burst
  to a daily CSV file, rotating at midnight and deleting files older than 7 days.

- **`TelemetryDashboard` (`gui/app.py`)** — the main window. Creates the config, the
  database, the CSV logger, and the `AcquisitionService`; builds the sidebar and dashboard
  page; and polls the acquisition queue every 100 ms via `self.after(...)`.

---

## 4. Data flow, end to end

```
 Arduino GIGA R1  (or SimulatorSource, for testing without hardware)
        │  700-sample burst, over USB Serial (text) or BLE (binary packets)
        ▼
 SerialSource / BLESource        (background thread — never touches the GUI directly)
        │  parses/reassembles the burst → builds a TraceBurst
        ▼
 burst_queue  (a plain thread-safe queue.Queue)
        │
        ▼  every 100 ms, on the main GUI thread
 AcquisitionService.poll_queue()
        │  for each burst:
        ├──► DatabaseManager.insert_burst()   (SQLite)
        ├──► RollingCSVLogger.log_burst()     (daily CSV)
        └──► GUI callback → TelemetryDashboard
                    │
                    ▼
             GraphRenderer.refresh()  →  chart + metric cards updated
```

The queue is the important bit: it's what lets a background thread (reading Serial/BLE)
hand data to the GUI thread safely. Nothing calls a Tkinter/Matplotlib method from a
background thread — everything that touches the screen happens on the main thread, driven
by the 100 ms timer in `app.py`.

---

## 5. Troubleshooting notes

- **`ModuleNotFoundError` for `serial` or `bleak` on startup** — these are optional
  imports (see `core/sources/serial_source.py` / `ble_source.py`). Missing them doesn't
  crash the app; the affected source just goes to `'error'` state when you try to connect
  it. Install the offline wheel and switch sources again.
- **`sqlite3.OperationalError: database is locked`** — shouldn't happen in this codebase;
  `DatabaseManager` keeps one persistent, thread-safe connection in WAL mode for the whole
  app's life rather than opening/closing per write. If you do see this, check that no
  external tool (e.g. DB Browser for SQLite) has the file open with an exclusive lock.
- **UI too big/small on a given monitor** — adjust `ui_scale` in the Settings window
  (UI & Graphing tab) or directly in `config_settings.json`.