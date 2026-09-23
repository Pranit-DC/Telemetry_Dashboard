# Telemetry Dashboard

> A Python desktop application for receiving, visualizing, and analyzing high-speed
> telemetry from an Arduino-based photodetector acquisition system.

## Project Overview

The goal is a clean, modular dashboard for tracking exponential decay transients captured by an Arduino GIGA R1.

The application uses a **burst-based** model: each excitation pulse produces one
700-sample capture (2.8 ms), sent as a discrete unit rather than a continuous stream.
Data can come from USB Serial, Bluetooth Low Energy (BLE), or a built-in Simulator.

## Features

- **Modern GUI**
  — dark-themed, built with `customtkinter`.
- **Live decay-trace chart**
  — full-width `matplotlib` plot of the most recent 700-sample capture, with pan/zoom/save
  toolbar.
- **Three interchangeable data sources**
  — Simulator, USB Serial, BLE (with per-sample loss detection and retransmission over BLE).
- **Persistence**
  — SQLite (`telemetry.db`, WAL mode) plus daily rolling CSV summaries.
- **Session management**
  — browse, search, rename, delete, and reload past recording runs.
- **Analytics window**
  — peak-voltage trend, recent-trace overlay, fall-time histogram, and one-click PDF report
  export.

## Installation & Setup

All dependencies can be installed offline via pre-downloaded `.whl` files (see
`docs/OFFLINE_DEVELOPMENT_GUIDE.md`). Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

**Dependencies:** `customtkinter`, `matplotlib`, `bleak`, `numpy`, `scipy`, `pyserial`

## Running the Application

```bash
python main.py
```

Starts on the Simulator source by default, so it's usable without any hardware attached.

## Architecture Summary

The codebase separates the UI layer from core business logic:

- **`gui/`**
  — the main window, dashboard layout, dialogs (Settings, Session Manager), and the Analytics
  window.
- **`core/`**
  — data sources (Simulator/Serial/BLE), protocol parsing, the fall-time regression, the
  acquisition service, database, and CSV logging.
- **`models/`**
  — the `TraceBurst`/`TracePoint` data classes used to move data through the app.

## Firmware

The matching Arduino GIGA R1 firmware is in `firmware/`. It samples at 250 kSPS using the
`AdvancedAnalog` library, runs the fall-time regression on-device for its own local
display, and sends each 700-sample burst to the dashboard as framed ASCII text over USB
CDC or as binary packets over BLE (Nordic UART Service) — see
`docs/06_DATA_ACQUISITION_PROCESS.md` for the exact wire formats.

## Testing

```bash
pip install --no-index --find-links . pytest==9.1.1
pytest tests/ -v                       # pure logic — no hardware needed
pytest tests/hardware --port COM7 -v   # real GIGA — plug in, flash firmware, then run
```