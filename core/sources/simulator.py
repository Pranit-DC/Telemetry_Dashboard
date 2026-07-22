import time
import random
import threading
from datetime import datetime
from queue import Queue
from .base import DataSource
from models.telemetry import TracePoint, TraceBurst

class SimulatorSource(DataSource):
    """Generates synthetic decay trace bursts for testing purposes."""
    
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
        
    def send_command(self, command: str) -> None:
        # No-op for simulator
        pass
        
    @property
    def source_type(self) -> str:
        return 'simulator'
        
    def _run_loop(self):
        """Background thread loop generating synthetic data."""
        avg_fall_sum = 0
        bursts_emitted = 0
        
        while self._running:
            # Generate synthetic decay trace
            trace_points = []
            peak = random.uniform(1.5, 3.0)
            
            # Simulate the Arduino's behavior: it captures 700 samples but only transmits 151
            # starting at (peakIndex + 40). We simulate a random peak index between 10 and 100.
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
