"""
Fall-time regression — exact port of the Arduino firmware's on-device math.

Firmware reference (relevant block in loop()):
    truePeakIndex found by scanning for a drop >= dropThreshold (0.050 V)
    peakStartVoltage = capturedVoltages[truePeakIndex]
    gate: peakStartVoltage >= 1.0, else ERROR_BOUNDS_EXCEEDED
    regStartIdx = truePeakIndex + 40
    regEndIdx   = truePeakIndex + 190
    gate: regEndIdx < TARGET_SAMPLES, else ERROR_BOUNDS_EXCEEDED
    linear regression of ln(voltage) vs t over that window, voltage > 0.05 only
    gate: nPoints > 10, else ERROR_NOT_ENOUGH_POINTS
    gate: |denominator| > 1e-4, else ERROR_DENOMINATOR_ZERO
    gate: slope < 0, else ERROR_SLOPE_POSITIVE
    fall_time_us = 2.1972245 * (-1.0 / slope)

This module intentionally mirrors that structure step-for-step (including the
magic constants) so dashboard results match what the Arduino would have
computed on the same raw samples. It runs on the raw, unprocessed voltages
received over BLE/Serial — it does not trust any metrics the firmware itself
may have reported.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

US_PER_SAMPLE = 4.0
TARGET_SAMPLES = 700
DROP_THRESHOLD = 0.050
REG_START_OFFSET = 40
REG_END_OFFSET = 190
MIN_REGRESSION_POINTS = 10
PEAK_VOLTAGE_GATE = 1.0
VOLTAGE_FLOOR_FOR_LN = 0.05
FALL_TIME_CONSTANT = 2.1972245  # ln(1 / (1 - 0.9)) — matches firmware exactly


@dataclass
class FallTimeResult:
    peak_voltage: float
    fall_time_us: float          # 0.0 if this burst's regression failed
    avg_fall_time_us: float      # rolling average of last 10 *successful* bursts
    true_peak_index: int
    error: Optional[str] = None  # matches firmware ERROR_* strings, or None on success


class FallTimeCalculator:
    """Stateful port of the firmware's rolling 10-run average.

    Keep one instance per BLE/Serial source (or per session) — it accumulates
    history exactly like the Arduino's fallTimeHistory[10] array does.
    """

    def __init__(self):
        self._history: List[float] = []

    def reset_history(self):
        self._history.clear()

    def compute(self, voltages: List[float]) -> FallTimeResult:
        n = len(voltages)
        if n != TARGET_SAMPLES:
            # Not a hard requirement of the math itself, but a burst that isn't
            # exactly 700 samples means upstream reconstruction is incomplete —
            # caller should not have gotten here without a fully reconstructed array.
            raise ValueError(f"Expected {TARGET_SAMPLES} samples, got {n}")

        # wnd truePeakIndex (same scan as firmware) 
        true_peak_index = 0
        peak_validated = False
        for i in range(TARGET_SAMPLES - 1):
            if (voltages[i] - voltages[i + 1]) >= DROP_THRESHOLD:
                true_peak_index = i
                peak_validated = True
                break
        if not peak_validated:
            true_peak_index = 0

        peak_start_voltage = voltages[true_peak_index]

        if peak_start_voltage < PEAK_VOLTAGE_GATE:
            return FallTimeResult(peak_start_voltage, 0.0, self._current_avg(),
                                   true_peak_index, error="ERROR_BOUNDS_EXCEEDED")

        reg_start_idx = true_peak_index + REG_START_OFFSET
        reg_end_idx = true_peak_index + REG_END_OFFSET

        if reg_end_idx >= TARGET_SAMPLES:
            return FallTimeResult(peak_start_voltage, 0.0, self._current_avg(),
                                   true_peak_index, error="ERROR_BOUNDS_EXCEEDED")

        sum_x = sum_y = sum_xy = sum_x2 = 0.0
        n_points = 0
        for i in range(reg_start_idx, reg_end_idx + 1):
            voltage = voltages[i]
            if voltage > VOLTAGE_FLOOR_FOR_LN:
                t = (i - reg_start_idx) * US_PER_SAMPLE
                ln_v = math.log(voltage)
                sum_x += t
                sum_y += ln_v
                sum_xy += t * ln_v
                sum_x2 += t * t
                n_points += 1

        if n_points <= MIN_REGRESSION_POINTS:
            return FallTimeResult(peak_start_voltage, 0.0, self._current_avg(),
                                   true_peak_index, error="ERROR_NOT_ENOUGH_POINTS")

        denominator = (n_points * sum_x2) - (sum_x * sum_x)
        if abs(denominator) <= 1e-4:
            return FallTimeResult(peak_start_voltage, 0.0, self._current_avg(),
                                   true_peak_index, error="ERROR_DENOMINATOR_ZERO")

        slope = ((n_points * sum_xy) - (sum_x * sum_y)) / denominator
        if slope >= 0:
            return FallTimeResult(peak_start_voltage, 0.0, self._current_avg(),
                                   true_peak_index, error="ERROR_SLOPE_POSITIVE")

        fall_time_us = FALL_TIME_CONSTANT * (-1.0 / slope)

        self._history.append(fall_time_us)
        if len(self._history) > 10:
            self._history.pop(0)

        return FallTimeResult(
            peak_voltage=peak_start_voltage,
            fall_time_us=fall_time_us,
            avg_fall_time_us=self._current_avg(),
            true_peak_index=true_peak_index,
            error=None,
        )

    def _current_avg(self) -> float:
        if not self._history:
            return 0.0
        return sum(self._history) / len(self._history)