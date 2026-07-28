from datetime import datetime
from models.telemetry import TracePoint, TraceBurst


def sample_burst():
    return TraceBurst(
        burst_id=7,
        timestamp=datetime(2026, 7, 29, 12, 0, 0),
        trace_points=[TracePoint(0, 0.0, 1.0), TracePoint(1, 4.0, 0.95)],
        peak_voltage=1.0,
        fall_time_us=123.45,
        avg_fall_time_us=120.0,
        channel=2,
    )


class TestTraceBurstSerialization:

    def test_to_dict_round_trip(self):
        burst = sample_burst()
        d = burst.to_dict()
        restored = TraceBurst.from_dict(d)
        assert restored.burst_id == burst.burst_id
        assert restored.channel == burst.channel
        assert restored.peak_voltage == burst.peak_voltage
        assert restored.trace_points == burst.trace_points
        assert restored.timestamp == burst.timestamp

    def test_from_dict_handles_string_timestamp(self):
        d = sample_burst().to_dict()
        assert isinstance(d["timestamp"], str)
        restored = TraceBurst.from_dict(d)
        assert restored.timestamp == datetime(2026, 7, 29, 12, 0, 0)

    def test_from_dict_defaults_missing_channel_to_zero(self):
        d = sample_burst().to_dict()
        del d["channel"]
        restored = TraceBurst.from_dict(d)
        assert restored.channel == 0

    def test_trace_to_json_and_back(self):
        burst = sample_burst()
        js = burst.trace_to_json()
        points = TraceBurst.trace_from_json(js)
        assert points == burst.trace_points