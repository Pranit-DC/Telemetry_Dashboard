# Signal Analysis tab skeleton for the Analytics window.
# TODO: Add peak detection, rolling mean, rolling std dev, drift.

import customtkinter as ctk


class SignalAnalysisTab(ctk.CTkFrame):
    """Signal Analysis tab — build your signal processing views here."""

    def __init__(self, parent, db, time_data, channels_data):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.time_data = time_data
        self.channels_data = channels_data

        ctk.CTkLabel(
            self, text="Signal Analysis Tab — Coming Soon",
            font=ctk.CTkFont("Segoe UI", 16), text_color="#7F7F8C",
        ).pack(expand=True)
