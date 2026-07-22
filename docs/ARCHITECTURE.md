# BARC Telemetry Dashboard — System Architecture

This document describes the software architecture of the BARC Telemetry Dashboard, specifically following the major refactoring to a burst-based trace acquisition model (v5.0.0).

## 1. High-Level Overview

The dashboard is designed to interface with an Arduino GIGA R1 that performs high-speed data acquisition (250 kSPS) of photodetector decay transients. Instead of receiving a continuous stream of low-frequency data, the dashboard receives **bursts** of trace data (approximately 151 points over 600 microseconds) followed by computed metrics (peak voltage, fall time) for each pulse event.

The dashboard provides a modern GUI to start/stop the acquisition, visualize the latest trace curve, plot the trend of the metrics over time, and persist all data to a SQLite database and daily CSV logs.

### Key Characteristics
- **Burst-Based Data Model**: Data is handled in discrete `TraceBurst` units rather than continuous arrays.
- **Unified Data Sources**: Simulator, USB Serial, and Bluetooth Low Energy (BLE) are all supported via a common `DataSource` interface.
- **Centralized Service Layer**: An `AcquisitionService` manages the data flow, decoupling the UI from the background processing threads.
- **Protocol Encapsulation**: A dedicated `TraceParser` translates the Arduino's framed ASCII protocol into Python objects.

## 2. Component Architecture

### 2.1 Core Services (`core/`)
The `core` package contains all business logic and data management.

- **`core.sources.DataSource`**: An Abstract Base Class defining the contract for data sources (`connect`, `start`, `stop`, `disconnect`, `send_command`).
  - `SimulatorSource`: Generates synthetic exponential decay bursts for testing.
  - `SerialSource`: Connects to the Arduino via USB CDC (Virtual COM port).
  - `BLESource`: Connects to the Arduino via Bluetooth Low Energy using the Nordic UART Service profile.
- **`core.parser.TraceParser`**: A stateful parser that buffers incoming ASCII data from Serial or BLE, detects `---BEGIN TRACE DATA---` and `---METRICS---` framing markers, and emits complete `TraceBurst` objects.
- **`core.services.AcquisitionService`**: The orchestrator. It holds the active `DataSource`, creates sessions in the database, polls a thread-safe `queue.Queue` for new bursts, and routes them to the database, CSV logger, and GUI callbacks.
- **`core.database.DatabaseManager`**: Manages the SQLite database (`telemetry_archive.db`). Implements a schema focused on sessions and bursts, storing the raw trace points as serialized JSON arrays for efficient retrieval.
- **`core.logging.RollingCSVLogger`**: Writes daily summary CSV files containing the metrics for each burst.

### 2.2 Models (`models/`)
- **`TracePoint`**: A `@dataclass` representing a single sample (index, time in μs, voltage).
- **`TraceBurst`**: A `@dataclass` representing a complete pulse event. Contains a list of `TracePoint`s and the computed metrics (`peak_voltage`, `fall_time_us`, `avg_fall_time_us`).

### 2.3 GUI (`gui/`)
Built with `CustomTkinter` and `matplotlib`.

- **`TelemetryDashboard` (`app.py`)**: The main application window. It initializes the `AcquisitionService` and polls it periodically (e.g., every 100ms) to update the UI without blocking the main event loop.
- **`DashboardPage`**: Displays the active telemetry data. Features a dual-view graph layout:
  - **Decay Trace Chart**: Shows the voltage vs. time curve of the *most recent* burst.
  - **Measurement Trend Chart**: Plots the fall time over successive bursts to visualize stability.
  - **Metric Cards**: Display the current numerical values.
- **Dialogs**:
  - `SettingsWindow`: Configures App settings (COM port, BLE device name, UI scaling).
  - `SessionManagerWindow`: Allows users to browse, rename, delete, or load past recording sessions from the database.

## 3. Data Flow

1. **Hardware/Simulator**: The Arduino (or Simulator) detects a pulse, captures the decay, performs a log-linear regression, and transmits the data as ASCII text.
2. **Background Thread**: The active `DataSource` (running in a background thread) receives the data (chunks for BLE, lines for Serial).
3. **Parsing**: The data is fed into the `TraceParser`, which reconstructs the protocol frames and yields a `TraceBurst` object.
4. **Queue**: The `TraceBurst` is placed into a thread-safe `queue.Queue`.
5. **Main Thread**: The `TelemetryDashboard` periodically calls `AcquisitionService.poll_queue()`.
6. **Storage**: `AcquisitionService` writes the burst to SQLite via `DatabaseManager` and to CSV via `RollingCSVLogger`.
7. **Visualization**: The dashboard updates the trace chart, trend chart, and metric cards with the new burst data.

## 4. Firmware Interaction

The dashboard expects the Arduino to follow a specific framed protocol:

```text
---BEGIN TRACE DATA---
Sample_Index,Time_us,Voltage_V
0,0.0,2.4521
...
150,600.0,0.8234
---END TRACE DATA---
---METRICS---
peak_voltage=2.4521,fall_time_us=156.3,avg_fall_time_us=158.1
```

The dashboard also sends commands to the Arduino to control acquisition:
- `START\n`: Instructs the Arduino to begin waiting for triggers and sending data.
- `STOP\n`: Instructs the Arduino to halt acquisition and return to idle.
