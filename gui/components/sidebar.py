import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    """
    Sidebar component for navigation and control.
    """
    def __init__(self, master, on_start, on_stop, on_clear, 
                 on_manage_sessions, on_analytics, on_export, on_settings):
        super().__init__(master, width=250, corner_radius=0, fg_color="#1A1A1E")
        
        self.grid_rowconfigure(6, weight=1)  # Spacer
        
        # Title
        self.lbl_title = ctk.CTkLabel(
            self, text="Telemetry Dashboard", font=("Segoe UI", 20, "bold")
        )
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Status
        self.lbl_status = ctk.CTkLabel(
            self, text="Status: DISCONNECTED", font=("Segoe UI", 12), text_color="#D73A49"
        )
        self.lbl_status.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        # Controls
        # This button triples as Start / Pause / Resume - see set_run_state().
        # Stop (separate, below) always fully ends the session regardless
        # of whether the stream is currently running or paused.
        self.btn_start = ctk.CTkButton(
            self, text="Start Acquisition", fg_color="#006f3c", hover_color="#008748",
            corner_radius=16, width=180, height=34, command=on_start
        )
        self.btn_start.grid(row=2, column=0, padx=20, pady=(10, 5))
        
        self.btn_stop = ctk.CTkButton(
            self, text="Stop", fg_color="#bf212f", hover_color="#e62737",
            corner_radius=16, width=180, height=34, command=on_stop, state="disabled"
        )
        self.btn_stop.grid(row=3, column=0, padx=20, pady=5)
        
        self.btn_clear = ctk.CTkButton(
            self, text="Clear Buffer", fg_color="#264b96", hover_color="#2e5bb6",
            corner_radius=16, width=180, height=34, command=on_clear
        )
        self.btn_clear.grid(row=4, column=0, padx=20, pady=5)
        
        # Historical Playback
        self.frame_playback = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_playback.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        
        self.lbl_playback = ctk.CTkLabel(
            self.frame_playback, text="HISTORICAL PLAYBACK", font=("Segoe UI", 10, "bold")
        )
        self.lbl_playback.pack(anchor="w", pady=(0, 5))
        
        playback_controls = ctk.CTkFrame(self.frame_playback, fg_color="transparent")
        playback_controls.pack(fill="x")
        
        self.btn_manage = ctk.CTkButton(
            playback_controls, text="Manage Sessions", fg_color="#242424", hover_color="#363636", 
            corner_radius=20, width=140, height=36, command=on_manage_sessions
        )
        self.btn_manage.pack(fill="x", expand=True, pady=5)
        
        # Bottom Actions
        self.btn_analytics = ctk.CTkButton(
            self, text="Analytics", fg_color="#242424", hover_color="#363636",
            corner_radius=20, width=180, height=36, command=on_analytics
        )
        self.btn_analytics.grid(row=7, column=0, padx=20, pady=(10, 5))
        
        self.btn_export = ctk.CTkButton(
            self, text="Export CSV", fg_color="#242424", hover_color="#363636",
            corner_radius=20, width=180, height=36, command=on_export
        )
        self.btn_export.grid(row=8, column=0, padx=20, pady=5)
        
        self.btn_settings = ctk.CTkButton(
            self, text="Settings", fg_color="#242424", hover_color="#363636",
            corner_radius=20, width=180, height=36, command=on_settings
        )
        self.btn_settings.grid(row=9, column=0, padx=20, pady=(5, 20))
        
        self.lbl_version = ctk.CTkLabel(
            self, text="v5.0.0", font=("Segoe UI", 10), text_color="gray"
        )
        self.lbl_version.grid(row=10, column=0, pady=(0, 10))

    def update_status(self, text, color):
        self.lbl_status.configure(text=text, text_color=color)

    def set_run_state(self, run_state: str):
        """Update button labels/colors for one of: 'stopped', 'running', 'paused'.

        The Start button doubles as Start/Pause/Resume; Stop is only ever
        enabled while a session exists (running or paused), and always
        fully ends it.
        """
        if run_state == 'running':
            self.btn_start.configure(text="Pause", fg_color="#8a6d1a", hover_color="#a6821f")
            self.btn_stop.configure(state="normal")
        elif run_state == 'paused':
            self.btn_start.configure(text="Resume", fg_color="#006f3c", hover_color="#008748")
            self.btn_stop.configure(state="normal")
        else:  # 'stopped'
            self.btn_start.configure(text="Start Acquisition", fg_color="#006f3c", hover_color="#008748")
            self.btn_stop.configure(state="disabled")