# Signal analysis functions for telemetry data.
# Every function here is pure math: takes numbers in, returns numbers out.
# No GUI code, no database calls, no file I/O.


def peak_to_peak(values):
    """Difference between the highest and lowest voltage in the dataset."""
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)


def estimate_frequency(time_data, voltage_data):
    """Estimate signal frequency using the zero-crossing method.

    We count how many times the signal crosses upward through its midpoint,
    then use the average time between crossings as the period.

    Returns frequency in Hz, or None if there aren't enough crossings.
    """
    if len(voltage_data) < 2:
        return None

    v_max = max(voltage_data)
    v_min = min(voltage_data)
    midpoint = (v_max + v_min) / 2

    # Find the times where voltage crosses upward through the midpoint
    n = min(len(time_data), len(voltage_data))
    crossings = [
        time_data[i]
        for i in range(1, n)
        if voltage_data[i - 1] < midpoint <= voltage_data[i]
    ]

    if len(crossings) < 2:
        return None

    # Average period = average gap between consecutive crossings
    periods = [crossings[i] - crossings[i - 1] for i in range(1, len(crossings))]
    avg_period = sum(periods) / len(periods)

    return (1.0 / avg_period) if avg_period > 0 else None


def find_peak_time(time_data, voltage_data):
    """Return the elapsed time at which the maximum voltage occurred."""
    if not voltage_data:
        return 0.0
    peak_idx = voltage_data.index(max(voltage_data))
    return time_data[peak_idx] if peak_idx < len(time_data) else 0.0


def rise_time(time_data, voltage_data):
    """Time for the signal to travel from 10% to 90% of its peak-to-peak range.

    This measures how fast the signal responds to a change.
    Returns seconds, or None if it can't be calculated.
    """
    if len(voltage_data) < 2:
        return None

    v_min = min(voltage_data)
    v_pp = max(voltage_data) - v_min
    if v_pp <= 0:
        return None

    threshold_10 = v_min + 0.1 * v_pp
    threshold_90 = v_min + 0.9 * v_pp

    # Find the first time the signal passes each threshold
    t_10 = next((t for t, v in zip(time_data, voltage_data) if v >= threshold_10), None)
    t_90 = next((t for t, v in zip(time_data, voltage_data) if v >= threshold_90), None)

    if t_10 is not None and t_90 is not None and t_90 > t_10:
        return t_90 - t_10
    return None


def max_jitter(time_data, channels_data, target_channel, all_channels):
    """Largest timing offset between the target channel's peak and other channels' peaks.

    Jitter tells us how synchronized the channels are. If Channel 1 peaks
    at t=5.0s and Channel 2 peaks at t=5.3s, the jitter is 300ms.
    Returns jitter in milliseconds.
    """
    target_data = list(channels_data[target_channel])
    if not target_data or len(target_data) != len(time_data):
        return 0.0

    target_peak_t = time_data[target_data.index(max(target_data))]
    worst_jitter = 0.0

    for ch in all_channels:
        if ch == target_channel:
            continue
        ch_data = list(channels_data[ch])
        if ch_data and len(ch_data) == len(time_data):
            ch_peak_t = time_data[ch_data.index(max(ch_data))]
            jitter_ms = abs(target_peak_t - ch_peak_t) * 1000.0
            worst_jitter = max(worst_jitter, jitter_ms)

    return worst_jitter


def normalize(values):
    """Scale values to a 0-1 range using min-max normalization.

    Useful for comparing channels with different amplitude ranges
    on the same graph scale.
    """
    if len(values) < 2:
        return values
    v_min = min(values)
    v_max = max(values)
    if v_max == v_min:
        return [0.0] * len(values)
    return [(v - v_min) / (v_max - v_min) for v in values]
