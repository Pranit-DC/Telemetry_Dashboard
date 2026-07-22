# BARC Dashboard — Scratch Development Design Decisions

This document acts as a development log explaining **why** the core technologies, libraries, and design patterns were chosen from day one of starting this project from scratch, and why alternative design options were skipped.

---

## 1. Choosing the Tech Stack (Core Technologies)

### Why CustomTkinter instead of PySide/PyQt or standard Tkinter?
* **The Decision**: CustomTkinter was chosen for the Graphical User Interface.
* **Why**: 
  * Standard Python Tkinter looks extremely outdated (like a 1990s desktop application) and doesn't support dark mode natively.
  * PyQt/PySide is highly powerful but has a steep learning curve, requires huge library installs, and has restrictive licensing rules.
  * CustomTkinter provides modern, styled widgets (rounded corners, clean fonts, dark/light modes) right out of the box with the simplicity of standard Tkinter syntax, making it perfect for a rapid final-year engineering build.

### Why Matplotlib instead of other plotting libraries?
* **The Decision**: Matplotlib was selected for live signal rendering.
* **Why**:
  * Matplotlib is the industry standard for scientific plotting in Python.
  * It integrates natively with Tkinter using a backend canvas widget (`FigureCanvasTkAgg`).
  * It provides high-performance rendering of multi-channel line plots and gives us a built-in Navigation Toolbar (for panning, zooming, and saving figures) with minimal configuration.
  * *Alternative Considered*: `PyQtGraph` (for high-speed 60+ Hz plotting). 
  * *Why skipped*: Integrating PyQtGraph would force us to use PyQt for the whole GUI, which is too complex for this project's timeline. Matplotlib is more than fast enough for 1-10 Hz telemetry.

### Why SQLite instead of MySQL or PostgreSQL?
* **The Decision**: SQLite was chosen as the database management system.
* **Why**:
  * Unlike MySQL or PostgreSQL, SQLite is a serverless, zero-configuration database. The entire database is stored in a single file (`telemetry_archive.db`) inside the project folder.
  * The user does not need to install or configure database servers to run the dashboard—it runs instantly.
  * Despite its simplicity, it supports standard SQL, transactions, foreign keys, and indexes, which is more than enough for high-speed local data logging.
  * *Alternative Considered*: Standard JSON/CSV files only.
  * *Why skipped*: JSON/CSV files do not support fast querying (e.g., "give me record counts per session" or "rename a session"). SQLite allows us to structure data and perform advanced filtering in milliseconds.

---

## 2. Architecture & Directory Design (Separation of Concerns)

### Why separate the project into `core` and `gui` packages?
* **The Decision**: Organized the codebase into an MVC (Model-View-Controller) inspired package structure.
* **Why**:
  * Mixing database commands or mathematical equations inside GUI files makes code incredibly messy. If we wanted to test our peak-detection algorithm, we would have to launch the whole app.
  * By splitting the code into `core/` (backend database, math logic, telemetry reading) and `gui/` (buttons, layouts, charting windows), the backend code remains completely independent. This means we can swap out the fake telemetry simulator for a real Bluetooth reader without changing a single line of layout code in the dashboard page.

---

## 3. Concurrency Design (Background Threads)

### Why run the Telemetry Reader on a separate background thread?
* **The Decision**: Used Python's `threading` library to run data acquisition off the main thread.
* **Why**:
  * Graphical user interfaces run on a single main thread (the loop that handles clicks, window resizing, and paints the screen).
  * If the telemetry reader runs on this main thread, any waiting period (e.g., waiting for a packet from Bluetooth or writing to disk) would cause the entire application to lock up and freeze.
  * Putting the telemetry collection loop on a background daemon thread ensures the user interface remains smooth, responsive, and interactive at all times.
  * *Alternative Considered*: Python's `asyncio` or `multiprocessing`.
  * *Why skipped*: `multiprocessing` introduces heavy memory overhead because it spawns separate operating system processes (making list sharing very complex). `asyncio` works well for network I/O, but Tkinter is not natively async-compatible. standard threads are simple, lightweight, and perfect for sharing variables under a mutex lock.

---

## 4. Telemetry Logging Design (Dual-Storage Strategy)

### Why use BOTH SQLite and Rolling CSV files?
* **The Decision**: Implemented SQLite for structured playback and daily CSV files for raw backups.
* **Why**:
  * **SQLite** is used for the application's internal features. It allows the session manager to query run metadata quickly (e.g., count records, rename tags, filter by date).
  * **Daily CSV Logging** serves as a failsafe backup. If the application crashes or the database gets corrupted, the raw telemetry data is already safely saved in standard text format. CSV files are also easily imported into Excel or MATLAB for quick plotting by other team members.

---

## 5. Configuration & Persistence Design

### Why use a dual config approach (`config.py` + JSON)?
* **The Decision**: Defined constants in code but saved user settings in a JSON file.
* **Why**:
  * Hardcoding settings like the default database path or BLE identifier inside source code means the user has to edit Python files to make changes.
  * Storing settings in `config_settings.json` allows the application to remember preferences (like graph normalization, channel visibility, and COM ports) across restarts.
  * `config.py` acts as the single source of truth, loading the JSON file on startup and providing safe fallback default values if the file is missing or corrupted.

