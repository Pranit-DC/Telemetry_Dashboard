import customtkinter as ctk
from gui.components.chart import BaseChart


class OverviewTab(ctk.CTkFrame):
    """Peak voltage trend across all bursts in the session."""

    def __init__(self, parent, db, burst_history):
        super().__init__(parent, fg_color="transparent")
        self.burst_history = burst_history

        self.chart = BaseChart(
            self,
            title="Peak Voltage per Burst",
            x_label="Burst ID",
            y_label="Peak Voltage (V)",
        )
        self.chart.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        self.chart.ax.clear()

        if not self.burst_history:
            self.chart.ax.text(
                0.5, 0.5, "No burst data yet",
                ha="center", va="center", color="white", transform=self.chart.ax.transAxes,
            )
            self.chart.draw()
            return

        burst_ids = [b.burst_id for b in self.burst_history]
        peaks = [b.peak_voltage for b in self.burst_history]

        self.chart.ax.plot(burst_ids, peaks, marker="o", color="#4FC3F7")
        self.chart.ax.set_title("Peak Voltage per Burst", color="white")
        self.chart.ax.set_xlabel("Burst ID", color="white")
        self.chart.ax.set_ylabel("Peak Voltage (V)", color="white")
        self.chart.ax.tick_params(colors="white")
        self.chart.draw()