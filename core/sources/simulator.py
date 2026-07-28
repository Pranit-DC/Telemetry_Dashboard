import time
import random
import math
import threading
from datetime import datetime
from queue import Queue
from .base import DataSource
from models.telemetry import TracePoint, TraceBurst
from core.analysis.fall_time import FallTimeCalculator, TARGET_SAMPLES, US_PER_SAMPLE


class SimulatorSource(DataSource):
    """Generates synthetic decay trace bursts for testing purposes.

    Shaped to match real photodiode/BLE capture behavior (see the RAW BLE RX
    sample this was validated against): a noisy flat baseline, a sharp drop,
    exponential decay into a noisy non-zero floor - not a clean textbook
    curve. Always emits exactly TARGET_SAMPLES (700) points, matching what
    real bursts (Serial and BLE) always produce, so the GUI's zoom/regression
    logic behaves identically whether the data is real or simulated.

    Metrics (peak_voltage, fall_time_us, avg_fall_time_us) are computed by
    running the exact same FallTimeCalculator used for real data - never
    fabricated - so what's displayed always matches what's actually plotted.
    """

    def __init__(self, burst_queue: Queue, burst_interval=0.25):
        super().__init__(burst_queue)
        self.burst_interval = burst_interval
        self._running = False
        self._thread = None
        self._burst_id_counter = 1
        self._fall_time_calc = FallTimeCalculator()

    def connect(self) -> None:
        self._set_state('connected')

    def start(self) -> None:
        if self._state == 'connected':
            self._running = True
            self._set_state('acquiring')
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._state == 'acquiring':
            self._set_state('connected')

    def disconnect(self) -> None:
        self.stop()
        self._set_state('disconnected')

    def send_command(self, command: str) -> None:
        # No-op for simulator
        pass

    @property
    def source_type(self) -> str:
        return 'simulator'

    def _generate_voltages(self) -> list:
        """Build one realistic 700-sample decay burst.

        Shape, in order, matching real captures:
          1. Flat noisy baseline before the trigger point (~2.2-2.3V)
          2. A sharp drop at a randomized peak index (kept small, like real
             data - the peak happens early in the burst, not mid-way)
          3. Exponential decay down toward a noisy non-zero floor
          4. Correlated (not white) noise throughout, since real ADC/photodiode
             noise is visibly "smooth-ish" jitter, not sample-to-sample static
        """
        baseline_v = random.uniform(2.15, 2.35)
        # Calibrated against a real BARC capture (single ground-truth sample,
        # not a distribution - treat this as a first approximation, refine
        # once more real bursts are available). That sample's regression
        # window (peak+40 to peak+190) decayed from 1.61V to 0.57V over
        # 600us, giving tau ~= 575us and fall_time_us ~= 1260us - NOT the
        # ~150-280us this was previously (wrongly) calibrated to, which
        # turned out to be simulator output mistaken for a hardware screenshot.
        #
        # The real floor in that sample was 0.058-0.116V (mean 0.084V) -
        # genuinely above the 0.05V regression gate. That's fine: with tau
        # this long, the fit window is still ~7x above the floor at its far
        # edge, so floor noise never dominates the fit the way it would with
        # a short tau. Floor is intentionally NOT forced below 0.05 here.
        floor_v = random.uniform(0.06, 0.12)
        true_peak_index = random.randint(8, 15)   # real sample: peak at index 11
        tau_us = random.uniform(450.0, 650.0)      # real sample implies ~575us

        voltages = []
        # Correlated noise via a simple leaky integrator (random walk with decay),
        # not independent gaussian per sample - matches the "jaggy but smooth"
        # texture seen in the real RAW BLE RX capture.
        noise_state = 0.0
        noise_leak = 0.7
        noise_sigma = 0.0095  # calibrated to match real floor stdev (~0.013V after leaky-integrator gain)

        for i in range(TARGET_SAMPLES):
            noise_state = noise_state * noise_leak + random.gauss(0, noise_sigma)

            if i < true_peak_index:
                ideal_v = baseline_v
            else:
                t_us = (i - true_peak_index) * US_PER_SAMPLE
                ideal_v = floor_v + (baseline_v - floor_v) * math.exp(-t_us / tau_us)

            v = ideal_v + noise_state
            v = max(0.0, min(3.3, v))  # clamp to valid ADC range
            voltages.append(v)

        return voltages

    def _run_loop(self):
        """Background thread loop generating synthetic bursts."""
        while self._running:
            voltages = self._generate_voltages()

            trace_points = [
                TracePoint(sample_index=i, time_us=i * US_PER_SAMPLE, voltage=v)
                for i, v in enumerate(voltages)
            ]

            # Same regression as real data - never fabricate metrics separately
            # from the curve actually being plotted.
            result = self._fall_time_calc.compute(voltages)

            burst = TraceBurst(
                burst_id=self._burst_id_counter,
                timestamp=datetime.now(),
                trace_points=trace_points,
                peak_voltage=result.peak_voltage,
                fall_time_us=result.fall_time_us,
                avg_fall_time_us=result.avg_fall_time_us,
                channel=0
            )
            self._burst_id_counter += 1

            self.burst_queue.put(burst)
            time.sleep(self.burst_interval)