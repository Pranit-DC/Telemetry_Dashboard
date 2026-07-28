import customtkinter as ctk
import datetime
from gui.components.chart import BaseChart
from core.analysis.fall_time import TARGET_SAMPLES, US_PER_SAMPLE

class DashboardPage(ctk.CTkFrame):
    """
    Main dashboard page displaying metrics and charts.
    """
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        # Grid layout for Dashboard: 3 rows (metrics, charts, console)
        self.grid_rowconfigure(0, weight=0) # Metrics
        self.grid_rowconfigure(1, weight=1) # Charts
        self.grid_rowconfigure(2, weight=0) # Console
        self.grid_columnconfigure(0, weight=1)
        
        self.cards = {}
        
        self._build_top_bar()
        self._build_charts()
        self._build_console()

    def _build_top_bar(self):
        """Top row of metric cards."""
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        metrics = ["Peak Voltage", "Fall Time", "Avg Fall Time", "Std Dev (σ)", "Min / Max Fall"]
        
        # Equal width columns for metrics
        for i in range(len(metrics)):
            self.frame_top.grid_columnconfigure(i, weight=1)
            
        for i, metric in enumerate(metrics):
            card = ctk.CTkFrame(self.frame_top, fg_color="#1E1E24", corner_radius=12)
            card.grid(row=0, column=i, padx=5, sticky="ew")
            
            lbl_title = ctk.CTkLabel(
                card, text=metric.upper(), font=("Segoe UI", 10, "bold"), text_color="gray"
            )
            lbl_title.pack(pady=(10, 0))
            
            lbl_val = ctk.CTkLabel(
                card, text="--", font=("Segoe UI", 18, "bold")
            )
            lbl_val.pack(pady=(5, 10))
            
            self.cards[metric] = {"frame": card, "title": lbl_title, "value": lbl_val}

    def _build_charts(self):
        """Middle row: single decay chart, full width."""
        self.frame_charts = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_charts.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        self.frame_charts.grid_rowconfigure(0, weight=1)
        self.frame_charts.grid_columnconfigure(0, weight=1)

        # Decay Trace (only chart now — Fall Time Trend removed for simplicity)
        self.chart_trace = BaseChart(
            self.frame_charts,
            title="Decay Trace (Latest Capture)",
            x_label="Time (μs)",
            y_label="Voltage (V)",
        )
        self.chart_trace.grid(row=0, column=0, sticky="nsew")
        self.ax_trace = self.chart_trace.ax
        self.canvas_trace = self.chart_trace.canvas
        self.trace_line, = self.ax_trace.plot([], [], color="#3A7DFF", linewidth=1.5)

        # Every burst is always exactly TARGET_SAMPLES points at a fixed
        # US_PER_SAMPLE spacing (set by the firmware), so the full-trace
        # range is a known constant, not something to infer from whatever
        # data happens to be plotted first. Set it now and lock it in as the
        # toolbar's "Home" view *before* any per-burst zoom is ever applied,
        # so Home reliably zooms out to the complete 2.8ms trace - not to
        # matplotlib's default empty (0,1) view.
        full_trace_max_us = (TARGET_SAMPLES - 1) * US_PER_SAMPLE
        self.ax_trace.set_xlim(0, full_trace_max_us)
        self.ax_trace.set_ylim(0, 3.3)  # matches ADC reference voltage range
        self.chart_trace.toolbar.update()

    def _build_console(self):
        """Bottom row: diagnostics and console."""
        self.frame_console = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_console.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        
        self.frame_console.grid_columnconfigure(0, weight=1)
        self.frame_console.grid_columnconfigure(1, weight=0)
        
        # Log Terminal
        term_frame = ctk.CTkFrame(self.frame_console, fg_color="#1E1E24", corner_radius=10)
        term_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        self.txt_log = ctk.CTkTextbox(
            term_frame, height=100, fg_color="transparent",
            font=("Consolas", 11), text_color="#A9B7C6"
        )
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_log.configure(state="disabled")
        
        # Diagnostics Panel
        diag_frame = ctk.CTkFrame(self.frame_console, fg_color="#1E1E24", corner_radius=10, width=200)
        diag_frame.grid(row=0, column=1, sticky="nsew")
        diag_frame.grid_propagate(False)
        
        lbl_diag = ctk.CTkLabel(
            diag_frame, text="SYSTEM DIAGNOSTICS", font=("Segoe UI", 10, "bold"), text_color="gray"
        )
        lbl_diag.pack(pady=(10, 5), padx=10, anchor="w")
        
        self.lbl_burst_count = ctk.CTkLabel(
            diag_frame, text="Burst Count: 0", font=("Segoe UI", 11)
        )
        self.lbl_burst_count.pack(pady=2, padx=10, anchor="w")
        
        self.lbl_source = ctk.CTkLabel(
            diag_frame, text="Source: SIMULATOR", font=("Segoe UI", 11)
        )
        self.lbl_source.pack(pady=2, padx=10, anchor="w")

    def log_message(self, message):
        """Add a message to the terminal text box."""
        self.txt_log.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {message}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        
    def update_source_status(self, status):
        """Update the diagnostics source label."""
        self.lbl_source.configure(text=f"Source: {status}")