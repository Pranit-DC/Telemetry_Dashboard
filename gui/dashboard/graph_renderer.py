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
        """Plot the decay trace: voltage vs relative sample number."""
        indices = list(range(len(burst.trace_points)))
        voltages = [p.voltage for p in burst.trace_points]
        self.page.trace_line.set_data(indices, voltages)
        if self.page.ax_trace.get_autoscalex_on() and self.page.ax_trace.get_autoscaley_on():
            self.page.ax_trace.relim()
            self.page.ax_trace.autoscale_view()
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
        cards['Burst Count']['value'].configure(text=str(len(history)))
    
    def _update_diagnostics(self, history):
        """Update diagnostic text."""
        self.page.lbl_burst_count.configure(text=f'Burst Count: {len(history)}')
    
    def clear(self):
        """Clear the charts."""
        self.page.trace_line.set_data([], [])
        self.page.trend_line.set_data([], [])
        self.page.canvas_trace.draw_idle()
        self.page.canvas_trend.draw_idle()
