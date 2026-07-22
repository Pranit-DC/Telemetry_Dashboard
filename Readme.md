# BARC Telemetry Dashboard - System Architecture & Developer Guide

Welcome to the project documentation! This guide explains the layout of the project, how data flows through the application, and how each component works in simple, clear terms (perfect for a final-year engineering project report or viva preparation).

---

## 1. Project Directory Structure

```
barc_dashboard/
├── main.py                 # Main application entry point
├── config.py               # Persisted configuration properties & defaults
│
├── core/                   # Back-end logic (No UI code here)
│   ├── database/           # SQLite Database persistence engines
│   │   ├── __init__.py     # Exposes DatabaseManager
│   │   └── manager.py      # SQLite operations (inserts, queries, logs)
│   ├── telemetry/          # Input acquisition and local backup loggers
│   │   ├── __init__.py     # Exposes simulator, CSV logger, and export utilities
│   │   ├── simulator.py    # Background thread simulating signal inputs
│   │   ├── adc.py          # ADC counts-to-voltage converters & wave equations
│   │   └── csv_logger.py   # Daily rolling backup CSV manager & exporters
│   └── analysis/           # Pure math and signal processing routines
│       ├── __init__.py     # Exposes signal analysis equations
│       └── signal.py       # Metrics: Peak-to-Peak, Rise Time, Frequency, Jitter
│
└── gui/                    # Front-end interface (Uses CustomTkinter & Matplotlib)
    ├── app.py              # Main Window controller (Event coordinator)
    ├── components/         # Reusable widgets
    │   ├── __init__.py     # Exposes sidebar, notifications, base chart
    │   ├── sidebar.py      # Left control panel sidebar
    │   ├── notification.py # Pop-up notification dialogue widget
    │   └── chart.py        # Reusable dark-mode Matplotlib canvas component
    │
    ├── dashboard/          # Real-time dashboard view
    │   ├── __init__.py     # Exposes Dashboard page and renderer
    │   ├── page.py         # Main view (Live chart, metric cards, logs)
    │   └── graph_renderer.py # Updates graph coordinates and fills card text
    │
    ├── dialogs/            # Modal dialogue popups (Transient child windows)
    │   ├── __init__.py     # Exposes sub-window launchers
    │   ├── manager.py      # Session list manager (styled Treeview table)
    │   ├── settings.py     # Settings window (tabbed config dashboard)
    │   └── launcher.py     # De-clutters app.py by managing sub-window instances
    │
    └── analytics/          # Dedicated multi-tab Analytics suite
        ├── __init__.py     # Exposes Analytics window shell
        ├── window.py       # Main tab-view layout container
        ├── overview.py     # Overview Tab skeleton frame
        ├── statistics.py   # Statistics Tab skeleton frame
        ├── signal.py       # Signal Analysis Tab skeleton frame
        └── reports.py      # Reports Tab skeleton frame
```

---

## 2. File-by-File Explanation

