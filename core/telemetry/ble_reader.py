# BLE device connection handler using the Bleak library.
# This module is incomplete — it will be used when the real
# Arduino Giga R1 hardware is connected via Bluetooth.
#
# For now, the dashboard uses core/telemetry/simulator.py for fake data.
# When real data is ready, this BLE reader (or a USB serial reader)
# will replace the simulator, following the same start/pause/stop interface.

import asyncio
from bleak import BleakScanner, BleakClient


class DeviceBle():

    def __init__(self):
        self.client = None
        self.uuid_battery_service = '0000180f-0000-1000-8000-00805f9b34fb'
        self.uuid_battery_level_characteristic = '00002a19-0000-1000-8000-00805f9b34fb'

    async def discover(self):
        devices = await BleakScanner.discover(5.0, return_adv=True)
        for device in devices:
            advertisement_data = devices[device][1]
            if advertisement_data.local_name == "Wa":
                if advertisement_data.rssi > -90:
                    self.device = devices[device]
                    return device

    async def connect(self):
        address = await self.discover()
        if address is not None:
            try:
                print("Found device at address: %s" % (address))
                print("Attempting to connect...")
                self.client = BleakClient(address)
                await self.client.connect()
                print("Connected")
            except Exception:
                raise Exception("Failed to connect")
        else:
            raise Exception("Did not find available devices")

    async def disconnect(self):
        try:
            print("Disconnecting...")
            await self.client.disconnect()
            print("Disconnected!")
        except Exception:
            raise Exception("Warning: Failed to disconnect. Check for hanging connection")

    async def read_characteristic(self, uuid):
        try:
            return await self.client.read_gatt_char(uuid)
        except Exception:
            raise Exception("Failed to read characteristic.")
