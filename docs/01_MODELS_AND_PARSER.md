# 1. Data Models & the Serial Parser

This covers `models/telemetry.py` and `core/parser/trace_parser.py` — the data shapes
used everywhere in the app, and the parser that turns raw Serial text into those shapes.

(BLE has its own, different parser — see `06_DATA_ACQUISITION_PROCESS.md`.)

---

## 1.1 Why "bursts" instead of a continuous stream?

The photodiode doesn't produce a smooth trickle of data — the firmware fires an LED,
waits for the decay, and captures a fixed 700-sample window (2.8 ms) each time, about
4 times a second. Streaming 250,000 samples/sec continuously over Serial would overload
the link and freeze the GUI, so instead the hardware groups each capture into one
**burst** and sends it in one go. The dashboard mirrors that with two data classes.

## 1.2 `models/telemetry.py`

```python
@dataclass
class TracePoint:
    sample_index: int
    time_us: float
    voltage: float

@dataclass
class TraceBurst:
    burst_id: int
    timestamp: datetime
    trace_points: List[TracePoint]
    peak_voltage: float
    fall_time_us: float
    avg_fall_time_us: float
    channel: int = 0
```

- `TracePoint` is one sample: its position in the burst, its time in microseconds, and
  the voltage reading.
- `TraceBurst` is one full capture: a list of `TracePoint`s (700 of them, in normal
  operation) plus the computed metrics for that burst.

`TraceBurst` also has serialization helpers, because the raw trace has to be stored in
SQLite and sometimes exported/loaded as JSON:

- `to_dict()` / `from_dict()` — convert to/from a plain dictionary.
- `trace_to_json()` — pack just the `trace_points` into a compact JSON string
  (`[[index, time_us, voltage], ...]`). This is what actually gets written into the
  `trace_data` column in SQLite.
- `trace_from_json()` — the reverse, used when loading a saved session back.

## 1.3 `core/parser/trace_parser.py` — the Serial framing parser

Serial data doesn't arrive as neat lines — a single read might return half a line, or
several bursts glued together. `TraceParser` keeps an internal buffer and only processes
data up to the last complete line, saving the leftover fragment for next time.

### Frame format it understands

```
<<BEG>>
Sample_Index,Time_us,Voltage_V
0,0.0,2.3120
1,4.0,2.3050
...
699,2796.0,0.0842
<<END>>
```

- `<<BEG>>` — start of a new burst. Clears any partial state.
- The header line `Sample_Index,Time_us,Voltage_V` is just skipped.
- Each following `index,time_us,voltage` line becomes one `TracePoint`.
- `<<END>>` — burst is complete. At this point the parser:
  1. Computes `peak_voltage` (the maximum voltage in the burst), if not already known.
  2. Computes `fall_time_us` by doing the same log-linear regression the firmware does
     (see `06_DATA_ACQUISITION_PROCESS.md` for the math) — because the firmware doesn't
     actually transmit a metrics block over Serial, the parser always calculates this
     itself, from the raw voltages.
  3. Updates a rolling average of the last 10 valid fall times → `avg_fall_time_us`.
  4. Emits a finished `TraceBurst`.

The parser also recognizes an optional `---METRICS---` block (`key=value` lines) if a
future firmware version ever sends one — but the current firmware doesn't use it, so in
practice every burst's metrics are always calculated in Python from the raw samples.

### A worked example

```python
from core.parser.trace_parser import TraceParser

parser = TraceParser()
bursts = parser.feed("<<BEG>>\nSample_Index,Time_us,Voltage_V\n0,0.0,2.50\n")
# bursts == [] here — the frame hasn't closed yet, and the trailing partial
# line (no newline) is held in the internal buffer until more data arrives.

more_bursts = parser.feed("1,4.0,2.10\n<<END>>\n")
# more_bursts now contains one completed TraceBurst
```

### A couple of things worth knowing

- `MAX_LINE_BUFFER = 100000` — if the buffer somehow grows past 100 KB without ever
  seeing a newline (e.g. a corrupted connection sending garbage), the parser just resets
  itself rather than growing forever.
- Malformed sample lines (wrong number of fields, non-numeric values) are silently
  skipped rather than crashing the parser.
- `burst_id` is a simple incrementing counter owned by the parser instance — it does not
  come from the firmware.