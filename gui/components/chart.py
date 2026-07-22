import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

class BaseChart(ctk.CTkFrame):
    """A reusable, Matplotlib chart wrapper with built-in toolbar."""
    
    def __init__(self, master, figsize=(6, 4), dpi=100, facecolor="#1A1A1E", subplot_facecolor="#121214", show_toolbar=True, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.figure = Figure(figsize=figsize, dpi=dpi, facecolor=facecolor)
        self.ax = self.figure.add_subplot(111, facecolor=subplot_facecolor)
        
        # Embed the canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        
        if show_toolbar:
            self.control_bar = ctk.CTkFrame(self, fg_color="transparent")
            self.control_bar.pack(fill="x", side="bottom", padx=5, pady=2)
            
            # Matplotlib Navigation Toolbar (pan, zoom, save, etc.)
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.control_bar)
            self.toolbar.update()
            self.toolbar.config(background="#1A1A1E", bd=0)
            self.toolbar._message_label.config(
                background="#1A1A1E", foreground="#7F7F8C", font=("Segoe UI", 9)
            )
            self.toolbar.pack(side="bottom", fill="x", padx=16, pady=(4, 12))
            
            self.canvas_widget.pack(fill="both", expand=True, padx=5, pady=(5, 2))
        else:
            self.canvas_widget.pack(fill="both", expand=True, padx=5, pady=5)
            
    def draw(self):
        self.canvas.draw()
