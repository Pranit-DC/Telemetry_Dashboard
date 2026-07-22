# Module 1: Data Modeling & Protocol Framing

Welcome to Module 1! In this module, you will build the foundational data structures and the protocol parser for the telemetry dashboard.

---

## 🎯 Learning Objectives
By the end of this module, you will understand:
- The difference between continuous time-series streaming and **Event-Burst** data modeling.
- How to write clean, memory-efficient data structures using Python `@dataclass`.
- How to implement a robust **State Machine Parser** to handle chunked serial text streams.
- How to implement **on-the-fly logarithmic linear regression** to compute exponential decay times.

---

## 1. Problem Statement & Design Rationale

### Why move from continuous samples to Event-Bursts?
In the old code, telemetry was treated as a continuous stream of $(t, V)$ points. But our photodetector hardware (Arduino GIGA R1) fires in short, high-speed pulses at **250,000 samples/sec**. 

If we try to stream 250 kSPS continuously over serial, the serial port will choke, and Tkinter will freeze. Instead, the hardware records a 600 μs window (151 points), frames it in ASCII, and transmits it as a single **Burst Event**.

We need to model this using two distinct classes:
1. `TracePoint`: Stores a single sample point `(sample_index, time_us, voltage)`.
2. `TraceBurst`: Stores a complete capture event, including its 151 points, timestamp, peak voltage, and fall time.

---

## 2. Step 1: Building the Data Models (`models/telemetry.py`)

### 💡 Mentor's Guidance on Dataclasses
Use Python's built-in `dataclasses` module. It automatically generates `__init__()`, `__repr__()`, and `__eq__()` methods for you, reducing boilerplate code.

### Tasks for you:
1. Create `models/telemetry.py`.
2. Define `TracePoint` with three attributes: `sample_index: int`, `time_us: float`, `voltage: float`.
3. Define `TraceBurst` with attributes for `burst_id`, `timestamp`, `trace_points`, `peak_voltage`, `fall_time_us`, `avg_fall_time_us`, and `channel`.
4. Add helper methods for serialization:
   - `to_dict()`: Converts the burst to a dictionary (useful for JSON/API exporting).
   - `from_dict()`: Constructs a `TraceBurst` from a dictionary.
   - `trace_to_json()`: Serializes `trace_points` into a compact JSON string for SQLite storage.

### ⚠️ Common Pitfalls to Avoid:
> **Mutable Default Arguments:** Never write `trace_points: List[TracePoint] = []` in dataclasses! In Python, default list parameters are shared across all instances. Use `field(default_factory=list)` or initialize in custom code.

---

## 3. Step 2: Designing the ASCII Protocol Parser (`core/parser/trace_parser.py`)

### 💡 Mentor's Guidance on Stream Parsing
Serial and Bluetooth data arrives in random, fragmented text chunks. A single call to `read()` might give you half a line, or three bursts at once!

Your parser must handle this by maintaining an internal **line buffer**:
```
Incoming Chunk: "---BEGIN TRACE DATA---\nSample_Index,Time_us,"
Buffer keeps: "Sample_Index,Time_us," until the next chunk brings "\n"
```

### Protocol Specification:
The parser must recognize the following state transitions:
- `---BEGIN TRACE DATA---` $\rightarrow$ Change state to `in_frame`, clear temporary point buffer.
- `Sample_Index,Time_us,Voltage_V` $\rightarrow$ Skip header line.
- `10, 0.0, 2.5000` $\rightarrow$ Parse CSV floats and append `TracePoint`.
- `---END TRACE DATA---` $\rightarrow$ Transition state to `idle`, calculate peak voltage & fall time, emit `TraceBurst`.

---

## 4. Step 3: Implementing the Embedded Linear Regression

### Why do regression in Python?
To save serial bandwidth, the Arduino transmits only raw $(t, V)$ points without metric headers. The parser must compute the exponential decay fall time ($10\% \rightarrow 90\%$) itself using least-squares linear regression:

Given $V(t) = V_0 \cdot e^{-\lambda t}$, taking the natural log yields:
$$\ln(V) = \ln(V_0) - \lambda t$$

This is a straight line $y = m x + c$ where $y = \ln(V)$, $x = t$, and slope $m = -\lambda$.

The least-squares slope formula is:
$$m = \frac{N \sum (x \cdot y) - \sum x \sum y}{N \sum x^2 - (\sum x)^2}$$

Once you have the slope $m$, the $10\% \rightarrow 90\%$ fall time is:
$$\text{Fall Time} = \ln(9) \cdot \frac{1}{\lambda} \approx 2.1972245 \times \left(-\frac{1}{m}\right)$$

---

## 5. Self-Test & Verification Check

Create a temporary test script `test_module1.py` and run it:

```python
from core.parser.trace_parser import TraceParser

parser = TraceParser()
raw_stream = """---BEGIN TRACE DATA---
Sample_Index,Time_us,Voltage_V
0,0.0,2.5000
1,4.0,2.1200
2,8.0,1.8000
3,12.0,1.5200
4,16.0,1.2900
5,20.0,1.0900
6,24.0,0.9200
7,28.0,0.7800
8,32.0,0.6600
9,36.0,0.5600
10,40.0,0.4700
---END TRACE DATA---
"""

bursts = parser.feed(raw_stream)
assert len(bursts) == 1, "Failed: Should parse exactly 1 burst"
assert round(bursts[0].peak_voltage, 2) == 2.50, "Failed: Peak voltage incorrect"
assert bursts[0].fall_time_us > 0, "Failed: Fall time regression calculation failed"

print("✅ Module 1 Self-Test PASSED!")
```

