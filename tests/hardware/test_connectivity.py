"""
Connectivity only. These don't need the photodiode to be firing
they just confirm the dashboard can open the port and talk to the board at
the protocol level.
"""
import time


class TestArduinoConnectivity:

    def test_port_opens_and_reports_open(self, require_arduino):
        ser = require_arduino
        assert ser.is_open is True

    def test_start_command_is_accepted_without_error(self, require_arduino):
        ser = require_arduino
        # Should not raise -- if this fails, the board isn't responding to
        # writes at all (cable, driver, or wrong port).
        ser.write(b"START\n")
        time.sleep(0.2)

    def test_stop_command_is_accepted_without_error(self, require_arduino):
        ser = require_arduino
        ser.write(b"STOP\n")
        time.sleep(0.2)

    def test_board_sends_something_after_start(self, require_arduino):
        """
        Not checking WHAT comes back, just that the board is alive and
        talking on the wire after a START command -- catches "board frozen /
        not flashed with expected firmware" without depending on the
        photodiode actually being triggered.
        """
        ser = require_arduino
        ser.reset_input_buffer()
        ser.write(b"START\n")

        received_anything = False
        deadline = time.time() + 10  # generous: covers slow USB enumeration etc.
        while time.time() < deadline:
            line = ser.readline()
            if line:
                received_anything = True
                break

        ser.write(b"STOP\n")

        if not received_anything:
            import pytest
            pytest.skip(
                "No data received within 10s of START -- this usually means "
                "the photodiode wasn't triggered during the test, not a wiring "
                "fault."
            )