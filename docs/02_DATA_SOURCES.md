# Module 2: Polymorphic Data Source Abstraction

Welcome to Module 2! In this module, you will build the hardware abstraction layer that allows your application to seamlessly switch between a synthetic simulator, a USB Serial connection, and a Bluetooth Low Energy (BLE) connection without breaking the rest of the codebase.

---

## 🎯 Learning Objectives
By the end of this module, you will understand:
- **Polymorphism & Abstraction:** How object-oriented design allows interchangeable components.
- **Hardware Simulation Strategy:** How to build a realistic simulator that mimics hardware buffer limits and pulse timing.
- **Air-Gapped Resiliency:** How to write `try...except ImportError` fallbacks so missing Linux wheels don't crash your dashboard.
- **Asynchronous Execution in Threads:** How to run `asyncio` loops (like `bleak`) inside Python background threads.

---

## 1. Problem Statement & Design Rationale

### Why do we need a Data Source Abstraction?
In the old code, USB reading logic was coupled directly to GUI callbacks. If serial failed, the app crashed. 

By defining a unified abstract interface `DataSource`, the rest of your system (GUI, Database, Logger) **does not care** where data comes from. Whether it's coming from `SimulatorSource`, `SerialSource`, or `BLESource`, they all expose the exact same methods:
- `connect()`
- `start()`
- `stop()`
- `disconnect()`

---

## 2. Step 1: Defining the Abstract Base Class (`core/sources/base.py`)

### 💡 Mentor's Guidance on Abstract Base Classes (ABC)
Use Python's `abc` module. An `@abstractmethod` enforces a contract: if a subclass forgets to implement `connect()`, Python will raise an error when instantiated.

### Tasks for you:
1. Create `core/sources/base.py`.
2. Define class `DataSource(ABC)`.
3. Accept `burst_queue: Queue` in `__init__()`.
4. Manage internal state transitions (`disconnected`, `connecting`, `connected`, `acquiring`, `error`) and notify listeners via `_set_state()`.

---

## 3. Step 2: Building the Hardware-Accurate Simulator (`core/sources/simulator.py`)

### 💡 Mentor's Guidance on Simulation Strategy
A good simulator shouldn't just send static data. It must accurately reflect real hardware:
- **700 $\rightarrow$ 151 Sampling:** The Arduino GIGA R1 captures 700 samples but only transmits 151 starting at `peakIndex + 40`.
- **Peak Jitter:** Photodiode flashes don't happen at the exact same microsecond every time. Simulate a random `true_peak_index` between 10 and 100.
- **Exponential Decay Formula:** Generate decay points using:
  $$V(i) = V_{\text{peak}} \cdot (0.95)^{0.1 \cdot i} + \mathcal{N}(0, 0.01)$$

### Tasks for you:
1. Create `core/sources/simulator.py` inheriting from `DataSource`.
2. Implement a background thread `_run_loop()` that emits synthetic bursts every 0.25 seconds (4 Hz).
3. Put the generated `TraceBurst` into `self.burst_queue`.

---

## 4. Step 3: USB Serial Source (`core/sources/serial_source.py`)

### 💡 Mentor's Guidance on Air-Gapped Workstation Safety
When working at BARC, you might boot Python on a machine that doesn't have `pyserial` installed yet. **Do not let your app crash on startup!**

Wrap imports like this:
```python
try:
    import serial
except ImportError:
    serial = None
```
Inside `connect()`, check `if serial is None:` and set state to `'error'` gracefully!

### Tasks for you:
1. Create `core/sources/serial_source.py`.
2. Implement a background `_read_loop()` thread that calls `self._serial.readline()`.
3. Feed incoming lines into `TraceParser` (from Module 1) and put resulting bursts into `self.burst_queue`.

---

## 5. Step 4: Bluetooth BLE Source (`core/sources/ble_source.py`)

### 💡 Mentor's Guidance on Asyncio + Threads
`bleak` (the standard Python BLE library) uses `asyncio`. But Tkinter uses a standard synchronous event loop.

To bridge these two worlds:
1. Spawn a background `threading.Thread`.
2. Inside the thread, create a new `asyncio` event loop:
   ```python
   self._loop = asyncio.new_event_loop()
   asyncio.set_event_loop(self._loop)
   self._loop.run_until_complete(self._connect_async())
   ```
