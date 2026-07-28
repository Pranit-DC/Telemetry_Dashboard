import math
import pytest
from core.analysis.fall_time import FallTimeCalculator, TARGET_SAMPLES


def make_burst(peak=2.0, tau_samples=50, floor=0.001, length=TARGET_SAMPLES, peak_index=10):
    """
    Build a synthetic 700-sample burst: flat baseline, a sharp drop at
    peak_index (>= DROP_THRESHOLD), then a clean exponential decay.
    tau_samples controls how fast it decays (in samples, not us).
    """
    v = [peak + 0.5] * peak_index          # baseline before the peak
    v.append(peak)                          # the peak sample itself
    i = 0
    while len(v) < length:
        val = peak * math.exp(-i / tau_samples)
        v.append(max(val, floor))
        i += 1
    return v[:length]


class TestFallTimeCalculator:

    def test_valid_decay_returns_no_error(self):
        calc = FallTimeCalculator()
        result = calc.compute(make_burst())
        assert result.error is None
        assert result.fall_time_us > 0

    def test_wrong_sample_count_raises(self):
        calc = FallTimeCalculator()
        with pytest.raises(ValueError):
            calc.compute([0.0] * 10)

    def test_peak_below_gate_returns_bounds_error(self):
        calc = FallTimeCalculator()
        # No drop >= 0.05V anywhere -> true_peak_index stays 0,
        # and that sample is below the 1.0V gate.
        result = calc.compute([0.2] * TARGET_SAMPLES)
        assert result.error == "ERROR_BOUNDS_EXCEEDED"
        assert result.fall_time_us == 0.0

    def test_peak_too_close_to_end_returns_bounds_error(self):
        calc = FallTimeCalculator()
        v = [1.5] * (TARGET_SAMPLES - 5) + [1.0] * 5
        # force a drop right near the end so reg_end_idx overflows
        v[-6] = 1.5
        v[-5] = 1.0  # drop of 0.5 here, near the tail
        result = calc.compute(v)
        assert result.error == "ERROR_BOUNDS_EXCEEDED"

    def test_flat_signal_after_peak_is_not_gated(self):
        """
        KNOWN EDGE CASE (not a test bug -- a real gap in the math):
        a perfectly flat post-peak signal has a true slope of exactly 0,
        which should trip ERROR_SLOPE_POSITIVE. In practice floating-point
        noise pushes the computed slope a hair below zero, so no gate
        catches it and compute() returns success with an absurd
        fall_time_us (order of 1e17 us here). Documented so this doesn't
        get "fixed" by surprise later -- see report notes.
        """
        calc = FallTimeCalculator()
        v = [1.0] * 5 + [1.5] * (TARGET_SAMPLES - 5)
        v[4] = 2.0
        v[5] = 1.5
        result = calc.compute(v)
        if result.error is None:
            assert result.fall_time_us > 1e6  # nonsensical magnitude, not a real fall time
        else:
            assert result.error in ("ERROR_NOT_ENOUGH_POINTS", "ERROR_SLOPE_POSITIVE",
                                     "ERROR_DENOMINATOR_ZERO")

    def test_rolling_average_over_last_10_bursts(self):
        calc = FallTimeCalculator()
        results = [calc.compute(make_burst(tau_samples=40 + k)) for k in range(12)]
        successful = [r.fall_time_us for r in results if r.error is None]
        assert len(calc._history) <= 10
        # avg reported on the last call should equal avg of at most last 10 successes
        expected_avg = sum(successful[-10:]) / len(successful[-10:])
        assert results[-1].avg_fall_time_us == pytest.approx(expected_avg)

    def test_reset_history_clears_average(self):
        calc = FallTimeCalculator()
        calc.compute(make_burst())
        assert calc._current_avg() != 0.0
        calc.reset_history()
        assert calc._current_avg() == 0.0

    def test_faster_decay_gives_smaller_fall_time(self):
        calc = FallTimeCalculator()
        fast = calc.compute(make_burst(tau_samples=20))
        slow = calc.compute(make_burst(tau_samples=100))
        assert fast.error is None and slow.error is None
        assert fast.fall_time_us < slow.fall_time_us