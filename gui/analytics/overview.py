# Overview tab skeleton for the Analytics window.
# TODO: Add time series graph, statistics cards, acquisition summary.

import customtkinter as ctk


class OverviewTab(ctk.CTkFrame):
    """Overview tab — build your charts and summary cards here."""

    def __init__(self, parent, db, time_data, channels_data):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.time_data = time_data
        self.channels_data = channels_data

        # Placeholder label (replace with your actual widgets)
        ctk.CTkLabel(
            self, text="Overview Tab — Coming Soon",
            font=ctk.CTkFont("Segoe UI", 16), text_color="#7F7F8C",
        ).pack(expand=True)
