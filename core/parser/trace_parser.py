import math
from datetime import datetime
from typing import List
from models.telemetry import TracePoint, TraceBurst

class TraceParser:
    """Parses raw streaming data into TraceBurst and TracePoint objects.
    
    Handles incoming raw string data, splits it into lines, detects frame
    boundaries, parses CSV data points, and extracts burst metrics.
    """
    MAX_LINE_BUFFER = 100000  # Safety cap to prevent unbounded memory growth
    
    def __init__(self):
        self._line_buffer = ""
        self._state = "idle"  # idle, in_frame, in_metrics
        self._metrics = {}
        self._burst_id_counter = 1
        self._current_points = []
        self._fall_time_history = []
        
    def feed(self, raw_data: str) -> List[TraceBurst]:
        """Process incoming raw string data and return any completed bursts."""
        self._line_buffer += raw_data
        
        # Safety cap: if buffer grows too large (corrupt data with no newlines), reset it
        if len(self._line_buffer) > self.MAX_LINE_BUFFER:
            self._line_buffer = ""
        
        lines = self._line_buffer.split('\n')
        # The last element is incomplete if it doesn't end with \n
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
                self._state = "idle" # metrics may follow or not
                if self._current_points:
                    # The Arduino firmware doesn't transmit METRICS, so calculate peak manually
                    if "peak_voltage" not in self._metrics:
                        self._metrics["peak_voltage"] = max((p.voltage for p in self._current_points), default=0.0)
                        
                    # Calculate fall_time_us using the exact same linear regression math as the Arduino
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
                                    
                    # Calculate rolling average fall time (last 10 runs)
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
                
            if line == "---METRICS---":
                self._state = "in_metrics"
                continue
                
            if self._state == "in_metrics":
                if "=" in line:
                    key, val = line.split("=", 1)
                    try:
                        self._metrics[key.strip()] = float(val.strip())
                    except ValueError:
                        pass
                else:
                    # End of metrics usually means burst is complete if we hit empty lines or new frame
                    pass
                
                # We can emit burst after metrics if we have enough info
                if "peak_voltage" in self._metrics and "fall_time_us" in self._metrics:
                    burst = self._create_burst()
                    if burst:
                        completed_bursts.append(burst)
                        self._reset_burst_state()
                        
            elif self._state == "in_frame":
                parts = line.split(',')
                if len(parts) == 3:
                    try:
                        idx = int(parts[0])
                        time_us = float(parts[1])
                        volts = float(parts[2])
                        self._current_points.append(TracePoint(idx, time_us, volts))
                    except ValueError:
                        pass # malformed point
        
        # In case metrics don't follow but we finished a frame and now we get a new one or whatever
        # The prompt says: "After metrics line or after END if no metrics follow: emit complete TraceBurst"
        # We handle this by checking if we have parsed points and are back to idle.
        
        return completed_bursts

    def _create_burst(self) -> TraceBurst:
        """Create a TraceBurst from current accumulated state."""
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
        """Reset internal structures after emitting a burst."""
        self._current_points.clear()
        self._metrics.clear()
        self._state = "idle"

    def reset(self):
        """Clear all internal state including line buffer."""
        self._line_buffer = ""
        self._current_points.clear()
        self._metrics.clear()
        self._state = "idle"
        # don't reset counter
