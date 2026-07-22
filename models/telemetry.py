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
