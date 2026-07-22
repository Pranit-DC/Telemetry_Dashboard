# Background telemetry data simulator.
# Generates fake sensor data in a separate thread to test the dashboard.
# When real BLE/USB data is ready, swap this with a real data reader.

import time
import random
import threading
from datetime import datetime

import config
from .adc import simulate_adc_reading, counts_to_voltage

# If any channel reads above this, the sensor is near saturation
SATURATION_VOLTAGE = 3.2


class TelemetrySimulator:
    """Runs a background thread that generates fake telemetry data.

    Mimics a real BLE data stream: produces one packet per interval,
    randomly drops ~1% of packets, writes to DB/CSV, refreshes GUI.
    """

    def __init__(self, time_data, channels_data, all_history,
                 db, csv_logger, schedule_fn, log_fn, refresh_fn,
                 data_lock=None):
        # Shared data lists (owned by the app, we just append to them)
        self.time_data = time_data
        self.channels_data = channels_data
        self.all_history = all_history

        # Lock to prevent GUI thread from reading lists while we write
        self.data_lock = data_lock or threading.Lock()

        # Backend services
        self.db = db
        self.csv_logger = csv_logger

        # UI callbacks (all run on the GUI thread via root.after)
        self.schedule = schedule_fn
        self.log = log_fn
        self.refresh = refresh_fn

        # Session timing state
        self.is_running = False
        self.session_id = ""
        self._start_time = None
        self._pause_offset = 0.0
        self._pause_start = None

        # Packet tracking counters
        self.expected_packets = 0
        self.received_packets = 0
        self._last_autosave_count = 0
        self._frame_idx = 0

        # Sampling rate in Hz (1.0 = one packet per second)
        self.sampling_rate_hz = 700.0

    def start(self, session_id):
        """Begin a new recording session and start the data thread."""
        self.session_id = session_id
        self.is_running = True
        self._start_time = time.time()
        self._pause_offset = 0.0
        self._pause_start = None
        self._frame_idx = 0

        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def resume(self):
        """Continue a paused session, accounting for pause duration."""
        if self._pause_start:
            self._pause_offset += time.time() - self._pause_start
            self._pause_start = None

        self.is_running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def pause(self):
        """Pause the data stream. Timing is preserved for resume."""
        self.is_running = False
        self._pause_start = time.time()

    def stop(self):
        """Fully stop the session and reset all timing state."""
        self.is_running = False
        self._start_time = None
        self._pause_offset = 0.0
        self._pause_start = None

    def _run_loop(self):
        """Main worker loop (runs in background thread).

        Each tick: generate ADC reading → convert to voltage →
        store in lists/DB/CSV → ask GUI to refresh.
        """
        while self.is_running:
            now = time.time()
            if self._start_time is None:
                self._start_time = now
            elapsed = now - self._start_time - self._pause_offset

            self.expected_packets += 1

            # Simulate ~1% packet drop rate (BLE is not 100% reliable)
            if random.random() > 0.01:
                self.received_packets += 1
                rounded_time = round(elapsed, 3)

                # Generate fake ADC data and convert to voltages
                hw_time_ms, adc_counts = simulate_adc_reading(
                    self._frame_idx, sampling_rate_hz=self.sampling_rate_hz
                )
                voltages = {}
                for ch in config.AVAILABLE_CHANNELS:
                    voltages[ch] = counts_to_voltage(adc_counts[ch])

                # Acquire lock before writing to shared lists
                # This prevents the GUI thread from reading half-written data
                with self.data_lock:
                    self.time_data.append(rounded_time)
                    for ch in config.AVAILABLE_CHANNELS:
                        self.channels_data[ch].append(voltages[ch])

                    # History row stores voltages (matches CSV header format)
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.all_history.append([
                        timestamp_str, rounded_time,
                        voltages["Channel 1"],
                        voltages["Channel 2"],
                        voltages["Channel 3"],
                    ])

                # Check saturation (outside lock — DB has its own safety)
                for ch in config.AVAILABLE_CHANNELS:
                    if voltages[ch] >= SATURATION_VOLTAGE:
                        msg = f"ALERT: {ch} near saturation: {voltages[ch]:.2f}V"
                        self.db.log_alarm_event("SATURATION_WARNING", msg)
                        self.schedule(0, lambda m=msg: self.log(f"⚠️ {m}"))

                # Save to database
                self.db.insert_frame(
                    self.session_id, timestamp_str, rounded_time, voltages
                )

                # Log to terminal
                v_str = " | ".join(
                    f"{ch}: {voltages[ch]:.2f}V" for ch in config.AVAILABLE_CHANNELS
                )
                pkt = self.received_packets
                self.schedule(0, lambda n=pkt, s=v_str: self.log(f"Rx #{n} -> {s}"))
            else:
                self.schedule(0, lambda: self.log("Warning: BLE dropped packet."))

            # Autosave to CSV every 10 packets
            self._last_autosave_count = self._autosave_to_csv()

            # Tell the GUI to refresh the graph
            self.schedule(0, self.refresh)

            # Wait for the next sampling interval
            time.sleep(1.0 / self.sampling_rate_hz)
            self._frame_idx += 1

    def _autosave_to_csv(self):
        """Write new data rows to the CSV logger in batches of 10."""
        current_count = len(self.all_history)
        if current_count - self._last_autosave_count >= 10:
            new_rows = self.all_history[self._last_autosave_count:current_count]
            try:
                for row in new_rows:
                    self.csv_logger.log_packet(row)
                self.schedule(0, lambda: self.log("Autosave: CSV sync complete"))
                return current_count
            except Exception as e:
                self.schedule(0, lambda err=e: self.log(f"Autosave error: {err}"))
        return self._last_autosave_count
