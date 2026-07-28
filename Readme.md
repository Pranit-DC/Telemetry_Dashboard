# BARC Telemetry Dashboard

A modern, Python-based desktop application designed to receive, visualize, and analyze high-speed telemetry data from an Arduino-based photodetector acquisition system.

## Project Overview

This project was built during an internship at the Bhabha Atomic Research Centre (BARC). The goal is to provide a clean, modular, and maintainable dashboard for tracking exponential decay transients captured by an Arduino GIGA R1 at 250 kSPS.

The application uses a **burst-based trace architecture** that natively understands the framed ASCII protocol transmitted by the hardware. It supports acquiring data via USB Serial, Bluetooth Low Energy (BLE), or a synthetic data Simulator.

## Features

- **Modern GUI**: Dark-themed, responsive interface built with `customtkinter`.
- **Dual-View Graphing**: Uses `matplotlib` to render both the latest high-resolution decay trace curve and a trend chart of computed fall times across bursts.
- **Multiple Data Sources**: Seamlessly switch between Simulation, USB Serial, and BLE.
- **Data Persistence**: Records sessions in a structured SQLite database (`telemetry_archive.db`) and exports daily summary logs to CSV files.
- **Session Management**: A dedicated console to view, rename, load, and delete historical recording runs.
- **Analytics Ready**: Modular tab architecture ready for advanced signal processing routines.

## Installation & Setup

All dependencies can be installed offline via downloaded `.whl` files. Ensure you are using Python 3.9+.

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `customtkinter`
- `matplotlib`
- `bleak`
- `numpy`
- `scipy`
- `pyserial`

## Running the Application

Start the dashboard using the main entry point:

```bash
python main.py
```

## Architecture Summary

The codebase strictly separates the UI layer from the core business logic (MVC pattern).

- **`gui/`**: Contains the `TelemetryDashboard` controller, the dashboard layout, custom widget components, and dialog windows.
- **`core/`**: Houses the `AcquisitionService`, database management, CSV logging, signal analysis math, and the `DataSource` implementations (`SerialSource`, `BLESource`, `SimulatorSource`).
- **`models/`**: Defines the central `TraceBurst` and `TracePoint` dataclasses used to transport data across the app.

For full architectural details, data flow diagrams, and design decisions, please refer to the documentation in the `/docs/` directory.

- [System Architecture (v5.0.0)](docs/ARCHITECTURE.md)
- [Execution & Data Workflow](docs/WORKFLOW.md)
- [Design Decisions](docs/DESIGN_DECISIONS.md)

## Firmware

The matching Arduino GIGA R1 firmware is available in the `firmware/` directory. It uses the `AdvancedAnalog` library to sample at 250 kSPS, performs onboard log-linear regression, and transmits framed text packets to the dashboard via native USB CDC or Nordic BLE UART.

## Testing

- pytest tests/ -v                          # pure logic, always runs, no hardware
- python -m pytest tests/ -v
- pytest tests/hardware --port COM7 -v      # real GIGA — plug in, flash firmware, then run
