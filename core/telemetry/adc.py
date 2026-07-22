# ADC conversion utilities for the PIN-6D photodiode sensor.
# The Arduino Giga R1 uses a 16-bit ADC with 3.3V reference voltage.
# This module handles converting between raw integer counts and voltage.

import math
import random

# Hardware constants matching the Arduino Giga R1 specs
ADC_BITS = 16
ADC_MAX_COUNT = (2 ** ADC_BITS) - 1  # 65535 discrete steps
VOLTAGE_REF = 3.3  # Maximum measurable voltage on the ADC pin


def counts_to_voltage(raw_counts, bits=ADC_BITS, v_ref=VOLTAGE_REF):
    """Convert raw ADC integer counts back into a real voltage.

    The ADC divides the 0-to-v_ref range into (2^bits - 1) equal steps.
    For example, with 16-bit and 3.3V: count 32767 = ~1.65V (midpoint).
    """
    max_steps = (2 ** bits) - 1
    return (raw_counts / max_steps) * v_ref


def simulate_adc_reading(frame_index, sampling_rate_hz=700.0):
    """Generate fake ADC readings that mimic a real photodiode output.

    This is only used for testing when the actual BLE hardware is not connected.
    Each channel produces a slightly different sine/cosine wave with small noise,
    simulating how a real sensor signal might look.

    Returns:
        (hardware_timestamp_ms, channel_counts_dict)
        where channel_counts_dict maps "Channel 1/2/3" to raw ADC integer counts.
    """
    # Time step between samples depends on the sampling rate
    interval_ms = int(1000.0 / sampling_rate_hz)
    hw_timestamp_ms = frame_index * interval_ms
    t_sec = hw_timestamp_ms / 1000.0

    # Simulate 3 photodiode channels with different wave patterns.
    # Voltages are centered around ~1.5V with varying amplitudes,
    # staying well within the 0-3.3V range of the ADC.
    raw_voltages = [
        1.65 + 1.0 * math.sin(t_sec * 1.0) + random.gauss(0, 0.2),
        1.30 + 0.8 * math.cos(t_sec * 0.8) + random.gauss(0, 0.2),
        1.00 + 0.5 * math.sin(t_sec * 1.5) + random.gauss(0, 0.1),
    ]

    # Convert each voltage to an integer ADC count, clamped within valid range
    channel_counts = {}
    for i, voltage in enumerate(raw_voltages, start=1):
        clamped = max(0.0, min(VOLTAGE_REF, voltage))
        count = int((clamped / VOLTAGE_REF) * ADC_MAX_COUNT)
        channel_counts[f"Channel {i}"] = count

    return hw_timestamp_ms, channel_counts
