from abc import ABC, abstractmethod
from queue import Queue

class DataSource(ABC):
    """Abstract base class for all telemetry data sources.
    
    All data sources put TraceBurst objects into a shared queue.
    The AcquisitionService polls this queue from the main thread.
    """
    
    def __init__(self, burst_queue: Queue):
        self.burst_queue = burst_queue
        self._state = 'disconnected'  # disconnected, connecting, connected, acquiring, error
        self._state_callback = None  # Called when state changes
    
    @property
    def state(self) -> str:
        return self._state
    
    def _set_state(self, new_state: str):
        self._state = new_state
        if self._state_callback:
            self._state_callback(new_state)
    
    def set_state_callback(self, callback):
        """Register a callback for state changes: callback(new_state: str)"""
        self._state_callback = callback
    
    @abstractmethod
    def connect(self) -> None:
        pass
    
    @abstractmethod
    def start(self) -> None:
        pass
    
    @abstractmethod
    def stop(self) -> None:
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def send_command(self, command: str) -> None:
        pass
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        pass
