# Design Decisions

A log of the "why" behind the main technical choices, for anyone (including a review
panel) asking "why did you build it this way?"

---

## Tech stack

**CustomTkinter, not plain Tkinter or PyQt/PySide.** Plain Tkinter looks dated and has no
built-in dark mode. Qt-based toolkits are powerful but heavier to learn and to package,
especially with the offline/air-gapped constraint. CustomTkinter gives modern-looking
widgets (rounded corners, dark theme) on top of the standard library's Tkinter, with a
similar API — a reasonable middle ground for a learning project.

**Matplotlib, not a custom or lighter-weight plotting widget.** It's the standard for
scientific plotting in Python, it embeds directly into Tkinter via
`FigureCanvasTkAgg`, and it comes with a working pan/zoom/save toolbar for free — useful
for actually inspecting a decay curve, not just glancing at it.

**SQLite, not a client-server database.** Single file, zero setup, no service to install
or keep running — a good fit for a single-user desktop tool in an offline lab
environment. Supports real SQL, indexes, and foreign keys, which is all this project
needs.

## Architecture

**Split into `core/`, `models/`, `gui/`.** Keeping business logic (`core/`) completely
separate from the UI (`gui/`) means a data source can be swapped (simulator ↔ Serial ↔
BLE) without touching a single line of GUI code, and the parsing/regression/storage logic
can be unit-tested without ever opening a window (see the `tests/` folder).

**A `DataSource` abstract base class.** `SimulatorSource`, `SerialSource`, and
`BLESource` all expose the same five methods. `AcquisitionService` and the GUI never
branch on "which kind of source is this" — they just call `connect()`/`start()`/`stop()`
on whatever's currently active.

## Concurrency

**`queue.Queue`, not shared/locked lists.** Background threads (Serial reads, BLE
notifications, the simulator's timer loop) never touch the GUI directly. They only ever
push finished `TraceBurst` objects into a `queue.Queue`; the GUI thread drains it on a
100 ms timer. This keeps acquisition speed and UI refresh rate independent, and avoids
the class of bugs where a background thread updates a Tkinter widget out from under the
main event loop.

## Data modeling

**Burst-based, not a continuous stream.** The hardware itself doesn't produce a
continuous stream — it fires, captures a fixed 700-sample window, and repeats. Modeling
data as discrete `TraceBurst` events (each holding a list of `TracePoint`s) matches the
physical reality of the sensor directly, rather than forcing it into a shape it doesn't
naturally have.

**Fall-time regression ported line-for-line from the firmware.** Rather than trusting
whatever number the Arduino reports (which the current firmware doesn't even send over
Serial, and which the BLE path deliberately never trusts either), the exact same
log-linear regression — same offsets, same thresholds, same rounding constant — is
reimplemented in Python (`core/analysis/fall_time.py`). This guarantees the number shown
on screen is what the raw samples actually support, computed the same way regardless of
which transport delivered them.

**Trace data stored as one JSON blob per burst, not one row per sample.** At a few
bursts a second with 700 samples each, one-row-per-sample would create an enormous number
of rows very quickly and make every session load or delete much slower. Serializing the
700 points into a single JSON string in one `trace_data` column keeps writes to one
`INSERT` per burst.

## BLE protocol

**Binary packets with per-sample indices, not text framing.** An earlier version sent
BLE data as `<<BEG>>`/`<<END>>` text, the same as Serial. The problem: a single dropped
BLE notification could silently corrupt or truncate an entire burst, with no way to tell
which samples were actually missing. Switching to one binary packet per sample (each
carrying its own index) means gaps are detectable and — via the RESEND command —
recoverable, at the cost of a slightly more involved protocol.

## Configuration

**A typed `AppConfig` class over raw globals**, backed by `config_settings.json`.
Centralizing settings behind typed properties (with sensible defaults if a key is
missing) is more predictable and testable than passing loose module-level constants
around, and makes the Settings dialog a straightforward read/write against one object.