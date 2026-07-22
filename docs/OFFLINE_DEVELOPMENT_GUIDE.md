# 🎓 BARC Telemetry Dashboard (v5.0.0) — Mentor's Offline Development Handbook

Welcome to the BARC Telemetry Dashboard project! As your senior mentor, my goal is not just to give you code to copy-paste, but to teach you **how to think like a systems developer**. 

When working on high-speed data acquisition (DAQ) systems in an air-gapped environment (like BARC), you need to understand **why** every component exists, **how** data flows through the system, and **what pitfalls** to avoid.

---

## 🏛️ Project Architecture: The Big Picture

Before writing a single line of code, let's understand the engineering transformation we are making:

```
+-----------------------------------------------------------------------------------+
|                                  DATA SOURCES                                     |
|   [SimulatorSource]        [SerialSource (USB)]         [BLESource (Bluetooth)]  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Raw String Streams)
+-----------------------------------------------------------------------------------+
|                             CORE PARSER & REGRESSION                              |
|   [TraceParser] ──> Parses ASCII Frames & Calculates Peak + Fall Time Math          |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (TraceBurst Objects)
+-----------------------------------------------------------------------------------+
|                             CONCURRENCY PIPELINE                                  |
|   [AcquisitionService] ──> Pushes into Thread-Safe Queue (queue.Queue)            |
+-----------------------------------------------------------------------------------+
                     │                                         │
                     ▼ (Async Storage)                         ▼ (100ms UI Polling)
+----------------------------------------+   +--------------------------------------+
|          STORAGE ENGINE                |   |          PRESENTATION LAYER          |
|  [DatabaseManager] ──> SQLite WAL DB   |   |  [TelemetryDashboard (CustomTkinter)]|
|  [RollingCSVLogger] ──> CSV Rotator    |   |   ├─ [DashboardPage] (50/50 Dual View)|
+----------------------------------------+   |   ├─ [GraphRenderer] (Drill-Down)    |
                                             |   └─ [Sidebar] (Control Panel)       |
                                             +--------------------------------------+
```

---

## 🧭 The 5-Step Mentorship Roadmap

Follow these modules in order. Each module is structured to guide your thinking, explain the logic, highlight common traps, and provide self-verification exercises:

| Module | Title & Focus | File Link |
|---|---|---|
| **Module 1** | Data Modeling & Protocol Framing | [01_MODELS_AND_PARSER.md](file:///home/pranitchiman/Projects/barc_dashboard/barc_dashboard/docs/01_MODELS_AND_PARSER.md) |
| **Module 2** | Polymorphic Data Source Abstraction | [02_DATA_SOURCES.md](file:///home/pranitchiman/Projects/barc_dashboard/barc_dashboard/docs/02_DATA_SOURCES.md) |
| **Module 3** | Persistence & Concurrency Safety (SQLite WAL + CSV) | [03_DATABASE_AND_STORAGE.md](file:///home/pranitchiman/Projects/barc_dashboard/barc_dashboard/docs/03_DATABASE_AND_STORAGE.md) |
| **Module 4** | Acquisition Pipeline & Thread-Safe Queues | [04_CONCURRENCY_AND_SERVICES.md](file:///home/pranitchiman/Projects/barc_dashboard/barc_dashboard/docs/04_CONCURRENCY_AND_SERVICES.md) |
| **Module 5** | GUI Component Engineering & Matplotlib Rendering | [05_GUI_AND_VISUALIZATION.md](file:///home/pranitchiman/Projects/barc_dashboard/barc_dashboard/docs/05_GUI_AND_VISUALIZATION.md) |

---

## 💡 How to Use These Guides as a Junior Developer

For each module, follow this workflow:

1. **Read the Design Rationale:** Understand *what problem* this module solves.
2. **Review the Architectural Blueprint:** Study the class diagrams and responsibility boundaries.
3. **Build the Skeleton:** Create the file structure and write the class signatures yourself.
4. **Implement Step-by-Step:** Follow the guided logic steps, paying attention to the **Mentor's Tips** and **Common Pitfalls**.
5. **Run the Self-Test Verification:** Execute the provided test script to prove your implementation works *before* moving to the next module.
6. **Compare with Reference Implementation:** Check your code against the reference solution at the end of the module.

---

## 🛠️ Offline Toolkit & Rules at BARC

- **No Internet Access:** All standard Python modules used (`dataclasses`, `queue`, `sqlite3`, `threading`, `math`, `json`, `csv`, `asyncio`) are built into Python 3.10+.
- **Graceful Imports:** Optional 3rd party hardware libraries (`pyserial`, `bleak`) must always be wrapped in `try...except ImportError` so the application can run in **Simulator Mode** even if wheels are missing.
- **Clean Architecture:** Never mix GUI code inside backend parser files, and never do database disk I/O directly on the Tkinter main loop thread.

Let's begin with **Module 1: Data Modeling & Protocol Framing**!
