import customtkinter as ctk
from tkinter import filedialog, ttk
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages


class ReportsTab(ctk.CTkFrame):
    """Summary table of all bursts + one-click PDF export with charts embedded."""

    def __init__(self, parent, db, burst_history):
        super().__init__(parent, fg_color="transparent")
        self.burst_history = burst_history

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.status_label = ctk.CTkLabel(top_bar, text="")
        self.status_label.pack(side="left")

        export_btn = ctk.CTkButton(top_bar, text="Export Report (PDF)", command=self._export_pdf)
        export_btn.pack(side="right")

        self._build_table()

    def _build_table(self):
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ("burst_id", "timestamp", "peak_voltage", "fall_time_us", "avg_fall_time_us")
        headers = ("Burst ID", "Timestamp", "Peak Voltage (V)", "Fall Time (us)", "Avg Fall Time (us)")

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for col, header in zip(columns, headers):
            self.tree.heading(col, text=header)
            self.tree.column(col, width=140, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for burst in self.burst_history:
            ts = burst.timestamp.strftime("%H:%M:%S") if isinstance(burst.timestamp, datetime) else str(burst.timestamp)
            self.tree.insert("", "end", values=(
                burst.burst_id,
                ts,
                f"{burst.peak_voltage:.4f}",
                f"{burst.fall_time_us:.2f}",
                f"{burst.avg_fall_time_us:.2f}",
            ))

    def _export_pdf(self):
        if not self.burst_history:
            self.status_label.configure(text="No burst data to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"telemetry_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
        if not filepath:
            return

        try:
            with PdfPages(filepath) as pdf:
                self._add_summary_table_page(pdf)
                self._add_overview_page(pdf)
                self._add_statistics_page(pdf)
                self._add_signal_page(pdf)
            self.status_label.configure(text=f"Report saved to {filepath}")
        except Exception as e:
            self.status_label.configure(text=f"Export failed: {e}")

    def _add_summary_table_page(self, pdf):
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.set_title("Telemetry Session Report — Summary", fontsize=14, pad=20)

        columns = ["Burst ID", "Timestamp", "Peak V", "Fall Time (us)", "Avg Fall Time (us)"]
        rows = []
        for burst in self.burst_history:
            ts = burst.timestamp.strftime("%H:%M:%S") if isinstance(burst.timestamp, datetime) else str(burst.timestamp)
            rows.append([
                burst.burst_id, ts,
                f"{burst.peak_voltage:.4f}",
                f"{burst.fall_time_us:.2f}",
                f"{burst.avg_fall_time_us:.2f}",
            ])

        # Cap rows on one page; keep it simple rather than paginating the table
        max_rows = 35
        table_rows = rows[:max_rows]
        table = ax.table(cellText=table_rows, colLabels=columns, loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.4)

        if len(rows) > max_rows:
            ax.text(0.5, 0.02, f"... {len(rows) - max_rows} more bursts not shown ...",
                     ha="center", transform=ax.transAxes, fontsize=8)

        pdf.savefig(fig)

    def _add_overview_page(self, pdf):
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        burst_ids = [b.burst_id for b in self.burst_history]
        peaks = [b.peak_voltage for b in self.burst_history]
        ax.plot(burst_ids, peaks, marker="o")
        ax.set_title("Peak Voltage per Burst")
        ax.set_xlabel("Burst ID")
        ax.set_ylabel("Peak Voltage (V)")
        pdf.savefig(fig)

    def _add_statistics_page(self, pdf):
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        fall_times = [b.fall_time_us for b in self.burst_history if b.fall_time_us > 0]
        if fall_times:
            bins = min(20, max(5, len(fall_times) // 2))
            ax.hist(fall_times, bins=bins)
        ax.set_title("Fall Time Distribution")
        ax.set_xlabel("Fall Time (us)")
        ax.set_ylabel("Count")
        pdf.savefig(fig)

    def _add_signal_page(self, pdf):
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        recent = self.burst_history[-10:]
        for burst in recent:
            times = [p.time_us for p in burst.trace_points]
            volts = [p.voltage for p in burst.trace_points]
            ax.plot(times, volts, linewidth=1, alpha=0.7, label=f"Burst {burst.burst_id}")
        ax.set_title(f"Last {len(recent)} Traces (Overlay)")
        ax.set_xlabel("Time (us)")
        ax.set_ylabel("Voltage (V)")
        if len(recent) <= 10:
            ax.legend(fontsize=7)
        pdf.savefig(fig)