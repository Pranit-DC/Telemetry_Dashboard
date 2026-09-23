# Software Requirements Specification (SRS)
# Telemetry Dashboard

**Version described:** current codebase (`v5.0.0`)
**Project type:** BARC internship/training project
**Platform:** Windows desktop (developed and run offline/air-gapped)
**Language:** Python 3.x

---

## 1. Introduction

### 1.1 Purpose

Defines the requirements for the current version of the Telemetry Dashboard: an
internship project built to acquire, visualize, store, and analyze high-speed
photodetector decay data from an Arduino GIGA R1.

### 1.2 Scope

The dashboard:
- Acquires burst-based telemetry from three interchangeable sources: a built-in
  simulator, USB Serial, and Bluetooth Low Energy (BLE).
- Visualizes the live decay trace and derived metrics in real time.
- Persists every burst to a SQLite database and a daily rolling CSV log.
- Supports session management (list, search, rename, delete, reload past runs).
- Provides a separate analytics window (trend view, trace overlay, histogram, PDF
  report export).
- Runs entirely offline, with no network dependency at runtime.

### 1.3 Product overview

The application interfaces with an Arduino GIGA R1 sampling a photodiode at 250 kSPS. On
each excitation pulse, the firmware captures a fixed 700-sample burst and sends it to the
dashboard as either ASCII text (USB Serial) or binary packets (BLE). The dashboard
reconstructs each burst, computes its peak voltage and exponential fall time (using the
same regression the firmware itself runs), displays it live, and stores it.

## 2. General Description

### 2.1 Product perspective

A standalone desktop application with a layered architecture: data acquisition and
business logic (`core/`, `models/`) are fully decoupled from the presentation layer
(`gui/`), so a source can be swapped or a new analysis feature added without touching UI
code, and vice versa.

### 2.2 Product features (current version)

- Three interchangeable acquisition sources: **Simulator**, **USB Serial**, **BLE**.
- Start / Pause / Resume / Stop session control.
- Live decay-trace chart with Matplotlib pan/zoom/save toolbar.
- Five live metric cards: Peak Voltage, Fall Time, Avg Fall Time, Std Dev, Min/Max Fall.
- Log console + connection-state diagnostics panel.
- SQLite persistence (sessions + per-burst trace data), WAL mode, single persistent
  connection.
- Daily rolling CSV metrics log (auto-rotate, 7-day retention) + full-trace CSV export.
- Session Manager dialog: list, search, rename, delete, reload.
- Settings dialog: connection parameters (COM port, baud rate, BLE device name, BLE
  timeout), UI/graphing options, file-path configuration.
- Analytics window: peak-voltage overview trend, recent-trace overlay, fall-time
  histogram, tabular report with PDF export.
- BLE loss recovery: per-sample gap detection and selective retransmission (up to 5
  rounds) rather than trusting a lossy stream.
- Graceful startup without optional hardware libraries (`pyserial`, `bleak`) installed —
  affected sources report an error state rather than crashing the app.

### 2.3 User characteristics

Intended for lab personnel who need to run and review photodetector decay acquisitions.
Basic computer literacy is assumed; no programming knowledge is required to operate the
dashboard day-to-day (only to extend it).

### 2.4 Operating environment

**Hardware:** Windows PC (primary target) or Linux; standard display, mouse, keyboard;
Arduino GIGA R1 with the matching firmware for Serial/BLE acquisition (optional — the
Simulator source requires no hardware at all).

**Software:** Python 3.9+, and the packages in `requirements.txt`
(`customtkinter`, `matplotlib`, `bleak`, `numpy`, `scipy`, `pyserial`). Designed to run
fully offline once installed — see `OFFLINE_DEVELOPMENT_GUIDE.md`.

### 2.5 Assumptions and dependencies

- Required Python packages are installed ahead of time from offline wheels (no runtime
  internet access assumed or required).
- SQLite is available as part of the Python standard library (`sqlite3`) — no separate
  database server needed.
- Real hardware acquisition (Serial/BLE) assumes the Arduino GIGA R1 is flashed with
  firmware matching the protocol described in `06_DATA_ACQUISITION_PROCESS.md`; a
  mismatched firmware version will not parse correctly.

## 3. Functional Requirements (summary)

| ID | Requirement |
|---|---|
| FR-1 | The system shall support switching between Simulator, Serial, and BLE data sources. |
| FR-2 | The system shall reconstruct complete 700-sample bursts from both Serial (text-framed) and BLE (binary-packet) transports. |
| FR-3 | The system shall detect and recover missing BLE samples via targeted retransmission, up to 5 rounds per burst, before discarding an unrecoverable burst. |
| FR-4 | The system shall compute peak voltage and fall time for every burst using a log-linear regression consistent with the firmware's own on-device calculation. |
| FR-5 | The system shall persist every burst of a recording session to SQLite, including its full raw trace. |
| FR-6 | The system shall write a daily rolling CSV summary log, retaining the last 7 days. |
| FR-7 | The system shall allow the user to start, pause, resume, and stop a recording session, with pause/resume continuing the same session rather than creating a new one. |
| FR-8 | The system shall allow browsing, searching, renaming, deleting, and reloading past sessions. |
| FR-9 | The system shall display a live decay-trace chart and derived metrics, updating within one polling interval (100 ms) of a burst's arrival. |
| FR-10 | The system shall provide an analytics view with an overview trend, a multi-trace overlay, a fall-time histogram, and a PDF-exportable report. |
| FR-11 | The system shall remain usable (Simulator source at minimum) even if optional hardware libraries are not installed. |

## 4. Non-Functional Requirements

- **Responsiveness** — the GUI event loop must never block on acquisition I/O; all
  hardware/simulator work happens on background threads, communicated via a thread-safe
  queue.
- **Data integrity** — no burst should be silently stored with missing or corrupted
  samples; an incomplete BLE burst that can't be fully recovered is discarded and logged,
  not stored partially.
- **Offline operation** — no feature may depend on network access at runtime.
- **Portability** — SQLite and CSV storage locations are user-configurable, since the
  target deployment (a specific Windows lab PC) isn't fixed in the codebase itself.

## 5. Out of scope (current version)

- Multi-channel simultaneous acquisition (the schema reserves a `channel` field, but
  every burst today is channel 0).
- Frequency-domain (FFT) analysis.
- Any cloud sync, remote access, or network-facing feature.
- Authentication/user accounts (single-user desktop tool).