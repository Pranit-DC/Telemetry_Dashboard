# Sidebar UI component for the telemetry dashboard.
# Contains all control buttons, playback menus, checkboxes, and settings triggers.

import customtkinter as ctk
import config


class Sidebar(ctk.CTkFrame):
    """The left control panel of the telemetry dashboard."""

    def __init__(self, parent, controller):
        super().__init__(parent, corner_radius=0, fg_color="#1A1A1E")
        self.controller = controller

        # Title and status label
        ctk.CTkLabel(
            self, text="Telemetry Dashboard",
            font=ctk.CTkFont("Segoe UI", 15, "bold"), text_color="#3A7DFF",
        ).pack(padx=20, pady=(20, 2))

        self.lbl_status = ctk.CTkLabel(
            self, text="Status: IDLE",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#7F7F8C",
        )
        self.lbl_status.pack(padx=20, pady=(0, 10))

        # Control buttons
        btn_specs = [
            ("btn_start", "Start Simulation", "#2EA44F", "#227D3B", controller._on_start, "normal"),
            ("btn_pause", "Pause Capture", "#2D2D34", "#3A3A42", controller._on_pause, "disabled"),
            ("btn_stop", "Stop", "#D73A49", "#B32431", controller._on_stop, "disabled"),
            ("btn_clear", "Clear Buffer", "#2D2D34", "#3A3A42", controller._on_clear, "normal"),
        ]
        self.buttons = {}
        for name, text, bg, hover, cmd, state in btn_specs:
            btn = ctk.CTkButton(
                self, text=text, fg_color=bg, hover_color=hover,
                height=34, command=cmd, state=state, corner_radius=20,
                font=ctk.CTkFont("Segoe UI", 14, "bold" if "Clear" not in text else "normal"),
            )
            btn.pack(fill="x", padx=20, pady=6)
            self.buttons[name] = btn

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#25252A").pack(fill="x", padx=15, pady=8)

        # Historical playback dropdown
        ctk.CTkLabel(
            self, text="HISTORICAL PLAYBACK",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color="#606066",
        ).pack(anchor="w", padx=20, pady=(0, 2))

        playback_row = ctk.CTkFrame(self, fg_color="transparent")
        playback_row.pack(fill="x", padx=20, pady=3)
        playback_row.grid_columnconfigure(0, weight=1)

        self.opt_playback = ctk.CTkOptionMenu(
            playback_row, values=["No Sessions Saved"],
            command=controller._on_load_session,
            fg_color="#2D2D34", button_color="#5A5A65", button_hover_color="#4A4A52",
        )
        self.opt_playback.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.btn_manage_sessions = ctk.CTkButton(
            playback_row, text="⚙️", width=35, height=28,
            fg_color="#2D2D34", hover_color="#3A3A42",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            command=controller._open_session_manager,
        )
        self.btn_manage_sessions.grid(row=0, column=1, sticky="e")

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#25252A").pack(fill="x", padx=15, pady=8)

        # Channel visibility checkboxes
        ctk.CTkLabel(
            self, text="CHANNEL VISIBILITY",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color="#606066",
        ).pack(anchor="w", padx=20, pady=(0, 2))

        self.chk_vars = {}
        for ch in config.AVAILABLE_CHANNELS:
            var = ctk.BooleanVar(value=True)
            self.chk_vars[ch] = var
            ctk.CTkCheckBox(
                self, text=ch, variable=var, text_color="#FFFFFF",
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=controller._on_visibility_changed,
            ).pack(anchor="w", padx=25, pady=3)

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#25252A").pack(fill="x", padx=15, pady=8)

        # Live analytics target channel selector
        ctk.CTkLabel(
            self, text="LIVE ANALYTICS TARGET",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color="#606066",
        ).pack(anchor="w", padx=20, pady=(0, 2))

        self.opt_analytics = ctk.CTkOptionMenu(
            self, values=config.AVAILABLE_CHANNELS,
            command=controller._on_analytics_changed,
            fg_color="#2D2D34", button_color="#3A7DFF", button_hover_color="#2A65D4",
        )
        self.opt_analytics.pack(fill="x", padx=20, pady=3)

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#25252A").pack(fill="x", padx=15, pady=8)

        # Bottom buttons
        self.btn_analytics = ctk.CTkButton(
            self, text="Analytics", font=ctk.CTkFont("Segoe UI", 12),
            height=32, command=controller._open_analytics_window,
        )
        self.btn_analytics.pack(fill="x", padx=20, pady=3)

        self.btn_csv = ctk.CTkButton(
            self, text="Export CSV Data", font=ctk.CTkFont("Segoe UI", 12),
            height=32, command=controller._on_export_csv,
        )
        self.btn_csv.pack(fill="x", padx=20, pady=6)

        self.btn_settings = ctk.CTkButton(
            self, text="Settings", font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#2D2D34", hover_color="#3A3A42", height=32,
            command=controller._open_settings,
        )
        self.btn_settings.pack(fill="x", padx=20, pady=9)

        ctk.CTkLabel(
            self, text="v4.0.0",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#45454C",
        ).pack(side="bottom", pady=10)
