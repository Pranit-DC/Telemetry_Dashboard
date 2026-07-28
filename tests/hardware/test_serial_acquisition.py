"""
Tier 2: full acquisition through the ACTUAL production code path
(core.sources.serial_source.SerialSource -> core.parser.trace_parser),
against the real Arduino GIGA R1 and the real photodiode on the analog
input.

This requires the photodiode to actually be triggered (a light pulse hitting
it) at some point during the test, since a burst only exists once the board
detects a real signal. If nothing triggers it in time, the test SKIPS with a
clear message rather than failing -- that is a "no light pulse happened"
result, not a dashboard defect.

If a burst IS received, the assertions are deliberately structural (sample
count, valid voltage range, index ordering) rather than exact values, since
exact voltages/fall-times depend on your specific optical setup and will
legitimately vary run to run.
"""
import time
import pytest
from queue import Queue, Empty
from core.sources.serial_source import SerialSource

BURST_WAIT_SECONDS = 30  # generous: give yourself time to trigger the photodiode
TARGET_SAMPLES = 700


@pytest.fixture
def connected_source(require_arduino, com_port, baud_rate):
    """
    Uses the real SerialSource class (the exact class the dashboard uses),
    """
    # require_arduino already proved the port opens; close it so SerialSource
    # can open its own handle to the same port without a "port busy" clash.
    require_arduino.close()

    q = Queue()
    source = SerialSource(q, port=com_port, baud_rate=baud_rate)
    source.connect()
    if source.state != "connected":
        pytest.skip(f"SerialSource could not connect on {com_port}")

    yield source, q

    source.disconnect()


class TestSerialAcquisition:

    def test_source_reaches_acquiring_state(self, connected_source):
        source, _ = connected_source
        source.start()
        assert source.state == "acquiring"
        source.stop()

    def test_receives_a_structurally_valid_burst(self, connected_source):
        source, q = connected_source
        source.start()

        burst = None
        deadline = time.time() + BURST_WAIT_SECONDS
        while time.time() < deadline:
            try:
                burst = q.get(timeout=1)
                break
            except Empty:
                continue

        source.stop()

        if burst is None:
            pytest.skip(
                f"No burst received within {BURST_WAIT_SECONDS}s -- trigger the "
                "photodiode (pulse the light source) during the test window "
                "for this to actually validate a capture."
            )

        # Structural checks only -- these should hold for ANY valid capture,
        # regardless of the specific optical signal on the day.
        assert len(burst.trace_points) == TARGET_SAMPLES

        indices = [p.sample_index for p in burst.trace_points]
        assert indices == list(range(TARGET_SAMPLES))  # sequential, no gaps

        voltages = [p.voltage for p in burst.trace_points]
        # GIGA ADC reference is 3.3V; allow a small margin for reference/noise.
        assert all(-0.1 <= v <= 3.5 for v in voltages), \
            "some voltage samples fell outside the plausible ADC range"

        times = [p.time_us for p in burst.trace_points]
        assert times == sorted(times)  # time is non-decreasing across the burst

        assert burst.peak_voltage > 0