# Module 5: Presentation Layer, Visualization & Main Entry Point

Welcome to the final module! In this module, you will build the presentation layer using CustomTkinter and Matplotlib. You will learn how to build a 50/50 dual-chart dashboard, implement interactive trend clicks (drill-down), respect user pan/zoom states, and write a crash-safe application entry point.

---

## 🎯 Learning Objectives
By the end of this module, you will understand:
- How to embed Matplotlib figures into CustomTkinter using `FigureCanvasTkAgg`.
- How to build a 50/50 balanced layout using Tkinter's `grid_columnconfigure(..., weight=1)`.
- How to implement **Interactive Drill-Down**: Clicking a data point on the trend chart locks the decay trace view onto that specific historical burst.
- How to preserve user **Pan & Zoom** states so live data updates don't overwrite user interaction.
- How to handle OS window closing cleanly via `WM_DELETE_WINDOW` protocol.

---

## 1. Step 1: Matplotlib Canvas Wrapper (`gui/components/chart.py`)

### 💡 Mentor's Guidance on Embedding Matplotlib in Tkinter
Matplotlib's standard `plt.show()` creates a separate pop-up window. In a desktop GUI app, we embed the Matplotlib canvas inside a Tkinter widget:

```python
self.figure = Figure(figsize=figsize, dpi=dpi, facecolor="#1A1A1E")
self.ax = self.figure.add_subplot(111, facecolor="#121214")
self.canvas = FigureCanvasTkAgg(self.figure, master=self)
self.canvas_widget = self.canvas.get_tk_widget()
```

---

## 2. Step 2: Dual Chart Layout (`gui/dashboard/page.py`)

### Layout Requirement:
- Top Row: 5 Metric Cards (`Peak Voltage`, `Fall Time`, `Avg Fall Time`, `Burst Count`, `Source Status`).
- Middle Row: 50% Decay Trace Chart (Left) + 50% Fall Time Trend Chart (Right).
- Bottom Row: Log Console Terminal + Diagnostics Box.

### 💡 Mentor's Tip on Equal Column Weights
In Tkinter, if you don't configure weights, widgets collapse to their minimum size. Set equal weights for a 50/50 split:
```python
self.frame_charts.grid_columnconfigure(0, weight=1) # Left Chart (50%)
self.frame_charts.grid_columnconfigure(1, weight=1) # Right Chart (50%)
```

---

## 3. Step 3: Graph Renderer with Pan/Zoom Locking (`gui/dashboard/graph_renderer.py`)

### ⚠️ Pitfall: Overwriting User Pan/Zoom
If you call `ax.autoscale_view()` every 100 milliseconds, and the user tries to zoom into a specific feature, the graph will snap back and override them!

### The Solution:
Check if Matplotlib's autoscaling is active before forcing `relim()` / `autoscale_view()`:
```python
if self.page.ax_trace.get_autoscalex_on() and self.page.ax_trace.get_autoscaley_on():
    self.page.ax_trace.relim()
    self.page.ax_trace.autoscale_view()
```
When the user uses the Pan or Zoom tools in the Matplotlib toolbar, Matplotlib automatically turns autoscaling off (`False`), so your live updates update the line data *without* resetting their view!

---

## 4. Step 4: Main Window & Trend Drill-Down (`gui/app.py`)

### Interactive Drill-Down Click Logic:
Connect Matplotlib's `button_press_event` on the trend canvas to a callback in `app.py`:
```python
self.dashboard_page.canvas_trend.mpl_connect('button_press_event', self._on_trend_click)
```

Inside `_on_trend_click`:
1. Read `event.xdata` (the clicked burst index).
2. Calculate offset relative to the rolling 20 window.
3. Lock `renderer.locked_burst = clicked_burst`.
4. Update trace title to `Decay Trace (Burst #X)`.

### Memory Leak Prevention:
Cap `self.burst_history` at 1000 items during polling loop:
```python
if len(self.burst_history) > 1000:
    self.burst_history = self.burst_history[-1000:]
```

---

## 5. Step 5: Safe Window Close Protocol (`main.py`)

### ⚠️ Pitfall: Zombie Threads & Corrupt DB Connections
If the user closes the window by clicking the `X` button, Python threads or SQLite file handles might stay open in the background.