---

## 📖 Reference Implementation

<details>
<summary>Click to view reference implementation for models/telemetry.py</summary>

```python
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List

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

    def to_dict(self):
        return {
            'burst_id': self.burst_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'trace_points': [[p.sample_index, p.time_us, p.voltage] for p in self.trace_points],
            'peak_voltage': self.peak_voltage,
            'fall_time_us': self.fall_time_us,
            'avg_fall_time_us': self.avg_fall_time_us,
            'channel': self.channel
        }

    @classmethod
    def from_dict(cls, data):
        trace_points = [TracePoint(*p) for p in data.get('trace_points', [])]
        timestamp = data['timestamp']
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                pass

        return cls(
            burst_id=data['burst_id'],
            timestamp=timestamp,
            trace_points=trace_points,
            peak_voltage=data['peak_voltage'],
            fall_time_us=data['fall_time_us'],
            avg_fall_time_us=data['avg_fall_time_us'],
            channel=data.get('channel', 0)
        )

    def trace_to_json(self) -> str:
        return json.dumps([[p.sample_index, p.time_us, p.voltage] for p in self.trace_points])

    @classmethod
    def trace_from_json(cls, json_str: str) -> List[TracePoint]:
        data = json.loads(json_str)
        return [TracePoint(*p) for p in data]
```
</details>

<details>
<summary>Click to view reference implementation for core/parser/trace_parser.py</summary>

```python
import math
from datetime import datetime
from typing import List
from models.telemetry import TracePoint, TraceBurst

class TraceParser:
    MAX_LINE_BUFFER = 100000
    
    def __init__(self):
        self._line_buffer = ""
        self._state = "idle"
        self._metrics = {}
        self._burst_id_counter = 1
        self._current_points = []
        self._fall_time_history = []
        
    def feed(self, raw_data: str) -> List[TraceBurst]:
        self._line_buffer += raw_data
        
        if len(self._line_buffer) > self.MAX_LINE_BUFFER:
            self._line_buffer = ""
        
        lines = self._line_buffer.split('\n')
        self._line_buffer = lines.pop()
        
        completed_bursts = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line == "---BEGIN TRACE DATA---":
                self._state = "in_frame"
                self._current_points.clear()
                self._metrics.clear()
                continue
                
            if line == "Sample_Index,Time_us,Voltage_V":
                continue
                
            if line == "---END TRACE DATA---":
                self._state = "idle"
                if self._current_points:
                    if "peak_voltage" not in self._metrics:
                        self._metrics["peak_voltage"] = max((p.voltage for p in self._current_points), default=0.0)
                        
                    if "fall_time_us" not in self._metrics:
                        sum_x, sum_y, sum_xy, sum_x2, n_points = 0.0, 0.0, 0.0, 0.0, 0
                        for p in self._current_points:
                            if p.voltage > 0.05:
                                t = p.time_us
                                ln_v = math.log(p.voltage)
                                sum_x += t
                                sum_y += ln_v
                                sum_xy += t * ln_v
                                sum_x2 += t * t
                                n_points += 1
                                
                        if n_points > 10:
                            denominator = (n_points * sum_x2) - (sum_x * sum_x)
                            if abs(denominator) > 1e-4:
                                slope = ((n_points * sum_xy) - (sum_x * sum_y)) / denominator
                                if slope < 0:
                                    self._metrics["fall_time_us"] = 2.1972245 * (-1.0 / slope)
                                    
                    fall_time = self._metrics.get("fall_time_us", 0.0)
                    if fall_time > 0:
                        self._fall_time_history.append(fall_time)
                        if len(self._fall_time_history) > 10:
                            self._fall_time_history.pop(0)
                        self._metrics["avg_fall_time_us"] = sum(self._fall_time_history) / len(self._fall_time_history)

                    burst = self._create_burst()
                    if burst:
                        completed_bursts.append(burst)
                        self._reset_burst_state()
                continue
                
            elif self._state == "in_frame":
                parts = line.split(',')
                if len(parts) == 3:
                    try:
                        idx = int(parts[0])
                        time_us = float(parts[1])
                        volts = float(parts[2])
                        self._current_points.append(TracePoint(idx, time_us, volts))
                    except ValueError:
                        pass
        
        return completed_bursts

    def _create_burst(self) -> TraceBurst:
        if not self._current_points:
            return None
            
        burst = TraceBurst(
            burst_id=self._burst_id_counter,
            timestamp=datetime.now(),
            trace_points=list(self._current_points),
            peak_voltage=self._metrics.get("peak_voltage", 0.0),
            fall_time_us=self._metrics.get("fall_time_us", 0.0),
            avg_fall_time_us=self._metrics.get("avg_fall_time_us", 0.0),
            channel=0
        )
        self._burst_id_counter += 1
        return burst
        
    def _reset_burst_state(self):
        self._current_points.clear()
        self._metrics.clear()
        self._state = "idle"

    def reset(self):
        self._line_buffer = ""
        self._current_points.clear()
        self._metrics.clear()
        self._state = "idle"
```
</details>
