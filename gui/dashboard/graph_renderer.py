import numpy as np

class GraphRenderer:
    """
    Handles plotting updates for the dashboard charts.
    """
    def __init__(self, dashboard_page):
        self.page = dashboard_page
        self.locked_burst = None
    
    def refresh(self, latest_burst, burst_history):
        """Update both charts and metric cards."""
        if latest_burst:
            display_burst = self.locked_burst if self.locked_burst else latest_burst
            self._update_trace_chart(display_burst)
            self._update_metric_cards(display_burst, burst_history)
        if burst_history:
            self._update_trend_chart(burst_history)
        self._update_diagnostics(burst_history)
    
    def _update_trace_chart(self, burst):
        """Plot the decay trace: voltage vs time (us) with smart default zoom."""
        if not burst.trace_points:
            return
            
        times = [p.time_us for p in burst.trace_points]
        voltages = [p.voltage for p in burst.trace_points]
        self.page.trace_line.set_data(times, voltages)
        
        # Smart Default Zoom: Focus on 900us region starting 40us before peak drop
        peak_idx = max(range(len(burst.trace_points)), key=lambda i: burst.trace_points[i].voltage)
        peak_time = times[peak_idx]
        
        min_x = max(times[0], peak_time - 40.0)
        max_x = min(times[-1], peak_time + 860.0)
        
        self.page.ax_trace.set_xlim(min_x, max_x)
        self.page.ax_trace.relim()
        self.page.ax_trace.autoscale_view(scalex=False, scaley=True)
        self.page.canvas_trace.draw_idle()
    
    def _update_trend_chart(self, burst_history):
        """Plot fall time trend over burst index (rolling window of 20)."""
        window_size = 20
        start_idx = max(0, len(burst_history) - window_size)
        display_history = burst_history[start_idx:]
        
        indices = list(range(start_idx, len(burst_history)))
        fall_times = [b.fall_time_us for b in display_history]
        self.page.trend_line.set_data(indices, fall_times)
        if self.page.ax_trend.get_autoscalex_on() and self.page.ax_trend.get_autoscaley_on():
            self.page.ax_trend.relim()
            self.page.ax_trend.autoscale_view()
        self.page.canvas_trend.draw_idle()
    
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
        """Clear the charts."""
        self.page.trace_line.set_data([], [])
        self.page.trend_line.set_data([], [])
        self.page.canvas_trace.draw_idle()
        self.page.canvas_trend.draw_idle()
