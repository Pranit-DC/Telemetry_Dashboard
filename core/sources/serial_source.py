import threading
try:
    import serial
except ImportError:
    serial = None
from queue import Queue
from .base import DataSource
from core.parser.trace_parser import TraceParser

class SerialSource(DataSource):
    """Data source for acquiring telemetry over a serial port."""
    
    def __init__(self, burst_queue: Queue, port='COM15', baud_rate=115200):
        super().__init__(burst_queue)
        self.port = port
        self.baud_rate = baud_rate
        self.parser = TraceParser()
        self._serial = None
        self._running = False
        self._thread = None
        
    def connect(self) -> None:
        try:
            if serial is None:
                raise ImportError("pyserial is not installed")
            self._serial = serial.Serial(self.port, self.baud_rate, timeout=1)
            self._set_state('connected')
        except Exception as e:
            self._set_state('error')
            print(f"Serial connect error: {e}")
            
    def start(self) -> None:
        if self._state == 'connected' and self._serial:
            self.send_command('START')
            self._running = True
            self._set_state('acquiring')
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            
    def stop(self) -> None:
        if self._running:
            self.send_command('STOP')
            self._running = False
        if self._state == 'acquiring':
            self._set_state('connected')
            
    def disconnect(self) -> None:
        self.stop()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._set_state('disconnected')
        
    def send_command(self, command: str) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(f"{command}\n".encode('utf-8'))
            except Exception as e:
                print(f"Serial send error: {e}")
                
    @property
    def source_type(self) -> str:
        return 'serial'
        
    def _read_loop(self):
        """Background thread to read lines from serial port."""
        while self._running and self._serial and self._serial.is_open:
            try:
                line = self._serial.readline().decode('utf-8', errors='ignore')
                if line:
                    bursts = self.parser.feed(line)
                    for burst in bursts:
                        self.burst_queue.put(burst)
            except Exception as e:
                self._set_state('error')
                self._running = False
                print(f"Serial read error: {e}")
                break
