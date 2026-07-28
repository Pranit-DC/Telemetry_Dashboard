import customtkinter as ctk
from gui.components.chart import BaseChart


class StatisticsTab(ctk.CTkFrame):
    """Distribution of fall times across all bursts in the session."""

    def __init__(self, parent, db, burst_history):
        super().__init__(parent, fg_color="transparent")
        self.burst_history = burst_history

        self.chart = BaseChart(
            self,
            title="Fall Time Distribution",
            x_label="Fall Time (us)",
            y_label="Count",
        )
        self.chart.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        self.chart.ax.clear()

        fall_times = [b.fall_time_us for b in self.burst_history if b.fall_time_us > 0]

        if not fall_times:
            self.chart.ax.text(
                0.5, 0.5, "No burst data yet",
                ha="center", va="center", color="white", transform=self.chart.ax.transAxes,
            )
            self.chart.draw()
            return

        bins = min(20, max(5, len(fall_times) // 2))
        self.chart.ax.hist(fall_times, bins=bins, color="#81C784", edgecolor="#1A1A1E")
        self.chart.ax.set_title("Fall Time Distribution", color="white")
        self.chart.ax.set_xlabel("Fall Time (us)", color="white")
        self.chart.ax.set_ylabel("Count", color="white")
        self.chart.ax.tick_params(colors="white")
        self.chart.draw()