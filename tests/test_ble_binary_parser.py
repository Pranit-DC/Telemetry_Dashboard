import struct
import pytest
from core.parser.ble_binary_parser import (
    BLEBurstAssembler,
    build_start_command,
    build_stop_command,
    build_burst_ack_command,
    build_resend_commands,
)


def sample_packet(index, time_us, voltage):
    return struct.pack('<BHff', 0x00, index, time_us, voltage)


def end_packet(total):
    return struct.pack('<BH', 0x01, total)


class TestBLEBurstAssembler:
    """
    All pure Python logic -- no Bluetooth adapter or Arduino required, so
    this runs the same on an offline lab machine as anywhere else.
    """

    def test_feed_sample_stores_it(self):
        asm = BLEBurstAssembler(total_samples=10)
        kind, idx = asm.feed(sample_packet(3, 12.0, 1.5))
        assert kind == "sample"
        assert idx == 3

    def test_not_complete_until_all_samples_received(self):
        asm = BLEBurstAssembler(total_samples=3)
        asm.feed(sample_packet(0, 0.0, 1.0))
        asm.feed(sample_packet(1, 4.0, 0.9))
        assert asm.is_complete is False
        asm.feed(sample_packet(2, 8.0, 0.8))
        assert asm.is_complete is True

    def test_missing_indices_reports_gaps(self):
        asm = BLEBurstAssembler(total_samples=5)
        asm.feed(sample_packet(0, 0.0, 1.0))
        asm.feed(sample_packet(2, 8.0, 0.8))
        assert asm.missing_indices == [1, 3, 4]

    def test_get_voltages_or_none_returns_none_when_incomplete(self):
        asm = BLEBurstAssembler(total_samples=3)
        asm.feed(sample_packet(0, 0.0, 1.0))
        assert asm.get_voltages_or_none() is None

    def test_get_voltages_or_none_returns_list_when_complete(self):
        asm = BLEBurstAssembler(total_samples=2)
        asm.feed(sample_packet(0, 0.0, 1.0))
        asm.feed(sample_packet(1, 4.0, 0.9))
        voltages = asm.get_voltages_or_none()
        # values are packed as float32 on the wire, so compare with tolerance
        assert voltages == pytest.approx([1.0, 0.9], abs=1e-6)

    def test_end_packet_sets_ended_flag(self):
        asm = BLEBurstAssembler(total_samples=5)
        kind, total = asm.feed(end_packet(5))
        assert kind == "end"
        assert total == 5
        assert asm.ended is True

    def test_malformed_packet_is_reported_not_raised(self):
        asm = BLEBurstAssembler(total_samples=5)
        kind, value = asm.feed(b"")
        assert kind == "malformed"

    def test_start_new_burst_clears_previous_data(self):
        asm = BLEBurstAssembler(total_samples=2)
        asm.feed(sample_packet(0, 0.0, 1.0))
        asm.feed(sample_packet(1, 4.0, 0.9))
        assert asm.is_complete is True
        asm.start_new_burst()
        assert asm.is_complete is False
        assert asm.missing_indices == [0, 1]

    def test_can_retry_stops_after_max_rounds(self):
        asm = BLEBurstAssembler(total_samples=5)
        for _ in range(5):
            assert asm.can_retry() is True
            asm.note_resend_round()
        assert asm.can_retry() is False


class TestBLECommandBuilders:

    def test_start_stop_ack_are_single_byte_commands(self):
        assert build_start_command() == bytes([0x01])
        assert build_stop_command() == bytes([0x02])
        assert build_burst_ack_command() == bytes([0x04])

    def test_resend_command_chunks_at_eight_indices(self):
        missing = list(range(20))
        commands = build_resend_commands(missing)
        # 20 indices / 8 per packet -> 3 packets (8, 8, 4)
        assert len(commands) == 3
        assert commands[0][1] == 8
        assert commands[2][1] == 4

    def test_resend_command_empty_list_produces_no_packets(self):
        assert build_resend_commands([]) == []