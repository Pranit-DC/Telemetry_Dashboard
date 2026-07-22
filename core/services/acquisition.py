from queue import Queue
from core.database.manager import DatabaseManager
from core.logging.csv_logger import RollingCSVLogger
from config import AppConfig

class AcquisitionService:
    """Orchestrates the acquisition pipeline.
    
    Sits between data sources and the GUI. Manages:
    - Active data source lifecycle
    - Session creation and finalization
    - Data routing to storage (DB + CSV)
    - Queue polling and burst dispatching
    """
    
    def __init__(self, db: DatabaseManager, csv_logger: RollingCSVLogger, config: AppConfig):
        self.db = db
        self.csv_logger = csv_logger
        self.config = config
        self._burst_queue = Queue()
        self._source = None
        self._session_id = None
        self._burst_count = 0
        self._on_burst_callback = None  # GUI callback for new burst
        self._on_state_callback = None  # GUI callback for state changes
    
    def set_source(self, source_type: str):
        """Create and set the active data source by type name."""
        # Disconnect existing source if any
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
        """Create a new session and start acquisition."""
        from datetime import datetime
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
        """Stop acquisition and finalize the session."""
        if self._source:
            self._source.stop()
        if self._session_id:
            self.db.end_session(self._session_id, status='completed')
        session_id = self._session_id
        self._session_id = None
        return session_id
    
    def poll_queue(self):
        """Called by the GUI timer. Process all pending bursts."""
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
        """Route a burst to storage and notify GUI."""
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
        """Release all resources."""
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
