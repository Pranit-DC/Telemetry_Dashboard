# Module 4: Concurrency Architecture & Acquisition Service

Welcome to Module 4! In this module, you will build the central controller of the backend (`core/services/acquisition.py`). You will learn how to safely bridge multi-threaded hardware data sources with single-threaded GUI widgets using Python's `queue.Queue`.

---

## 🎯 Learning Objectives
By the end of this module, you will understand:
- **Thread Safety in GUI Development:** Why calling Tkinter functions directly from background threads causes fatal crashes.
- **Producer-Consumer Pattern:** How data sources (Producers) push into `queue.Queue()`, and the GUI (Consumer) safely polls it.
- **Service Orchestration:** How `AcquisitionService` manages the lifecycle of data sources, database sessions, and logger calls in one place.

---

## 1. Problem Statement & Design Rationale

### Why do we need `queue.Queue`?
Tkinter is single-threaded. If a background serial thread tries to update a Matplotlib plot directly, one of two things will happen:
1. Tkinter will raise `TclError: main thread is not in main loop`.
2. Memory will corrupt due to race conditions.

### The Solution:
```
[ Background Thread ] ──> ( burst_queue.put ) ──> [ queue.Queue ]
                                                        │
                                                        ▼ (Non-blocking polling every 100ms)
                                            [ app._start_polling() on Main UI Thread ]
```

By putting `TraceBurst` objects into `queue.Queue()`, thread-safety is guaranteed automatically by Python's internal queue locking!

---

## 2. Step 1: Designing `AcquisitionService` (`core/services/acquisition.py`)

### Responsibilities:
- **Source Management:** Instantiates and switches between `SimulatorSource`, `SerialSource`, and `BLESource` dynamically.
- **Session Control:** Handles `start_session()` (generates a unique `RUN_YYYYMMDD_HHMMSS` ID, registers it with `DatabaseManager`) and `stop_session()`.
- **Queue Polling:** Exposes `poll_queue()` so the GUI can fetch pending bursts safely on the main thread.
- **Data Dispatching:** Routes bursts to `DatabaseManager.insert_burst()` and `RollingCSVLogger.log_burst()`.

---

## 3. Step 2: Implementing `poll_queue()`

### 💡 Mentor's Guidance on Non-Blocking Queue Polling
When the GUI calls `poll_queue()`, it must **never block or wait**. If `queue.get()` is called with blocking enabled and the queue is empty, the GUI will freeze!

Always use `get_nowait()` inside a `try...except queue.Empty` block:

```python
def poll_queue(self):
    bursts = []
    while not self._burst_queue.empty():
        try:
            burst = self._burst_queue.get_nowait()
            bursts.append(burst)
            self._process_burst(burst)
        except Exception:
            break
    return bursts
```

---

## 4. Self-Test & Verification Check

Create `test_module4.py`:

```python
import time
from config import AppConfig
from core.database.manager import DatabaseManager
from core.logging import RollingCSVLogger
from core.services.acquisition import AcquisitionService

config = AppConfig()
db = DatabaseManager(config)
logger = RollingCSVLogger(config)
service = AcquisitionService(db, logger, config)

# 1. Set source to simulator
service.set_source('simulator')
service.connect()

# 2. Start session
service.start_session(session_name="Test Queue Run")
time.sleep(1.0)  # Allow background simulator thread to produce bursts

# 3. Poll queue from main thread
bursts = service.poll_queue()
assert len(bursts) >= 3, f"Failed: Expected bursts in queue, got {len(bursts)}"

# 4. Stop & Cleanup
service.stop_session()
service.cleanup()

print(f"✅ Module 4 Self-Test PASSED! Successfully polled {len(bursts)} bursts from queue.")
```

---

## 📖 Reference Implementation

<details>
<summary>Click to view reference implementation for core/services/acquisition.py</summary>

```python
from queue import Queue
from datetime import datetime
from core.database.manager import DatabaseManager
from core.logging.csv_logger import RollingCSVLogger
from config import AppConfig

class AcquisitionService:
    def __init__(self, db: DatabaseManager, csv_logger: RollingCSVLogger, config: AppConfig):
        self.db = db
        self.csv_logger = csv_logger
        self.config = config
        self._burst_queue = Queue()
        self._source = None
        self._session_id = None
        self._burst_count = 0
        self._on_burst_callback = None
        self._on_state_callback = None
    
    def set_source(self, source_type: str):
        if self._source:
            self.stop_session()
            self._source.disconnect()
        
        if source_type == 'simulator':
            from core.sources import SimulatorSource
            self._source = SimulatorSource(self._burst_queue)
        elif source_type == 'serial':
            from core.sources import SerialSource
            self._source = SerialSource(
                self._burst_queue,
                port=self.config.com_port,
                baud_rate=self.config.baud_rate
            )
        elif source_type == 'ble':
            from core.sources import BLESource
            self._source = BLESource(
                self._burst_queue,
                device_name=self.config.ble_device_name,
                timeout=self.config.ble_timeout
            )
        
        if self._source:
            self._source.set_state_callback(self._on_source_state_changed)
    
    def connect(self):
        if self._source:
            self._source.connect()
    
    def start_session(self, session_name=None):
        self._session_id = f'RUN_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        self._burst_count = 0
        self.db.create_session(
            self._session_id,
            source_type=self._source.source_type if self._source else 'unknown',
            name=session_name
        )
        if self._source:
            self._source.start()
    
    def stop_session(self):
        if self._source:
            self._source.stop()
        if self._session_id:
            self.db.end_session(self._session_id, status='completed')
        session_id = self._session_id
        self._session_id = None
        return session_id
    
    def poll_queue(self):
        bursts = []
        while not self._burst_queue.empty():
            try:
                burst = self._burst_queue.get_nowait()
                bursts.append(burst)
                self._process_burst(burst)
            except Exception:
                break
        return bursts
    
    def _process_burst(self, burst):
        self._burst_count += 1
        if self._session_id:
            self.db.insert_burst(self._session_id, burst)
            self.csv_logger.log_burst(burst)
        if self._on_burst_callback:
            self._on_burst_callback(burst)
    
    def _on_source_state_changed(self, new_state):
        if self._on_state_callback:
            self._on_state_callback(new_state)
    
    def set_on_burst(self, callback):
        self._on_burst_callback = callback
    
    def set_on_state_change(self, callback):
        self._on_state_callback = callback
    
    @property
    def session_id(self):
        return self._session_id
    
    @property
    def burst_count(self):
        return self._burst_count
    
    @property
    def source(self):
        return self._source
    
    @property
    def is_acquiring(self):
        return self._source is not None and self._source.state == 'acquiring'
    
    def cleanup(self):
        if self._source:
            try:
                self._source.stop()
                self._source.disconnect()
            except Exception:
                pass
        if self.csv_logger:
            self.csv_logger.close()
        if self.db:
            self.db.close()
```
</details>