Use Tkinter's `WM_DELETE_WINDOW` protocol with a safe `on_close` handler:
```python
import customtkinter as ctk
from gui.app import TelemetryDashboard

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = TelemetryDashboard()
    
    def on_close():
        try:
            app.cleanup()  # Disconnects hardware, closes SQLite & CSV logger
        finally:
            app.destroy()  # Destroys Tkinter window
            
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()

if __name__ == "__main__":
    main()
```

---

## 📖 Reference Implementation

<details>
<summary>Click to view reference implementation for gui/components/chart.py</summary>

```python
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

class BaseChart(ctk.CTkFrame):
    def __init__(self, master, figsize=(8, 4), dpi=100, facecolor="#1A1A1E", subplot_facecolor="#121214", show_toolbar=True, title=None, x_label=None, y_label=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.figure = Figure(figsize=figsize, dpi=dpi, facecolor=facecolor)
        self.ax = self.figure.add_subplot(111, facecolor=subplot_facecolor)
        
        if title:
            self.ax.set_title(title, color="white")
        if x_label:
            self.ax.set_xlabel(x_label, color="white")
        if y_label:
            self.ax.set_ylabel(y_label, color="white")
        self.ax.tick_params(colors="white")
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        
        if show_toolbar:
            self.control_bar = ctk.CTkFrame(self, fg_color="transparent")
            self.control_bar.pack(fill="x", side="bottom", padx=(0, 15), pady=2)
            
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.control_bar)
            self.toolbar.update()
            self.toolbar.config(background="#1a1a1e", bd=0)
            self.toolbar._message_label.config(
                background="#1A1A1E", foreground="#7F7F8C", font=("Segoe UI", 9)
            )
            self.toolbar.pack(side="left", fill="x", expand=True, padx=(16, 0), pady=(4, 12))
            
            self.canvas_widget.pack(fill="both", expand=True, padx=5, pady=(5, 2))
        else:
            self.canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)
            
    def draw(self):
        self.canvas.draw()
```
</details>

<details>
<summary>Click to view reference implementation for gui/dashboard/graph_renderer.py</summary>

```python
class GraphRenderer:
    def __init__(self, dashboard_page):
        self.page = dashboard_page
        self.locked_burst = None
    
    def refresh(self, latest_burst, burst_history):
        if latest_burst:
            display_burst = self.locked_burst if self.locked_burst else latest_burst
            self._update_trace_chart(display_burst)
            self._update_metric_cards(display_burst, burst_history)
        if burst_history:
            self._update_trend_chart(burst_history)
        self._update_diagnostics(burst_history)
    
    def _update_trace_chart(self, burst):
        indices = list(range(len(burst.trace_points)))
        voltages = [p.voltage for p in burst.trace_points]
        self.page.trace_line.set_data(indices, voltages)
        
        if self.page.ax_trace.get_autoscalex_on() and self.page.ax_trace.get_autoscaley_on():
            self.page.ax_trace.relim()
            self.page.ax_trace.autoscale_view()
        self.page.canvas_trace.draw_idle()
    
    def _update_trend_chart(self, burst_history):
        window_size = 20
        start_idx = max(0, len(burst_history) - window_size)
        display_history = burst_history[start_idx:]
        
        indices = list(range(start_idx, len(burst_history)))
        fall_times = [b.fall_time_us for b in display_history]
        self.page.trend_line.set_data(indices, fall_times)
        
        if self.page.ax_trend.get_autoscalex_on() and self.page.ax_trend.get_autoscaley_on():
            self.page.ax_trend.relim()
            self.page.ax_trend.autoscale_view()
        self.page.canvas_trend.draw_idle()
    
    def _update_metric_cards(self, burst, history):
        cards = self.page.cards
        cards['Peak Voltage']['value'].configure(text=f'{burst.peak_voltage:.3f} V')
        cards['Fall Time']['value'].configure(text=f'{burst.fall_time_us:.1f} μs')
        cards['Avg Fall Time']['value'].configure(text=f'{burst.avg_fall_time_us:.1f} μs')
        cards['Burst Count']['value'].configure(text=str(len(history)))
    
    def _update_diagnostics(self, history):
        self.page.lbl_burst_count.configure(text=f'Burst Count: {len(history)}')
    
    def clear(self):
        self.page.trace_line.set_data([], [])
        self.page.trend_line.set_data([], [])
        self.page.canvas_trace.draw_idle()
        self.page.canvas_trend.draw_idle()
```
</details>

🎉 **Congratulations!** Once you complete Module 5, your BARC Photodetector Telemetry Dashboard (v5.0.0) is fully functional, crash-safe, and ready for offline deployment!
