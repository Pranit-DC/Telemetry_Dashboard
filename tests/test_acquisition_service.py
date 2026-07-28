import csv
import time
import pytest
from types import SimpleNamespace
from core.database.manager import DatabaseManager
from core.logging.csv_logger import RollingCSVLogger
from core.services.acquisition import AcquisitionService


@pytest.fixture
def service(tmp_path):
    db_dir = tmp_path / "db"
    logs_dir = tmp_path / "logs"
    config = SimpleNamespace(
        sqlite_database_directory=str(db_dir),
        system_logs_directory=str(logs_dir),
        com_port="COM15",
        baud_rate=115200,
        ble_device_name="GIGA_TEST",
        ble_timeout=5,
    )
    # Real DatabaseManager and real RollingCSVLogger -- just pointed at a
    # temp folder instead of the project's actual db/logs directories, so
    # tests don't touch or clutter real data.
    db = DatabaseManager(config=config)
    csv_logger = RollingCSVLogger(config)
    svc = AcquisitionService(db, csv_logger, config)
    yield svc, logs_dir
    svc.cleanup()


class TestAcquisitionService:

    def test_set_source_simulator_creates_source(self, service):
        svc, _ = service
        svc.set_source("simulator")
        assert svc.source is not None
        assert svc.source.source_type == "simulator"

    def test_start_session_creates_a_session_id(self, service):
        svc, _ = service
        svc.set_source("simulator")
        svc.connect()
        svc.start_session(session_name="Test Run")
        assert svc.session_id is not None
        assert svc.session_id.startswith("RUN_")

    def test_burst_count_starts_at_zero(self, service):
        svc, _ = service
        svc.set_source("simulator")
        assert svc.burst_count == 0

    def test_poll_queue_processes_bursts_into_db_and_real_csv_file(self, service):
        svc, logs_dir = service
        svc.set_source("simulator")
        svc.source.burst_interval = 0.05  # speed up for the test
        svc.connect()
        svc.start_session(session_name="Test Run")

        time.sleep(0.3)  # let the simulator generate a couple of bursts
        bursts = svc.poll_queue()

        assert len(bursts) > 0
        assert svc.burst_count == len(bursts)

        # Read back the REAL CSV file the real RollingCSVLogger wrote,
        # instead of trusting an in-memory stand-in.
        svc.csv_logger.close()
        csv_files = list(logs_dir.glob("telemetry_metrics_*.csv"))
        assert len(csv_files) == 1
        with open(csv_files[0], newline="") as f:
            rows = list(csv.reader(f))
        # header row + one row per logged burst
        assert len(rows) - 1 == len(bursts)

    def test_stop_session_ends_session_and_clears_session_id(self, service):
        svc, _ = service
        svc.set_source("simulator")
        svc.connect()
        svc.start_session(session_name="Test Run")
        session_id = svc.stop_session()
        assert session_id is not None
        assert svc.session_id is None

    def test_is_acquiring_reflects_source_state(self, service):
        svc, _ = service
        svc.set_source("simulator")
        assert svc.is_acquiring is False
        svc.connect()
        svc.start_session(session_name="Test Run")
        assert svc.is_acquiring is True
        svc.stop_session()
        assert svc.is_acquiring is False

    def test_on_burst_callback_is_called(self, service):
        svc, _ = service
        received = []
        svc.set_on_burst(lambda burst: received.append(burst))
        svc.set_source("simulator")
        svc.source.burst_interval = 0.05
        svc.connect()
        svc.start_session(session_name="Test Run")

        time.sleep(0.3)
        svc.poll_queue()

        assert len(received) > 0