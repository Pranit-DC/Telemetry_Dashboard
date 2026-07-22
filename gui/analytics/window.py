# Analytics window with tabbed layout.
# Each tab gets access to the database and live data references
# so they can build charts and tables from real data.

import customtkinter as ctk
from .overview import OverviewTab
from .statistics import StatisticsTab
from .signal import SignalAnalysisTab
from .reports import ReportsTab


class AnalyticsWindow(ctk.CTkToplevel):
    """Tabbed analytics window for detailed signal analysis."""

    def __init__(self, db, time_data, channels_data):
        super().__init__()

        # Store data references so tabs can access them
        self.db = db
        self.time_data = time_data
        self.channels_data = channels_data

        self.title("Analytics Suite")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        self.lift()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(main_frame)
        self.tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Create the tab containers
        overview_tab = self.tabview.add("Overview")
        statistics_tab = self.tabview.add("Statistics")
        signal_tab = self.tabview.add("Signal Analysis")
        report_tab = self.tabview.add("Reports")

        # Configure tabs to expand their content
        for tab in [overview_tab, statistics_tab, signal_tab, report_tab]:
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        # Mount modular tab views — each receives db and data references
        self.overview_view = OverviewTab(overview_tab, db, time_data, channels_data)
        self.overview_view.grid(row=0, column=0, sticky="nsew", padx=20, pady=5)

        self.statistics_view = StatisticsTab(statistics_tab, db, time_data, channels_data)
        self.statistics_view.grid(row=0, column=0, sticky="nsew", padx=20, pady=5)

        self.signal_view = SignalAnalysisTab(signal_tab, db, time_data, channels_data)
        self.signal_view.grid(row=0, column=0, sticky="nsew", padx=20, pady=5)

        self.report_view = ReportsTab(report_tab, db, time_data, channels_data)
        self.report_view.grid(row=0, column=0, sticky="nsew", padx=20, pady=5)
