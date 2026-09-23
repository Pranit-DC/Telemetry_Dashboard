import time
from queue import Queue
from core.sources.simulator import SimulatorSource


class TestSimulatorSource:
    """The simulator needs no hardware and no mocking, so these tests run
    exactly the same in 's offline environment as anywhere else."""

    def test_source_type_is_simulator(self):
        source = SimulatorSource(Queue())
        assert source.source_type == "simulator"

    def test_starts_disconnected(self):
        source = SimulatorSource(Queue())
        assert source.state == "disconnected"

    def test_connect_sets_connected_state(self):
        source = SimulatorSource(Queue())
        source.connect()
        assert source.state == "connected"

    def test_start_moves_to_acquiring_and_produces_a_burst(self):
        q = Queue()
        source = SimulatorSource(q, burst_interval=0.05)
        source.connect()
        source.start()
        assert source.state == "acquiring"

        # give the background thread a moment to generate at least one burst
        time.sleep(0.5)
        source.stop()

        assert not q.empty()
        burst = q.get_nowait()
        assert len(burst.trace_points) == 700  # TARGET_SAMPLES

    def test_stop_returns_to_connected_state(self):
        source = SimulatorSource(Queue(), burst_interval=0.05)
        source.connect()
        source.start()
        time.sleep(0.2)
        source.stop()
        assert source.state == "connected"

    def test_disconnect_sets_disconnected_state(self):
        source = SimulatorSource(Queue(), burst_interval=0.05)
        source.connect()
        source.start()
        time.sleep(0.1)
        source.disconnect()
        assert source.state == "disconnected"

    def test_send_command_does_not_raise(self):
        # Simulator ignores commands, but the call must be safe to make
        # since the GUI calls it the same way for every source type.
        source = SimulatorSource(Queue())
        source.send_command("START")  # should simply do nothing