# BARC Dashboard — Scratch Development Design Decisions

This document acts as a development log explaining **why** the core technologies, libraries, and design patterns were chosen from day one of starting this project from scratch, and why alternative design options were skipped.

---

## 1. Choosing the Tech Stack (Core Technologies)

### Why CustomTkinter instead of PySide/PyQt or standard Tkinter?
* **The Decision**: CustomTkinter was chosen for the Graphical User Interface.
* **Why**: 
  * Standard Python Tkinter looks outdated and lacks native dark mode.
  * PyQt/PySide is highly powerful but has a steep learning curve and heavy licensing.
  * CustomTkinter provides modern, styled widgets (rounded corners, clean fonts, dark/light modes) right out of the box with standard Tkinter syntax.

### Why Matplotlib instead of other plotting libraries?
* **The Decision**: Matplotlib was selected for live signal rendering.
* **Why**:
  * Matplotlib is the industry standard for scientific plotting in Python.
  * Integrates natively with Tkinter using a backend canvas widget (`FigureCanvasTkAgg`).
  * Gives us a built-in Navigation Toolbar (for panning, zooming, and saving figures) with minimal configuration.

### Why SQLite instead of MySQL or PostgreSQL?
* **The Decision**: SQLite was chosen as the database management system.
* **Why**:
  * Serverless, zero-configuration database stored in a single file (`telemetry_archive.db`).
  * Supports standard SQL, transactions, foreign keys, and indexes, handling our JSON-serialized burst data easily.

---

## 2. Architecture & Directory Design

### Why separate the project into `core`, `models`, and `gui` packages?
* **The Decision**: Organized the codebase into an MVC (Model-View-Controller) inspired package structure.
* **Why**:
  * By splitting the code into `core/` (services, data sources, parser, database), `models/` (data structures like `TraceBurst`), and `gui/` (layouts), the backend remains completely independent.
  * Enables swapping out the simulator for USB Serial or BLE sources via a formal `DataSource` ABC without touching UI logic.

---

## 3. Concurrency & Data Flow

### Why use `queue.Queue` polling instead of sharing locked lists?
* **The Decision**: Refactored from locked arrays to a message-passing architecture using `queue.Queue`.
* **Why**:
  * Previously, the background thread would lock lists, append data, and trigger a UI redraw. This tightly coupled the UI to the background thread.
  * Using a standard thread-safe `queue.Queue`, the background `DataSource` just produces `TraceBurst` objects. The main UI thread uses a timer (`root.after`) to poll the queue.
  * This completely decouples acquisition speed from UI refresh rate and eliminates race conditions.

---

## 4. Telemetry Modeling & Storage

### Why use a "Burst" architecture instead of continuous sampling?
* **The Decision**: Switched the entire application to model data as discrete `TraceBurst` events rather than continuous time streams.
* **Why**:
  * The actual Arduino GIGA R1 firmware samples photodetector transients at 250 kSPS over 600μs, then processes the data. It sends this data in chunks, not a continuous stream.
  * Modeling the data as bursts (`TraceBurst` objects containing `TracePoint` lists) perfectly maps to the physical reality of the hardware.

### Why serialize trace data as JSON in SQLite?
* **The Decision**: The SQLite `trace_bursts` table stores `trace_data` as a serialized JSON string.
* **Why**:
  * Inserting 150 individual points into a SQL table for every single burst is incredibly slow and fragments the database.
  * By serializing the trace array into JSON, we can save an entire capture event in a single row insert, maintaining high performance while keeping the data structured.

---

## 5. Configuration & Persistence Design

### Why use the `AppConfig` class approach?
* **The Decision**: Centralized settings in a formal `AppConfig` class backed by JSON.
* **Why**:
  * Moving away from global variables makes the code testable and predictable.
  * `AppConfig` provides typed properties, handling migration, default values, and saving state to `config_settings.json` automatically.

---

## 6. Parsing & Communication

### Why use a dedicated `TraceParser`?
* **The Decision**: Extracted framing and CSV parsing into a `TraceParser` class used by both USB Serial and BLE.
* **Why**:
  * BLE packets arrive in 20-byte chunks. USB serial packets arrive as lines. The parser abstracts this away, buffering text until complete frames (`---BEGIN TRACE DATA---` to `---METRICS---`) are found.
  * This means the `BLESource` and `SerialSource` contain zero parsing logic, making them simple and reliable.
