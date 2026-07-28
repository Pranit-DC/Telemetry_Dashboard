from core.parser.trace_parser import TraceParser


def frame(points, header=True):
    lines = ["<<BEG>>"]
    if header:
        lines.append("Sample_Index,Time_us,Voltage_V")
    for idx, t, v in points:
        lines.append(f"{idx},{t},{v}")
    lines.append("<<END>>")
    return "\n".join(lines) + "\n"


class TestTraceParser:

    def test_single_complete_frame_produces_one_burst(self):
        parser = TraceParser()
        pts = [(i, i * 4.0, 2.0 - i * 0.01) for i in range(20)]
        bursts = parser.feed(frame(pts))
        assert len(bursts) == 1
        assert len(bursts[0].trace_points) == 20
        assert bursts[0].burst_id == 1

    def test_burst_ids_increment_across_frames(self):
        parser = TraceParser()
        pts = [(0, 0.0, 1.0)]
        b1 = parser.feed(frame(pts))
        b2 = parser.feed(frame(pts))
        assert b1[0].burst_id == 1
        assert b2[0].burst_id == 2

    def test_data_split_across_multiple_feed_calls(self):
        parser = TraceParser()
        pts = [(i, i * 4.0, 2.0 - i * 0.01) for i in range(20)]
        raw = frame(pts)
        mid = len(raw) // 2
        first = parser.feed(raw[:mid])
        assert first == []  # nothing completed yet, buffered mid-line/mid-frame
        second = parser.feed(raw[mid:])
        assert len(second) == 1
        assert len(second[0].trace_points) == 20

    def test_malformed_point_line_is_skipped_not_crashing(self):
        parser = TraceParser()
        raw = "<<BEG>>\nSample_Index,Time_us,Voltage_V\n0,0.0,1.0\nGARBAGE,LINE\n1,4.0,0.9\n<<END>>\n"
        bursts = parser.feed(raw)
        assert len(bursts) == 1
        assert len(bursts[0].trace_points) == 2  # garbage line dropped, not crashed

    def test_empty_frame_produces_no_burst(self):
        parser = TraceParser()
        raw = "<<BEG>>\nSample_Index,Time_us,Voltage_V\n<<END>>\n"
        bursts = parser.feed(raw)
        assert bursts == []

    def test_peak_voltage_defaults_to_max_when_not_transmitted(self):
        parser = TraceParser()
        pts = [(0, 0.0, 0.5), (1, 4.0, 1.8), (2, 8.0, 0.3)]
        bursts = parser.feed(frame(pts))
        assert bursts[0].peak_voltage == 1.8

    def test_line_buffer_safety_cap_resets_on_corrupt_stream(self):
        parser = TraceParser()
        # No newlines at all -> buffer just keeps growing until the cap trips
        garbage = "x" * (parser.MAX_LINE_BUFFER + 10)
        bursts = parser.feed(garbage)
        assert bursts == []
        assert parser._line_buffer == ""

    def test_reset_clears_state_but_keeps_burst_counter(self):
        parser = TraceParser()
        parser.feed(frame([(0, 0.0, 1.0)]))
        assert parser._burst_id_counter == 2
        parser.reset()
        assert parser._line_buffer == ""
        assert parser._state == "idle"
        assert parser._burst_id_counter == 2  # counter is intentionally preserved