3. Use `asyncio.run_coroutine_threadsafe()` to schedule commands (like `stop()`) onto that loop from outside the thread!

---

## 6. Self-Test & Verification Check

Create `test_module2.py`:

```python
from queue import Queue
import time
from core.sources import SimulatorSource

burst_queue = Queue()
source = SimulatorSource(burst_queue)

source.connect()
assert source.state == 'connected', "Failed: Should be connected"

source.start()
assert source.state == 'acquiring', "Failed: Should be acquiring"

time.sleep(1.0)
source.stop()

bursts_received = []
while not burst_queue.empty():
    bursts_received.append(burst_queue.get_nowait())

assert len(bursts_received) >= 3, f"Failed: Expected at least 3 bursts, got {len(bursts_received)}"
print(f"✅ Module 2 Self-Test PASSED! Received {len(bursts_received)} simulated bursts.")
```

---

## 📖 Reference Implementation

<details>
<summary>Click to view reference implementation for core/sources/base.py</summary>

```python
from abc import ABC, abstractmethod
from queue import Queue

class DataSource(ABC):
    def __init__(self, burst_queue: Queue):
        self.burst_queue = burst_queue
        self._state = 'disconnected'
        self._state_callback = None
        
    def set_state_callback(self, callback):
        self._state_callback = callback
        
    def _set_state(self, new_state: str):
        self._state = new_state
        if self._state_callback:
            self._state_callback(new_state)
            
    @property
    def state(self) -> str:
        return self._state
        
    @property
    @abstractmethod
    def source_type(self) -> str:
        pass
        
    @abstractmethod
    def connect(self) -> None:
        pass
        
    @abstractmethod
    def disconnect(self) -> None:
        pass
        
    @abstractmethod
    def start(self) -> None:
        pass
        
    @abstractmethod
    def stop(self) -> None:
        pass
```
</details>

<details>
<summary>Click to view reference implementation for core/sources/simulator.py</summary>

```python
import time
import random
import threading
from datetime import datetime
from queue import Queue
from .base import DataSource
from models.telemetry import TracePoint, TraceBurst

class SimulatorSource(DataSource):
    def __init__(self, burst_queue: Queue, burst_interval=0.25):
        super().__init__(burst_queue)
        self.burst_interval = burst_interval
        self._running = False
        self._thread = None
        self._burst_id_counter = 1
        
    def connect(self) -> None:
        self._set_state('connected')
        
    def start(self) -> None:
        if self._state == 'connected':
            self._running = True
            self._set_state('acquiring')
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            
    def stop(self) -> None:
        self._running = False
        if self._state == 'acquiring':
            self._set_state('connected')
            
    def disconnect(self) -> None:
        self.stop()
        self._set_state('disconnected')
        
    @property
    def source_type(self) -> str:
        return 'simulator'
        
    def _run_loop(self):
        avg_fall_sum = 0
        bursts_emitted = 0
        
        while self._running:
            trace_points = []
            peak = random.uniform(1.5, 3.0)
            
            true_peak_index = random.randint(10, 100)
            reg_start_idx = true_peak_index + 40
            reg_end_idx = true_peak_index + 190
            
            for i in range(reg_start_idx, reg_end_idx + 1):
                time_us = (i - reg_start_idx) * 4.0
                voltage = peak * (0.95 ** ((i - reg_start_idx) * 0.1)) + random.gauss(0, 0.01)
                trace_points.append(TracePoint(sample_index=i, time_us=time_us, voltage=voltage))
                
            peak_voltage = max(p.voltage for p in trace_points)
            fall_time_us = random.uniform(100.0, 300.0)
            
            avg_fall_sum += fall_time_us
            bursts_emitted += 1
            avg_fall_time_us = avg_fall_sum / bursts_emitted
            
            burst = TraceBurst(
                burst_id=self._burst_id_counter,
                timestamp=datetime.now(),
                trace_points=trace_points,
                peak_voltage=peak_voltage,
                fall_time_us=fall_time_us,
                avg_fall_time_us=avg_fall_time_us,
                channel=0
            )
            self._burst_id_counter += 1
            
            self.burst_queue.put(burst)
            time.sleep(self.burst_interval)
```
</details>
