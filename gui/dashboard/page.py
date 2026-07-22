# Dashboard page layout: the main content area of the application.
# Contains three sections stacked vertically:
#   1. Analytics metric cards (top)
#   2. Live chart with matplotlib (middle, takes most space)
#   3. Log terminal + diagnostics panel (bottom)

import customtkinter as ctk
import matplotlib
import matplotlib.ticker as ticker
from config import AVAILABLE_CHANNELS, CHANNEL_COLORS
from gui.components import BaseChart

matplotlib.use("TkAgg")


class DashboardPage(ctk.CTkFrame):
    """The main content panel that shows the live chart, metrics, and log output."""

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="#121214", corner_radius=0)
        self.controller = controller

        # Three rows: metrics (fixed), chart (expandable), diagnostics (fixed)
        for row, weight in [(0, 0), (1, 1), (2, 0)]:
            self.grid_rowconfigure(row, weight=weight)
        self.grid_columnconfigure(0, weight=1)

        self._build_metrics_panel()
        self._build_graph_panel()
        self._build_diagnostics_panel()

    def _build_metrics_panel(self):
        """Build the row of analytics cards at the top."""
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        self.cards = {}

        metrics = [
            ("Peak-to-Peak", "0.00 V"),
            ("Frequency", "0.0 Hz"),
            ("Max Jitter (Δt)", "0.0 ms"),
            ("Rise Time", "0.00 s"),
            ("Peak Time", "0.00 s"),
        ]
        for idx, (title, default) in enumerate(metrics):
            panel.grid_columnconfigure(idx, weight=1, uniform="metrics")
            card = ctk.CTkFrame(
                panel, fg_color="#1A1A1E",
                border_width=1, border_color="#25252A", corner_radius=8,
            )
            card.grid(row=0, column=idx, sticky="nsew", padx=4)

            lbl_title = ctk.CTkLabel(
                card, text=f"{title.upper()} (CH1)",
                font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color="#7F7F8C",
            )
            lbl_title.pack(anchor="w", padx=14, pady=(12, 2))

            lbl_val = ctk.CTkLabel(
                card, text=default,
                font=ctk.CTkFont("Consolas", 22, "bold"), text_color="#FFFFFF",
            )
            lbl_val.pack(anchor="w", padx=14, pady=(0, 12))

            self.cards[title] = {"value": lbl_val, "title": lbl_title}

    def _build_graph_panel(self):
        """Build the matplotlib chart area using the reusable BaseChart component."""
        wrapper = ctk.CTkFrame(
            self, fg_color="#1A1A1E",
            border_width=1, border_color="#25252A", corner_radius=12,
        )
        wrapper.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)
        wrapper.pack_propagate(False)

        # Instantiate our reusable BaseChart component
        self.chart = BaseChart(wrapper, figsize=(7, 3.8), show_toolbar=True)
        self.chart.pack(fill="both", expand=True, padx=16, pady=(16, 2))

        self.figure = self.chart.figure
        self.canvas = self.chart.canvas
        self.ax = self.chart.ax
        self.toolbar = self.chart.toolbar

        # Chart styling
        self.ax.set_title(
            "Live Multi-Channel Sensor Response",
            color="#E0E0E6", fontsize=15, pad=20,
            fontweight="bold", fontname="Segoe UI",
        )
        self.ax.set_xlabel(
            "Elapsed Time (Seconds)",
            color="#7F7F8C", fontsize=10, fontname="Segoe UI", labelpad=8,
        )
        self.ax.set_ylabel(
            "Amplitude (Volts)",
            color="#7F7F8C", fontsize=10, fontname="Segoe UI", labelpad=8,
        )
        self.ax.tick_params(colors="#FFFFFF", labelsize=9)
        self.ax.grid(True, color="#222226", linestyle="-", linewidth=0.8)
        self.ax.xaxis.set_major_locator(ticker.MultipleLocator(1.0))
        for spine in ["top", "right", "left", "bottom"]:
            self.ax.spines[spine].set_color("#25252A")

        # "Reset Live View" button - snaps back to auto-scrolling mode
        self.btn_reset_view = ctk.CTkButton(
            self.chart.toolbar, text="Reset Live View",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color="#3A7DFF", hover_color="#2A65D4", text_color="#FFFFFF",
            height=26, corner_radius=14,
            command=self._reset_to_live_view,
        )
        self.btn_reset_view.pack(side="left", padx=(12, 6), pady=4)

        # Normalize toggle switch
        self.normalize_switch = ctk.CTkSwitch(
            self.chart.toolbar, text="Normalize",
            command=self.controller._on_normalization_changed,
        )
        self.normalize_switch.pack(side="left", padx=(12, 6), pady=4)

        # Create empty plot lines for each channel (data gets added later)
        self.plot_lines = {}
        for ch in AVAILABLE_CHANNELS:
            line, = self.ax.plot(
                [], [], color=CHANNEL_COLORS[ch],
                linewidth=2.5, antialiased=True, label=ch,
            )
            self.plot_lines[ch] = line

        self.ax.legend(
            facecolor="#16161A", edgecolor="#25252A", labelcolor="#E0E0E6",
            loc="upper right", framealpha=0.9, fontsize=9,
        )

    def _reset_to_live_view(self):
        """Disable pan/zoom mode and snap back to the live auto-scrolling view."""
        if hasattr(self, "toolbar"):
            mode = self.toolbar.mode.name
            if mode == "PAN":
                self.toolbar.pan()
            elif mode == "ZOOM":
                self.toolbar.zoom()

        if hasattr(self.controller, "_refresh_dashboard"):
            self.controller._refresh_dashboard()
            self.controller.log_message("View reset: live scrolling restored.")

    def _build_diagnostics_panel(self):
        """Build the bottom panel with log terminal and diagnostics info."""
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=2, column=0, sticky="nsew", padx=20, pady=(5, 20))
        panel.grid_columnconfigure(0, weight=3)
        panel.grid_columnconfigure(1, weight=1)

        # Log terminal (shows timestamped messages)
        self.log_terminal = ctk.CTkTextbox(
            panel, fg_color="#1A1A1E", border_width=1, height=115,
            border_color="#25252A", font=ctk.CTkFont("Consolas", 13),
            text_color="#A8FFB2", corner_radius=8,
        )
        self.log_terminal.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.log_terminal.configure(state="disabled")

        # Diagnostics panel (dropped frames + battery)
        diag = ctk.CTkFrame(
            panel, fg_color="#1A1A1E", border_width=1,
            border_color="#25252A", corner_radius=8, height=115,
        )
        diag.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        diag.pack_propagate(False)

        ctk.CTkLabel(
            diag, text="DIAGNOSTICS SYSTEMS",
            font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color="#7F7F8C",
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.lbl_loss = ctk.CTkLabel(
            diag, text="Dropped Frames: 0",
            font=ctk.CTkFont("Consolas", 13), text_color="#E0E0E6",
        )
        self.lbl_battery = ctk.CTkLabel(
            diag, text="Battery: 100%",
            font=ctk.CTkFont("Consolas", 13), text_color="#2EA44F",
        )
        self.lbl_loss.pack(anchor="w", padx=14, pady=2)
        self.lbl_battery.pack(anchor="w", padx=14, pady=2)
