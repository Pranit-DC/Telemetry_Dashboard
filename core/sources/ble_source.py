import asyncio
import threading
from queue import Queue
try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None
from .base import DataSource
from core.parser.trace_parser import TraceParser

class BLESource(DataSource):
    """Data source for acquiring telemetry over BLE (Bluetooth Low Energy)."""
    
    SERVICE_UUID = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
    TX_CHAR_UUID = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'
    RX_CHAR_UUID = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
    
    def __init__(self, burst_queue: Queue, device_name='GIGA_WORKSTATION', timeout=15):
        super().__init__(burst_queue)
        self.device_name = device_name
        self.timeout = timeout
        self.parser = TraceParser()
        self._client = None
        self._loop = None
        self._thread = None
        self._connected_event = threading.Event()
        
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
            self._set_state('acquiring')
            asyncio.run_coroutine_threadsafe(self._start_async(), self._loop)
            
    async def _start_async(self):
        try:
            await self._client.start_notify(self.TX_CHAR_UUID, self._notification_handler)
            await self._client.write_gatt_char(self.RX_CHAR_UUID, b'START\n')
        except Exception as e:
            self._set_state('error')
            print(f"BLE start error: {e}")
            
    def stop(self) -> None:
        if self._state == 'acquiring' and self._loop:
            asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            self._set_state('connected')
            
    async def _stop_async(self):
        try:
            await self._client.write_gatt_char(self.RX_CHAR_UUID, b'STOP\n')
            await self._client.stop_notify(self.TX_CHAR_UUID)
        except Exception as e:
            print(f"BLE stop error: {e}")
            
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
        if self._loop and self._client and self._client.is_connected:
            asyncio.run_coroutine_threadsafe(
                self._client.write_gatt_char(self.RX_CHAR_UUID, f"{command}\n".encode('utf-8')),
                self._loop
            )
            
    @property
    def source_type(self) -> str:
        return 'ble'
        
    def _notification_handler(self, sender, data: bytearray):
        try:
            raw_str = data.decode('utf-8')
            bursts = self.parser.feed(raw_str)
            for burst in bursts:
                self.burst_queue.put(burst)
        except Exception as e:
            print(f"BLE notify error: {e}")
