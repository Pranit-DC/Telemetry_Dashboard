import numpy as np
from core.analysis.fall_time import DROP_THRESHOLD

class GraphRenderer:
    """
    Handles plotting updates for the dashboard charts.
    """
    def __init__(self, dashboard_page):
        self.page = dashboard_page
    
    def refresh(self, latest_burst, burst_history):
        """Update the chart and metric cards."""
        if latest_burst:
            self._update_trace_chart(latest_burst)
            self._update_metric_cards(latest_burst, burst_history)
        self._update_diagnostics(burst_history)
    
    def _update_trace_chart(self, burst):
        """Plot the decay trace: voltage vs time (us), full 700-sample view by default."""
        if not burst.trace_points:
            return

        times = [p.time_us for p in burst.trace_points]
        voltages = [p.voltage for p in burst.trace_points]
        self.page.trace_line.set_data(times, voltages)

        # Default view is always the complete burst (all 700 samples, full
        # 2.8ms) - not narrowed to any sub-window. User can still zoom/pan via
        # the toolbar; this just controls what's shown immediately on each
        # new capture.
        self.page.ax_trace.set_xlim(times[0], times[-1])
        self.page.ax_trace.relim()
        self.page.ax_trace.autoscale_view(scalex=False, scaley=True)
        self.page.canvas_trace.draw_idle()
    
    def _update_metric_cards(self, burst, history):
        """Update the metric card values on the page."""
        cards = self.page.cards
        cards['Peak Voltage']['value'].configure(text=f'{burst.peak_voltage:.3f} V')
        cards['Fall Time']['value'].configure(text=f'{burst.fall_time_us:.1f} μs')
        cards['Avg Fall Time']['value'].configure(text=f'{burst.avg_fall_time_us:.1f} μs')
        
        valid_falls = [b.fall_time_us for b in history if b.fall_time_us > 0]
        if valid_falls:
            std_dev = float(np.std(valid_falls))
            min_f = min(valid_falls)
            max_f = max(valid_falls)
            cards['Std Dev (σ)']['value'].configure(text=f'±{std_dev:.1f} μs')
            cards['Min / Max Fall']['value'].configure(text=f'{min_f:.1f} / {max_f:.1f} μs')
        else:
            cards['Std Dev (σ)']['value'].configure(text='--')
            cards['Min / Max Fall']['value'].configure(text='--')
    
    def _update_diagnostics(self, history):
        """Update diagnostic text."""
        self.page.lbl_burst_count.configure(text=f'Burst Count: {len(history)}')
    
    def clear(self):
        """Clear the chart."""
        self.page.trace_line.set_data([], [])
        self.page.canvas_trace.draw_idle()