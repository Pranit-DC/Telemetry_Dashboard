import numpy as np
from typing import List, Dict
from models.telemetry import TracePoint, TraceBurst

def compute_peak_voltage(trace_points: List[TracePoint]) -> float:
    """Returns the maximum voltage from a list of trace points."""
    if not trace_points:
        return 0.0
    return max(pt.voltage for pt in trace_points)

def compute_fall_time(trace_points: List[TracePoint]) -> float:
    """Computes the 90%-to-10% fall time in microseconds."""
    if not trace_points:
        return 0.0
        
    peak_voltage = compute_peak_voltage(trace_points)
    # Find peak index
    peak_idx = 0
    for i, pt in enumerate(trace_points):
        if pt.voltage == peak_voltage:
            peak_idx = i
            break
            
    # Look only at the decay portion
    decay_points = trace_points[peak_idx:]
    if not decay_points:
        return 0.0
        
    v90 = peak_voltage * 0.9
    v10 = peak_voltage * 0.1
    
    t90 = None
    t10 = None
    
    # Simple linear interpolation or just nearest for now
    # We find the first time it drops below the threshold
    for pt in decay_points:
        if t90 is None and pt.voltage <= v90:
            t90 = pt.time_us
        if t10 is None and pt.voltage <= v10:
            t10 = pt.time_us
            
    if t90 is not None and t10 is not None:
        return max(0.0, t10 - t90)
    return 0.0

def compute_decay_constant(trace_points: List[TracePoint]) -> float:
    """Performs log-linear regression on the decay portion to find tau."""
    if not trace_points or len(trace_points) < 3:
        return 0.0
        
    peak_voltage = compute_peak_voltage(trace_points)
    
    peak_idx = 0
    for i, pt in enumerate(trace_points):
        if pt.voltage == peak_voltage:
            peak_idx = i
            break
            
    decay_points = trace_points[peak_idx:]
    if len(decay_points) < 3:
        return 0.0
        
    # v(t) = v0 * exp(-t/tau) => ln(v(t)) = ln(v0) - t/tau
    t_vals = np.array([pt.time_us for pt in decay_points])
    # shift time to 0 at peak
    t_vals = t_vals - t_vals[0]
    
    v_vals = np.array([max(pt.voltage, 1e-6) for pt in decay_points]) # avoid log(0)
    ln_v = np.log(v_vals)
    
    # Fit line: ln_v = m*t + c
    # m = -1/tau => tau = -1/m
    coeffs = np.polyfit(t_vals, ln_v, 1)
    m = coeffs[0]
    
    if m >= 0:
        return 0.0 # Did not decay properly
        
    tau = -1.0 / m
    return float(tau)

def compute_session_statistics(bursts: List[TraceBurst]) -> Dict[str, float]:
    """Computes mean, std, min, max for fall time and peak voltage across bursts."""
    if not bursts:
        return {}
        
    fall_times = [b.fall_time_us for b in bursts]
    peaks = [b.peak_voltage for b in bursts]
    
    return {
        'fall_time_mean': float(np.mean(fall_times)),
        'fall_time_std': float(np.std(fall_times)),
        'fall_time_min': float(np.min(fall_times)),
        'fall_time_max': float(np.max(fall_times)),
        'peak_mean': float(np.mean(peaks)),
        'peak_std': float(np.std(peaks)),
        'peak_min': float(np.min(peaks)),
        'peak_max': float(np.max(peaks))
    }

def normalize(values: List[float]) -> List[float]:
    """Min-max normalizes a list of values to [0, 1]."""
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.0 for _ in values]
    return [(v - min_val) / (max_val - min_val) for v in values]