### Entry Points & Configuration
* **[main.py](file:///home/pranitchiman/Projects/barc_dashboard/main.py)**: The application bootstrapper. It loads the main Tkinter thread, instantiates the `TelemetryDashboard` window, and starts the event loop (`mainloop()`).
* **[config.py](file:///home/pranitchiman/Projects/barc_dashboard/config.py)**: Stores constant values (like colors, channel names, and limits). It also handles reading and saving settings locally to a JSON file (`config_settings.json`).

### Back-End Components (`core/`)
* **`database/manager.py`**: Interacts with SQLite (`telemetry_archive.db`). Set up with 4 indexed tables:
  1. `telemetry_sessions` (metadata about recording runs)
  2. `pulse_telemetry` (discrete voltage points mapped to session IDs)
  3. `system_settings` (for lightweight key-value pairs)
  4. `system_events` (logging sat/clipping warning alerts)
  
  *Efficiency Note:* Uses an internal memory queue that flushes data in batches of 10 inside a single database transaction. This protects the hard drive from writing to disk 100 times per second and lagging the app.
* **`telemetry/adc.py`**: Contains math to convert raw 16-bit integer ADC counts (0 to 65535) into actual potential levels (0 to 3.3V) according to the Arduino Giga R1 microcontroller reference characteristics. Also generates mathematical sine/cosine waves for simulation.
* **`telemetry/simulator.py`**: Runs a background worker thread that mimics real hardware inputs. At each tick, it generates fake data frames, checks if the signal saturates (above 3.2V), triggers alerts, writes to the database batch queue, and schedules a screen refresh.
* **`telemetry/csv_logger.py`**: Automatically writes daily telemetry backups locally (`logs/telemetry_daily_YYYY-MM-DD.csv`). Rotates files automatically at midnight and discards backup logs older than 30 days. Also provides utility routines to write historical playback runs out to custom CSVs.
* **`analysis/signal.py`**: Houses pure mathematical formulas (zero UI dependencies):
  * `peak_to_peak`: Computes $V_{max} - V_{min}$.
  * `estimate_frequency`: Locates zero-crossings (midpoint crossings) to calculate the signal's period and frequency.
  * `rise_time`: Measures time elapsed between the 10% and 90% threshold limits of the wave.
  * `max_jitter`: Finds timing lag discrepancies between the peaks of different channels (in milliseconds).

### Front-End Components (`gui/`)
* **`app.py`**: The "brain" or controller of the UI. Connects the user controls on the left side to the simulation loops and plot renders on the right side. It also exposes standard log message callbacks that other classes call to print to the diagnostic terminal.
* **`components/sidebar.py`**: Left dashboard panel. Contains the start/stop simulation buttons, historical sessions selector, visible channels checkbox group, live target channel selector, and buttons to open sub-panels.
* **`components/notification.py`**: A custom modal alert popup used to display confirmation errors and warning alerts on top of the dashboard.
* **`components/chart.py`**: A customized Tkinter wrapper for Matplotlib plots. Automatically styles the plot background, labels, axes, and line weights. Re-packs and restyles the standard Matplotlib navigation toolbar buttons to fit the dark theme.
* **`dashboard/page.py`**: The right side dashboard layout containing metric cards (top), the chart area (middle), and the log terminal text box with battery/frame status logs (bottom).
* **`dashboard/graph_renderer.py`**: Updates coordinates for active channels, slides the X-axis limit to follow the live scrolling buffer, auto-scales Y-axis bounds, and updates numerical display cards.
* **`dialogs/manager.py`**: Houses the Session Management dashboard. Employs a native Virtual List Table (`ttk.Treeview`) to render thousands of session records instantly without lagging.
* **`dialogs/settings.py`**: A settings screen containing three tabs: BLE, UI, and Storage. Validates all inputs before committing changes to the JSON settings file.
* **`dialogs/launcher.py`**: A helper module that instantiates sub-windows, manages focus lifespans, and prevents `app.py` from growing too large.
* **`analytics/window.py`**: A tabbed popup window shell that serves as the home for your custom analysis interfaces. Exposes blank placeholder tabs: Overview, Statistics, Signal Analysis, and Reports.

---

## 3. Project Workflow & Data Pipelines

The system is split into two asynchronous loops to keep the user interface highly responsive:
1. **The Telemetry Thread (Background)**: Polls data from the sensors at a constant frequency, pushes to database/CSV logs, and tells the GUI thread to update.
2. **The Main Tkinter Event Loop (GUI Thread)**: Manages mouse clicks, button highlights, dialog maps, and updates the Matplotlib canvas when notified by the background thread.

### The Live Telemetry Data Flow
```
 [TelemetrySimulator Thread]
            │
            ▼
 1. Generate ADC counts (adc.py)
            │
            ▼
 2. Convert raw counts to Voltages (adc.py)
            │
            ├──► [If voltage > 3.2V] ──► Log event to database & print GUI alarm
            │
            ▼
 3. Push to lists (time_data, channels_data, all_history) in app.py
            │
            ├──► Save to SQLite manager (core/database/manager.py)
            │      └─► Queued in batch queue ──► [If queue size >= 10] ──► Commit Transaction
            │
            ├──► Save to rolling CSV backup logger (core/telemetry/csv_logger.py)
            │      └─► [If count >= 10] ──► Append to daily file
            │
            ▼
 4. Schedule GUI refresh: root.after(0, refresh)
            │
            ▼
 [GraphRenderer.refresh() inside GUI Thread]
            │
            ├──► Calculate Signal Analytics: peak-to-peak, frequency, jitter, rise-time
            ├──► Update screen cards (value labels)
            ├──► Set coordinates on plot lines for visible channels
            └──► Redraw Matplotlib canvas: canvas.draw_idle()
```

---

## 4. How to Extend the Dashboard

### Adding Real BLE Hardware Reading
Currently, the telemetry simulator runs a loop in `core/telemetry/simulator.py` generating mock wave values. To read from actual hardware, implement a matching BLE reader:
1. Create a file `core/telemetry/ble_reader.py`.
2. Implement methods like `start()`, `pause()`, and `stop()` matching the interface of `TelemetrySimulator`.
3. In `gui/app.py`, check which connection option is active, then initialize and run `BLEReader` instead of `TelemetrySimulator`.

### Adding a Custom Math Metric
To calculate a new metric (for example, Root Mean Square Voltage - RMS):
1. In `core/analysis/signal.py`, define your formula:
   ```python
   def calculate_rms(voltages):
       if not voltages:
           return 0.0
       squares = [v ** 2 for v in voltages]
       return math.sqrt(sum(squares) / len(voltages))
   ```
2. In `gui/dashboard/graph_renderer.py`, call your method inside `_update_cards` and write the result to a UI label.

### Writing Code for the Analytics Tabs
To add custom widgets (like histograms, scatter plots, or PDF exporters) to the Analytics panel, modify the skeleton frames inside `gui/analytics/`:
* Open `gui/analytics/statistics.py` to write math tables, box-plots, or distribution histograms.
* Open `gui/analytics/reports.py` to add buttons for PDF/HTML report generators.
* Since they subclass `ctk.CTkFrame`, you can add cards, labels, text inputs, and buttons inside their `__init__` builders exactly like in `DashboardPage`. You can also drop a `BaseChart` component into them to display analytics charts!
