import pytest
from datetime import datetime
from types import SimpleNamespace
from core.database.manager import DatabaseManager
from models.telemetry import TracePoint, TraceBurst


@pytest.fixture
def db(tmp_path):
    config = SimpleNamespace(sqlite_database_directory=str(tmp_path))
    manager = DatabaseManager(config=config)
    yield manager
    manager.close()


def make_burst(burst_id=1):
    return TraceBurst(
        burst_id=burst_id,
        timestamp=datetime.now(),
        trace_points=[TracePoint(0, 0.0, 1.2), TracePoint(1, 4.0, 1.1)],
        peak_voltage=1.2,
        fall_time_us=50.0,
        avg_fall_time_us=48.0,
        channel=0,
    )


class TestDatabaseManager:

    def test_create_session_appears_in_list(self, db):
        db.create_session("sess-1", "simulator", name="Test Run")
        sessions = db.get_all_sessions()
        assert len(sessions) == 1
        assert sessions[0][0] == "sess-1"

    def test_insert_burst_increments_burst_count(self, db):
        db.create_session("sess-1", "serial")
        db.insert_burst("sess-1", make_burst(1))
        db.insert_burst("sess-1", make_burst(2))
        info = db.get_session_by_id("sess-1")
        assert info["burst_count"] == 2

    def test_get_session_bursts_round_trips_trace_points(self, db):
        db.create_session("sess-1", "ble")
        original = make_burst(1)
        db.insert_burst("sess-1", original)
        bursts = db.get_session_bursts("sess-1")
        assert len(bursts) == 1
        assert bursts[0].peak_voltage == original.peak_voltage
        assert bursts[0].trace_points == original.trace_points

    def test_end_session_sets_status_and_end_time(self, db):
        db.create_session("sess-1", "serial")
        db.end_session("sess-1", status="completed")
        info = db.get_session_by_id("sess-1")
        assert info["status"] == "completed"
        assert info["end_time"] is not None

    def test_rename_session(self, db):
        db.create_session("sess-1", "serial", name="Old Name")
        db.rename_session("sess-1", "New Name")
        info = db.get_session_by_id("sess-1")
        assert info["name"] == "New Name"

    def test_delete_session_cascades_bursts(self, db):
        db.create_session("sess-1", "serial")
        db.insert_burst("sess-1", make_burst(1))
        db.delete_session("sess-1")
        assert db.get_session_by_id("sess-1") is None
        assert db.get_session_bursts("sess-1") == []

    def test_search_term_filters_sessions(self, db):
        db.create_session("sess-1", "serial", name="Photodiode Run")
        db.create_session("sess-2", "serial", name="Calibration")
        results = db.get_all_sessions(search_term="Photodiode")
        assert len(results) == 1
        assert results[0][0] == "sess-1"

    def test_get_session_by_id_missing_returns_none(self, db):
        assert db.get_session_by_id("does-not-exist") is None