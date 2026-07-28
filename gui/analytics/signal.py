import customtkinter as ctk
from gui.components.chart import BaseChart

MAX_OVERLAY_TRACES = 10


class SignalAnalysisTab(ctk.CTkFrame):
    """Overlay of raw voltage traces for the most recent bursts."""

    def __init__(self, parent, db, burst_history):
        super().__init__(parent, fg_color="transparent")
        self.burst_history = burst_history

        self.chart = BaseChart(
            self,
            title=f"Last {MAX_OVERLAY_TRACES} Traces (Overlay)",
            x_label="Time (us)",
            y_label="Voltage (V)",
        )
        self.chart.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        self.chart.ax.clear()

        recent = self.burst_history[-MAX_OVERLAY_TRACES:]

        if not recent:
            self.chart.ax.text(
                0.5, 0.5, "No burst data yet",
                ha="center", va="center", color="white", transform=self.chart.ax.transAxes,
            )
            self.chart.draw()
            return

        for burst in recent:
            times = [p.time_us for p in burst.trace_points]
            volts = [p.voltage for p in burst.trace_points]
            self.chart.ax.plot(times, volts, linewidth=1, alpha=0.7, label=f"Burst {burst.burst_id}")

        self.chart.ax.set_title(f"Last {len(recent)} Traces (Overlay)", color="white")
        self.chart.ax.set_xlabel("Time (us)", color="white")
        self.chart.ax.set_ylabel("Voltage (V)", color="white")
        self.chart.ax.tick_params(colors="white")
        if len(recent) <= 10:
            legend = self.chart.ax.legend(fontsize=7, facecolor="#1A1A1E", labelcolor="white")
        self.chart.draw()