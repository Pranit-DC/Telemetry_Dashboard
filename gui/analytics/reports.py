# Reports tab skeleton for the Analytics window.
# TODO: Add preview, export, and report settings.

import customtkinter as ctk


class ReportsTab(ctk.CTkFrame):
    """Reports tab — build your PDF/HTML report generators here."""

    def __init__(self, parent, db, time_data, channels_data):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.time_data = time_data
        self.channels_data = channels_data

        ctk.CTkLabel(
            self, text="Reports Tab — Coming Soon",
            font=ctk.CTkFont("Segoe UI", 16), text_color="#7F7F8C",
        ).pack(expand=True)