---

## 6. File-by-File Design Rationale & Alternatives

### `main.py` (App Entry Point)
* **Design**: Standard Python execution wrapper. Keeps the launch script extremely simple.
* **Alternatives Considered**: Initializing the app GUI elements directly inside `main.py`.
* **Why Skipped**: Bad separation of concerns. `main.py` should only be responsible for starting and closing the process; keeping it clean makes packaging the app (e.g., with PyInstaller) trivial.

### `config.py` (App Configurations)
* **Design**: Config module loading an external JSON file with fallback checks.
* **Alternatives Considered**: Reading JSON file path directly in every file that needs settings.
* **Why Skipped**: Reading settings files repeatedly across different files is slow and hard to maintain. A single centralized `config.py` loaded once at start acts as the single source of truth.

### `core/database/manager.py` (SQLite Interface)
* **Design**: Persistent connection model using batch writes.
* **Alternatives Considered**: Opening/closing connections on every SQL query, and writing each sensor packet instantly.
* **Why Skipped**: SQLite write locks on every disk commit. Writing single frames at 10Hz commits to the hard drive 10 times a second, creating a massive disk I/O bottleneck that freezes the Tkinter thread. Batching writes in groups of 10 solves this.

### `core/telemetry/simulator.py` (Telemetry Simulator)
* **Design**: Threaded simulation class generating math-based waves.
* **Alternatives Considered**: Running simulation inside the Tkinter GUI thread using `root.after()`.
* **Why Skipped**: Using `root.after` means the simulation shares execution time with mouse movement and drawing. If the GUI lags, the simulation slows down, resulting in inaccurate timestamps. A background thread runs at a constant timing interval independent of GUI lag.

### `core/telemetry/csv_logger.py` (CSV Logger)
* **Design**: Auto-rotating CSV writer that rolls over at midnight and keeps 30 days of data.
* **Alternatives Considered**: Writing one massive CSV file forever.
* **Why Skipped**: A single CSV file will grow to gigabytes over months of testing, making it impossible to open in Excel. Rotating daily keeps files small, organized, and easy to share.

### `core/telemetry/ble_reader.py` (BLE Hardware Interface)
* **Design**: Standard class wrapper for the asynchronous `Bleak` library.
* **Alternatives Considered**: Writing Bleak logic directly in `app.py`.
* **Why Skipped**: We kept this file decoupled from the UI. This allows the developer to complete the Bluetooth integration without editing the visual layout files.

### `core/analysis/signal.py` (Math Calculations)
* **Design**: Pure Python functions with no UI imports.
* **Alternatives Considered**: Embedding equations directly inside `graph_renderer.py`.
* **Why Skipped**: By keeping mathematical equations (Peak-to-Peak, Rise Time, Jitter, Frequency estimation) pure, you can verify they work using standalone unit test scripts without launching a graphical window.

### `gui/app.py` (Main Controller Window)
* **Design**: Coordinates interaction between the layout, database, and background simulator.
* **Alternatives Considered**: Placing all layout components directly in `app.py` (Monolithic view).
* **Why Skipped**: Putting 500 lines of buttons, labels, and textboxes inside one file makes it unmaintainable. Splitting it into pages and dialog frames keeps files short and understandable.

### `gui/dashboard/page.py` & `graph_renderer.py` (Main View & Chart Refresher)
* **Design**: `page.py` defines *where* widgets are placed. `graph_renderer.py` defines *how* data updates them.
* **Alternatives Considered**: Merging both into `page.py`.
* **Why Skipped**: By separating the layout from the live update loops, `page.py` remains a simple blueprint of the layout, while `graph_renderer.py` handles the high-frequency math updates.

### `gui/components/` (`sidebar.py`, `chart.py`, `notification.py`)
* **Design**: Self-contained UI controls.
* **Alternatives Considered**: Direct inline Tkinter declarations.
* **Why Skipped**: Custom widgets are reusable. For instance, `BaseChart` is used by the main dashboard, but it can also be instantiated in any of the four future Analytics tabs, saving hundreds of lines of code.

### `gui/dialogs/` (`manager.py`, `settings.py`, `launcher.py`)
* **Design**: Tabbed dialogue configurations and window mapping router.
* **Alternatives Considered**: Instantiating dialog classes directly inside `app.py`.
* **Why Skipped**: Putting class imports and duplicates check directly in `app.py` bloats the file. `launcher.py` acts as a clean router that handles window instantiation safely.

### `gui/analytics/` (`window.py` & Tabs)
* **Design**: A modular tabbed window layout where data references (`db`, `time_data`, `channels_data`) are passed to each tab constructor.
* **Alternatives Considered**: Creating a flat analytics window with no modular tabs.
* **Why Skipped**: A flat layout would make the file huge and hard to divide among team members. Creating a separate tab file for each view (`overview.py`, `statistics.py`, `signal.py`, `reports.py`) lets multiple developers work on different tabs at the same time.
