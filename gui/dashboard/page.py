import customtkinter as ctk
import datetime
from gui.components.chart import BaseChart

class DashboardPage(ctk.CTkFrame):
    """
    Main dashboard page displaying metrics and charts.
    """
    def __init__(self, master, on_reset_view):
        super().__init__(master, fg_color="transparent")
        
        # Grid layout for Dashboard: 3 rows (metrics, charts, console)
        self.grid_rowconfigure(0, weight=0) # Metrics
        self.grid_rowconfigure(1, weight=1) # Charts
        self.grid_rowconfigure(2, weight=0) # Console
        self.grid_columnconfigure(0, weight=1)
        
        self.cards = {}
        
        self._build_top_bar()
        self._build_charts(on_reset_view)
        self._build_console()

    def _build_top_bar(self):
        """Top row of metric cards."""
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        metrics = ["Peak Voltage", "Fall Time", "Avg Fall Time", "Burst Count", "Source Status"]
        
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

    def _build_charts(self, on_reset_view):
        """Middle row of charts."""
        self.frame_charts = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_charts.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        self.frame_charts.grid_rowconfigure(0, weight=1)
        self.frame_charts.grid_columnconfigure(0, weight=1) # Left chart (50%)
        self.frame_charts.grid_columnconfigure(1, weight=1) # Right chart (50%)
        
        # Left Chart: Decay Trace
        self.chart_trace = BaseChart(
            self.frame_charts,
            title="Decay Trace (Latest Capture)",
            x_label="Sample Index",
            y_label="Voltage (V)",
        )
        self.chart_trace.grid(row=0, column=0, sticky="nsew")
        self.ax_trace = self.chart_trace.ax
        self.canvas_trace = self.chart_trace.canvas
        self.trace_line, = self.ax_trace.plot([], [], color="#3A7DFF", linewidth=1.5)
        
        # Right Chart: Measurement Trend
        self.chart_trend = BaseChart(
            self.frame_charts,
            title="Fall Time Trend",
            x_label="Burst #",
            y_label="Fall Time (μs)"
        )
        self.chart_trend.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.ax_trend = self.chart_trend.ax
        self.canvas_trend = self.chart_trend.canvas
        self.trend_line, = self.ax_trend.plot([], [], color="#2EA44F", linewidth=1.5)
        
        # Reset button inside the chart's bottom control bar
        btn_reset = ctk.CTkButton(
            self.chart_trace.control_bar, text="Reset Live View", width=120, height=28,
            corner_radius=14, font=("Segoe UI", 11, "bold"),
            fg_color="#363636", hover_color="#1F1F1F", 
            text_color="white",
            command=on_reset_view
        )
        btn_reset.pack(side="right", padx=(10, 16), pady=(4, 12))

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
        """Update Source Status metric and Diagnostics label."""
        self.cards['Source Status']['value'].configure(text=status)
        self.lbl_source.configure(text=f"Source: {status}")
