"""
Shared fixtures for hardware-in-the-loop tests.

These tests talk to the REAL Arduino GIGA R1 over the REAL serial port.

How the port is chosen (in order):
  1. --port command-line option:      pytest tests/hardware --port COM7
  2. TELEMETRY_TEST_PORT environment variable
  3. Auto-detect: first COM port whose description mentions "Arduino"
  4. Fall back to the project's configured default (COM15, see config.py)

"""
import os
import pytest

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


def pytest_addoption(parser):
    parser.addoption(
        "--port", action="store", default=None,
        help="COM port the Arduino GIGA is connected to (e.g. COM7)"
    )
    parser.addoption(
        "--baud", action="store", default=115200, type=int,
        help="Baud rate to use for the hardware tests"
    )


def _autodetect_arduino_port():
    if list_ports is None:
        return None
    for p in list_ports.comports():
        desc = f"{p.description} {p.manufacturer or ''}".lower()
        if "arduino" in desc or "giga" in desc:
            return p.device
    return None


@pytest.fixture(scope="session")
def com_port(request):
    port = request.config.getoption("--port")
    if not port:
        port = os.environ.get("TELEMETRY_TEST_PORT")
    if not port:
        port = _autodetect_arduino_port()
    if not port:
        port = "COM15"  # matches config.py's default
    return port


@pytest.fixture(scope="session")
def baud_rate(request):
    return request.config.getoption("--baud")


@pytest.fixture(scope="session")
def require_arduino(com_port, baud_rate):
    """
    Opens the real serial connection once per test session. Skips the whole
    hardware suite (instead of failing) if the port can't be opened at all --
    e.g. board not plugged in, wrong port, or pyserial not installed.
    """
    if serial is None:
        pytest.skip("pyserial is not installed -- run: pip install pyserial")

    try:
        ser = serial.Serial(com_port, baud_rate, timeout=1)
    except Exception as e:
        pytest.skip(f"Could not open {com_port} -- is the Arduino GIGA plugged in? ({e})")

    yield ser

    try:
        ser.close()
    except Exception:
        pass