# Offline Development Guide

How to work on this project inside the air-gapped BARC setup, plus an index of the rest
of the documentation and a summary of the test suite.

---

## 1. Documentation map

| Doc | What's in it |
|---|---|
| `ARCHITECTURE.md` | Folder-by-folder tour, component responsibilities, full data flow |
| `01_MODELS_AND_PARSER.md` | `TracePoint`/`TraceBurst` data classes, the Serial text parser |
| `02_DATA_SOURCES.md` | Simulator / USB Serial / BLE data sources |
| `03_DATABASE_AND_STORAGE.md` | SQLite schema, daily CSV logging |
| `04_CONCURRENCY_AND_SERVICES.md` | The background-thread/queue model, `AcquisitionService` |
| `05_GUI_AND_VISUALIZATION.md` | Window layout, dialogs, Analytics tabs |
| `06_DATA_ACQUISITION_PROCESS.md` | Arduino firmware capture + regression math, both wire protocols in full detail |
| `DESIGN_DECISIONS.md` | Why each major technical choice was made |
| `WORKFLOW.md` | Startup → live acquisition → stop/replay → shutdown, step by step |
| `PROJECT_REPORT.md` | Formal write-up, closer to what you'd hand to a review panel |
| `SRS_v5.0_Telemetry_Dashboard.md` | Software Requirements Specification for the current version |

A reasonable reading order if you're new to the project: `ARCHITECTURE.md` →
`WORKFLOW.md` → the numbered docs (01 → 06) → `DESIGN_DECISIONS.md`.

## 2. The offline development setup

- **Primary machine**: Windows, no internet access. This is where the app is actually
  developed, run, and tested against real hardware.
- **Linux VM**: has internet access, used *only* to download wheels/installers, which are
  then transferred to the Windows machine and installed manually (no live package-manager
  access on Windows).
- Everything the app needs at runtime is either in the Python standard library
  (`dataclasses`, `queue`, `sqlite3`, `threading`, `math`, `json`, `csv`, `asyncio`) or one
  of the packages in `requirements.txt`:

  ```
  customtkinter
  matplotlib
  bleak
  numpy
  scipy
  pyserial
  ```

  Install with `pip install -r requirements.txt` from pre-downloaded wheels
  (`pip install --no-index --find-links <wheel_folder> -r requirements.txt` if working
  fully offline from a local wheel cache).

- **Graceful degradation without hardware libraries**: `pyserial` and `bleak` are both
  imported inside `try/except ImportError` blocks in `core/sources/serial_source.py` and
  `core/sources/ble_source.py`. If either isn't installed yet, the app still starts —
  attempting to connect that particular source just puts it into the `'error'` state
  instead of crashing the whole app on launch. The Simulator source has no external
  dependency at all, so it always works.

## 3. Testing

The `tests/` folder has two tiers:

**Pure logic tests (`tests/*.py`)** — no hardware needed, safe to run anywhere, anytime:

```bash
pytest tests/ -v
```

Covers, one file per module:
- `test_models.py` — `TraceBurst` serialization round-trips
- `test_trace_parser.py` — the Serial `<<BEG>>`/`<<END>>` framing parser
- `test_ble_binary_parser.py` — the BLE `BLEBurstAssembler` and command builders
- `test_fall_time.py` — the `FallTimeCalculator` regression math
- `test_simulator_source.py` — the synthetic data generator
- `test_database_manager.py` — SQLite storage/retrieval
- `test_acquisition_service.py` — session lifecycle and queue routing

**Hardware-in-the-loop tests (`tests/hardware/`)** — talk to a real, connected GIGA over
its actual Serial port. Only run these with the board plugged in and the current firmware
flashed:

```bash
pytest tests/hardware --port COM7 -v
```

The port can be given three ways (checked in this order): the `--port` command-line flag,
the `TELEMETRY_TEST_PORT` environment variable, or auto-detection (first COM port whose
description mentions "Arduino"/"GIGA"); otherwise it falls back to the project's default
(`COM15`, see `config.py`). Covers basic connectivity (`test_connectivity.py`) and a real
end-to-end capture over Serial (`test_serial_acquisition.py`).

## 4. Working across the two firmware versions

If you're comparing two firmware variants (as mentioned when this project started), the
important thing to check for each is: which mode-routing scheme it uses (`ROUTE_LOCAL_ONLY`
/ `ROUTE_REMOTE_USB` / `ROUTE_REMOTE_BLE`), what it sends on the Serial route (should match
the `<<BEG>>`/`<<END>>` CSV framing in `06_DATA_ACQUISITION_PROCESS.md`), and what it sends
on the BLE route (should match the binary SAMPLE/END packet format in the same doc) — since
`TraceParser` and `BLEBurstAssembler` on the Python side are written against those exact
formats and won't tolerate a firmware that drifts from them without also updating the
parser.