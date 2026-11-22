import asyncio
import threading
from datetime import datetime
from queue import Queue
try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None
from .base import DataSource
from models.telemetry import TracePoint, TraceBurst
from core.analysis.fall_time import FallTimeCalculator, US_PER_SAMPLE
from core.parser.ble_binary_parser import (
    BLEBurstAssembler,
    build_start_command,
    build_stop_command,
    build_burst_ack_command,
    build_resend_commands,
    build_set_local_mode_command,
    build_set_usb_mode_command,
    build_set_ble_mode_command,
)

# Wait this long after sending a RESEND round before re-checking completeness.
RESEND_WAIT_SECONDS = 0.4


class BLESource(DataSource):
    """Handles telemetry acquisition over Bluetooth Low Energy.    
    Receives binary packets, requests missing samples, and converts
    completed bursts into trace data for further processing.
    """

    SERVICE_UUID = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
    TX_CHAR_UUID = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'   # Notify: Arduino -> PC
    RX_CHAR_UUID = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'   # Write:  PC -> Arduino

    def __init__(self, burst_queue: Queue, device_name='GIGA_WORKSTATION', timeout=15):
        super().__init__(burst_queue)
        self.device_name = device_name
        self.timeout = timeout

        self.assembler = BLEBurstAssembler()
        self.fall_time_calc = FallTimeCalculator()
        self._burst_id_counter = 1

        self._client = None
        self._loop = None
        self._thread = None
        self._connected_event = threading.Event()

    # CONNECT
    def connect(self) -> None:
        self._set_state('connecting')
        self._thread = threading.Thread(target=self._run_asyncio_loop, daemon=True)
        self._thread.start()

    def _run_asyncio_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_async())
            if self._client and self._client.is_connected:
                self._loop.run_forever()
        except Exception as e:
            self._set_state('error')
            print(f"BLE loop error: {e}")
        finally:
            self._loop.close()

    async def _connect_async(self):
        try:
            if BleakScanner is None or BleakClient is None:
                raise ImportError("bleak is not installed")
            devices = await BleakScanner.discover(timeout=self.timeout)
            target_device = next((d for d in devices if d.name == self.device_name), None)

            if not target_device:
                raise Exception(f"Device {self.device_name} not found")

            self._client = BleakClient(target_device)
            await self._client.connect()
            self._set_state('connected')
            self._connected_event.set()
        except Exception as e:
            self._set_state('error')
            print(f"BLE connect error: {e}")

    def start(self) -> None:
        if self._state == 'connected' and self._loop:
            self.assembler.start_new_burst()
            self._set_state('acquiring')
            asyncio.run_coroutine_threadsafe(self._start_async(), self._loop)

    async def _start_async(self):
        try:
            await self._client.start_notify(
                self.TX_CHAR_UUID,
                self._notification_handler
            )
            # Tell firmware to switch to BLE mode
            await self._client.write_gatt_char(
                self.RX_CHAR_UUID,
                build_set_ble_mode_command(),
                response=True
            )
            # Start acquisition
            await self._client.write_gatt_char(
                self.RX_CHAR_UUID,
                build_start_command(),
                response=True
            )
        except Exception as e:
            self._set_state("error")
            print(f"BLE start error: {e}")

    def stop(self) -> None:
        if self._state == 'acquiring' and self._loop:
            asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            self._set_state('connected')

    async def _stop_async(self):
        try:
            await self._client.write_gatt_char(self.RX_CHAR_UUID, build_stop_command(), response=True)
            await self._client.stop_notify(self.TX_CHAR_UUID)
        except Exception as e:
            print(f"BLE stop error: {e}")

    # TEARDOWN
    def disconnect(self) -> None:
        if self._loop:
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._disconnect_async(), self._loop)
            else:
                self._set_state('disconnected')

    async def _disconnect_async(self):
        try:
            if self._client and self._client.is_connected:
                await self._client.disconnect()
        finally:
            self._set_state('disconnected')
            if self._loop:
                self._loop.stop()

    def send_command(self, command: str) -> None:
        """Kept for compatibility with the GUI's generic command hooks.
        Prefer start()/stop() for START/STOP - they use the binary protocol.
        """
        if self._loop and self._client and self._client.is_connected:
            if command == 'START':
                asyncio.run_coroutine_threadsafe(
                    self._client.write_gatt_char(self.RX_CHAR_UUID, build_start_command(), response=True),
                    self._loop
                )
            elif command == 'STOP':
                asyncio.run_coroutine_threadsafe(
                    self._client.write_gatt_char(self.RX_CHAR_UUID, build_stop_command(), response=True),
                    self._loop
                )

    @property
    def source_type(self) -> str:
        return 'ble'

    # PACKET INTAKE
    def _notification_handler(self, sender, data: bytearray):
        try:
            kind, value = self.assembler.feed(bytes(data))
            if kind == 'end':
                self._loop.create_task(self._resolve_burst())
        except Exception as e:
            print(f"BLE notify error: {e}")

    async def _resolve_burst(self):
        """Called once the END marker for a burst has been seen.
        Checks for gaps; if any exist, requests exactly those samples be
        resent (Selective Repeat), waits, and re-checks - up to a bounded
        number of rounds so a dead link can't stall acquisition forever.
        """
        try:
            while not self.assembler.is_complete and self.assembler.can_retry():
                missing = self.assembler.missing_indices
                self.assembler.note_resend_round()
                print(f"[BLE] Burst incomplete, requesting resend of {len(missing)} samples "
                      f"(round {self.assembler._resend_round}): {missing}")
                for cmd in build_resend_commands(missing):
                    await self._client.write_gatt_char(self.RX_CHAR_UUID, cmd, response=True)
                await asyncio.sleep(RESEND_WAIT_SECONDS)

            if self.assembler.is_complete:
                await self._finalize_burst()
            else:
                missing = self.assembler.missing_indices
                print(f"[BLE] Giving up on burst after max retries - "
                      f"{len(missing)} samples permanently lost: {missing}. Burst discarded.")
                # ACK anyway so the Arduino resumes its automated capture loop
                # instead of waiting out the full timeout for nothing.
                await self._client.write_gatt_char(self.RX_CHAR_UUID, build_burst_ack_command(), response=True)
                self.assembler.start_new_burst()
        except Exception as e:
            print(f"BLE resolve_burst error: {e}")

    async def _finalize_burst(self):
        voltages = self.assembler.get_voltages_or_none()
        if voltages is None:
            print("[BLE] finalize_burst called but array is not actually complete - skipping.")
            self.assembler.start_new_burst()
            return

        result = self.fall_time_calc.compute(voltages)
        if result.error:
            print(f"[BLE] Burst {self._burst_id_counter}: regression did not converge "
                  f"({result.error}) - burst still stored with fall_time_us=0.0.")

        trace_points = [
            TracePoint(sample_index=i, time_us=i * US_PER_SAMPLE, voltage=v)
            for i, v in enumerate(voltages)
        ]

        burst = TraceBurst(
            burst_id=self._burst_id_counter,
            timestamp=datetime.now(),
            trace_points=trace_points,
            peak_voltage=result.peak_voltage,
            fall_time_us=result.fall_time_us,
            avg_fall_time_us=result.avg_fall_time_us,
            channel=0,
        )
        self._burst_id_counter += 1
        self.burst_queue.put(burst)

        await self._client.write_gatt_char(self.RX_CHAR_UUID, build_burst_ack_command(), response=True)
        self.assembler.start_new_burst()