import customtkinter as ctk

from .overview import OverviewTab
from .signal import SignalAnalysisTab
from .statistics import StatisticsTab
from .reports import ReportsTab

class AnalyticsWindow(ctk.CTkToplevel):
    """
    Advanced Analytics Window.
    """
    def __init__(self, db, burst_history):
        super().__init__()
        self.title("Data Analytics & Post-Processing")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}+0+0")
        self.minsize(1200, 780)

        self.db = db
        self.burst_history = burst_history
        
        # Build UI
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_overview = self.tabview.add("Overview")
        self.tab_signal = self.tabview.add("Signal Analysis")
        self.tab_stats = self.tabview.add("Statistics")
        self.tab_reports = self.tabview.add("Reports")
        
        self.overview_view = OverviewTab(self.tab_overview, self.db, self.burst_history)
        self.overview_view.pack(fill="both", expand=True)
        
        self.signal_view = SignalAnalysisTab(self.tab_signal, self.db, self.burst_history)
        self.signal_view.pack(fill="both", expand=True)
        
        self.stats_view = StatisticsTab(self.tab_stats, self.db, self.burst_history)
        self.stats_view.pack(fill="both", expand=True)
        
        self.reports_view = ReportsTab(self.tab_reports, self.db, self.burst_history)
        self.reports_view.pack(fill="both", expand=True)
