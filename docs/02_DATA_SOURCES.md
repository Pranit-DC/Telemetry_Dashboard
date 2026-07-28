# 2. Data Sources — Simulator, USB Serial, BLE

Covers `core/sources/` — the abstraction that lets the rest of the app not care whether
data is coming from real hardware or a synthetic generator.

---

## 2.1 The shared interface (`core/sources/base.py`)

Every source is a `DataSource` subclass and implements the same five methods:

```python
class DataSource(ABC):
    def __init__(self, burst_queue: Queue): ...
    def connect(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def disconnect(self) -> None: ...
    def send_command(self, command: str) -> None: ...
    @property
    def source_type(self) -> str: ...   # 'simulator' | 'serial' | 'ble'
```

Every source also tracks a small state machine — `disconnected`, `connecting`,
`connected`, `acquiring`, `error` — and calls a registered callback whenever the state
changes, so the GUI's status label can stay in sync without polling.

Because all three sources share this interface, `AcquisitionService` can create whichever
one the user picks and use it identically — nothing else in the app needs to know or care
which one is active.

## 2.2 `SimulatorSource` — synthetic data for development/demo

No hardware needed. Every `burst_interval` seconds (default 0.25 s, ~4 Hz — matching the
real hardware's pulse rate) it generates one realistic 700-sample burst:

1. A noisy flat baseline (~2.15–2.35 V) before the "trigger" point.
2. A sharp drop at a randomized index near the start of the burst.
3. An exponential decay down to a noisy floor (~0.06–0.12 V).
4. Correlated ("smooth-ish"), not purely random, noise throughout — closer to what a
   real photodiode/ADC actually looks like than plain white noise.

The shape was calibrated against one real captured burst from the hardware, so it's a
first approximation rather than a statistically-validated model — worth refining further
once more real captures are available.

Importantly, the simulator computes its `peak_voltage`/`fall_time_us`/`avg_fall_time_us`
using the exact same `FallTimeCalculator` that real BLE data goes through — it never
invents numbers separately from the curve it draws, so what's displayed always matches
what's plotted.

## 2.3 `SerialSource` — USB connection to the Arduino

Opens a `pyserial` connection (default port `COM15`, 115200 baud — both configurable in
Settings), sends a `"START\n"` / `"STOP\n"` text command to arm/disarm the firmware, and
runs a background thread that calls `readline()` in a loop, feeding each line into a
`TraceParser` (see `01_MODELS_AND_PARSER.md`). Completed bursts go straight into the
shared `burst_queue`.

If `pyserial` isn't installed, the import is wrapped in a `try/except`, so the app still
starts — attempting to connect a Serial source without the library just puts it into the
`'error'` state instead of crashing on launch. This matters in the air-gapped BARC
environment, where a dependency might not be installed yet.

## 2.4 `BLESource` — Bluetooth Low Energy connection

BLE is the more involved source, because BLE notifications can be dropped, and losing
even one sample out of 700 would corrupt the regression. So instead of streaming text,
the firmware and dashboard use a small binary protocol with **retransmission of exactly
the samples that went missing** ("Selective Repeat ARQ" — see `06_DATA_ACQUISITION_PROCESS.md`
for the full wire format).

In short:
1. `connect()` scans for a device named `GIGA_WORKSTATION` (configurable) using `bleak`,
   and connects using the Nordic UART Service profile.
2. `start()` subscribes to notifications and writes a `START` command.
3. As sample packets arrive, `BLEBurstAssembler` (see `01_MODELS_AND_PARSER.md`'s sibling
   file, `core/parser/ble_binary_parser.py`) records which indices have been received.
4. When the "END" packet arrives, if any samples are missing, the source asks the
   firmware to resend just those indices — up to 5 rounds — before giving up and
   discarding that burst (logging how many samples were permanently lost).
5. Once a burst is complete, `FallTimeCalculator` computes the metrics **in Python, from
   the raw voltages** — it never trusts a number from the firmware, so results are
   consistent regardless of transport.
6. The dashboard sends a BURST_ACK back to the Arduino once the burst is safely stored,
   so the firmware's auto-capture loop knows it's safe to overwrite its buffer and move
   on to the next pulse.

`bleak` runs on `asyncio`, but Tkinter runs its own synchronous loop, so `BLESource` spins
up its own background thread with a private `asyncio` event loop, and uses
`asyncio.run_coroutine_threadsafe(...)` whenever code outside that thread (e.g.
`stop()` called from the GUI) needs to schedule something onto it. Like `SerialSource`,
the `bleak` import is wrapped in `try/except` so a machine without it can still run in
Simulator mode.

## 2.5 Switching sources at runtime

`AcquisitionService.set_source(source_type)` (see `04_CONCURRENCY_AND_SERVICES.md`) is
how a source gets created and swapped in. Switching sources disconnects whatever was
active first, so only one source is ever live at a time.