# 5. GUI & Visualization

Covers `gui/` — built with `customtkinter` (a modern-looking skin over Tkinter) and
`matplotlib` for charts.

> Older docs in this folder described a two-chart layout with a "fall time trend" chart
> and click-to-inspect drill-down on historical bursts. **That layout was simplified** —
> the current dashboard has a single live chart, and there's no drill-down click handler
> anywhere in the code. This document describes what's actually there today.

---

## 5.1 Main window layout (`gui/app.py`, `gui/dashboard/page.py`)

The window is a simple 1×2 grid: a fixed-width **sidebar** on the left, and the
**dashboard page** filling the rest.

The dashboard page itself is three stacked rows:

1. **Top row — 5 metric cards**: Peak Voltage, Fall Time, Avg Fall Time, Std Dev (σ),
   Min/Max Fall. Each is just a small dark rounded frame with a title and a value label.
2. **Middle row — one chart**: "Decay Trace (Latest Capture)" — voltage (V) vs. time
   (µs), showing the most recently received burst, full width. It's a `BaseChart`
   (see below) with the standard Matplotlib navigation toolbar (pan/zoom/save)
   underneath it.
3. **Bottom row — console + diagnostics**: a scrolling log terminal on the left, and a
   small "SYSTEM DIAGNOSTICS" panel on the right showing burst count and the current
   source's connection state.

## 5.2 `BaseChart` (`gui/components/chart.py`)

A small reusable wrapper that embeds a Matplotlib `Figure` inside a `CTkFrame` via
`FigureCanvasTkAgg`, styled to match the app's dark theme, with the standard Matplotlib
`NavigationToolbar2Tk` shown underneath (also restyled to match). Every chart in the app
— the dashboard trace, and all four Analytics tabs — is built on this same wrapper.

## 5.3 Updating the chart live (`gui/dashboard/graph_renderer.py`)

`GraphRenderer.refresh(latest_burst, burst_history)` is called from `app.py` every time
new bursts arrive (still on the 100 ms polling timer). It:

- Redraws the trace line with the latest burst's 700 points, and resets the chart's
  view to exactly that burst's own time range (so each new capture is shown at full
  width, not zoomed to whatever the previous burst's range happened to be).
- Recomputes the metric cards: current peak/fall/avg-fall values, plus a running
  standard deviation and min/max of fall time across *all* bursts seen so far this
  session (only bursts with a successful, `> 0` fall time count toward these stats).
- Updates the "Burst Count" diagnostic label.

The chart's x/y axis limits are pinned once at startup to the full 700-sample range
(0 to 2796 µs) and 0–3.3 V (the ADC's reference range), so the toolbar's "Home" button
always zooms back out to the complete trace rather than an empty default view.

## 5.4 Sidebar (`gui/components/sidebar.py`)

Buttons, top to bottom:

- **Start Acquisition** — triples as Start / Pause / Resume depending on run state
  (see `04_CONCURRENCY_AND_SERVICES.md`). Label and color change accordingly.
- **Stop** — always fully ends the current session (only enabled once one exists).
- **Clear Buffer** — clears the in-memory burst history and chart without touching
  anything already saved to the database.
- **Manage Sessions** — opens the Session Manager dialog.
- **Analytics** — opens the Analytics window.
- **Export CSV** — writes the full raw trace of every burst currently in memory to a
  CSV file (see `03_DATABASE_AND_STORAGE.md` §3.4).
- **Settings** — opens the Settings dialog.

A status label near the top shows the active source's connection state
(`DISCONNECTED` / `CONNECTING` / `CONNECTED` / `ACQUIRING` / `ERROR`), color-coded.

## 5.5 Settings dialog (`gui/dialogs/settings.py`)

Three tabs:

- **Connection** — BLE device name, COM port, baud rate, BLE timeout.
- **UI & Graphing** — graph display window (seconds), chart line thickness, UI scale
  slider. *(Note: at the moment, these two graphing values are saved to config but are
  not actually read anywhere in the current chart-rendering code — the trace chart's line
  width is hardcoded, and the chart always shows the full burst rather than a rolling
  time window. UI scale, by contrast, is applied on next launch.)*
- **File Paths** — database directory, logs directory.

Saving calls back into `TelemetryDashboard._apply_settings()`, which updates and
persists `AppConfig` (`config_settings.json`). Some settings (COM port, BLE device name)
only take effect the next time that source is connected.

## 5.6 Session Manager dialog (`gui/dialogs/manager.py`)

A `ttk.Treeview` table (styled to match the dark theme) listing every session from the
database: ID, name, created time, burst count, status, source type. A search box filters
by name/ID. Buttons: Refresh, Rename (prompts for a new name), Delete, and Load Data
(also triggered by double-clicking a row) — which replaces the dashboard's current burst
history with everything from that session.

## 5.7 Analytics window (`gui/analytics/`)

Opened as a separate maximized window with four tabs, all operating on whatever burst
history is currently loaded (live session or a loaded historical one):

- **Overview** — peak voltage vs. burst id, as a line chart.
- **Signal Analysis** — the last 10 bursts' full traces, overlaid on one chart (with a
  legend, if 10 or fewer are shown).
- **Statistics** — a histogram of fall times across all bursts (only bursts with a
  valid, non-zero fall time are included).
- **Reports** — a scrollable table of every burst's metrics, plus an
  **Export Report (PDF)** button. The PDF has 4 pages: the summary table (capped at 35
  rows per page for readability — a note is added if more bursts exist), then one page
  each reproducing the Overview, Statistics, and Signal Analysis charts.

None of the analytics tabs currently use the standalone helper functions in
`core/analysis/signal.py` (`compute_peak_voltage`, `compute_session_statistics`, etc.) —
they work directly off the `TraceBurst` fields that were already computed when the burst
was captured. That module is available for future analysis features but isn't wired into
the GUI today.

## 5.8 Startup and shutdown

`main.py` sets CustomTkinter's dark appearance and blue color theme, creates the
`TelemetryDashboard`, and hooks the window-close ("X" button) event to a safe shutdown:
`app.cleanup()` (stops/disconnects the active source, closes the CSV logger and the DB
connection) runs before `app.destroy()` tears down the Tkinter window.