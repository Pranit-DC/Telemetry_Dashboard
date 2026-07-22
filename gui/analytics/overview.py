import customtkinter as ctk

class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, db, burst_history):
        super().__init__(parent, fg_color="transparent")
        lbl = ctk.CTkLabel(self, text="Overview Analytics\n(Coming Soon)", font=("Segoe UI", 24))
        lbl.pack(expand=True)
