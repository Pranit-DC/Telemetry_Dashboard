import customtkinter as ctk

class SettingsWindow(ctk.CTkToplevel):
    """
    Settings dialog window.
    """
    def __init__(self, parent, config, on_save_callback):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x400")
        self.minsize(500, 400)
        
        self.config = config
        self.on_save_callback = on_save_callback
        
        self._build_ui()
        self._populate_fields()
        
    def _build_ui(self):
        """Build settings UI with tabs."""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        
        # Tabs
        self.tab_conn = self.tabview.add("Connection")
        self.tab_ui = self.tabview.add("UI & Graphing")
        self.tab_paths = self.tabview.add("File Paths")
        
        # Connection Tab
        self.lbl_device = ctk.CTkLabel(self.tab_conn, text="BLE Device Name:")
        self.lbl_device.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_device = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_device.grid(row=0, column=1, padx=10, pady=10)
        
        self.lbl_com = ctk.CTkLabel(self.tab_conn, text="COM Port:")
        self.lbl_com.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_com = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_com.grid(row=1, column=1, padx=10, pady=10)
        
        self.lbl_baud = ctk.CTkLabel(self.tab_conn, text="Baud Rate:")
        self.lbl_baud.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.combo_baud = ctk.CTkComboBox(self.tab_conn, values=["9600", "19200", "38400", "57600", "115200"], width=200)
        self.combo_baud.grid(row=2, column=1, padx=10, pady=10)
        
        self.lbl_timeout = ctk.CTkLabel(self.tab_conn, text="BLE Timeout (s):")
        self.lbl_timeout.grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.entry_timeout = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_timeout.grid(row=3, column=1, padx=10, pady=10)
        
        # UI & Graphing Tab
        self.lbl_win_sec = ctk.CTkLabel(self.tab_ui, text="Graph Time Window (s):")
        self.lbl_win_sec.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_win_sec = ctk.CTkEntry(self.tab_ui, width=200)
        self.entry_win_sec.grid(row=0, column=1, padx=10, pady=10)
        
        self.lbl_line_thick = ctk.CTkLabel(self.tab_ui, text="Line Thickness:")
        self.lbl_line_thick.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_line_thick = ctk.CTkEntry(self.tab_ui, width=200)
        self.entry_line_thick.grid(row=1, column=1, padx=10, pady=10)
        
        self.lbl_scale = ctk.CTkLabel(self.tab_ui, text="UI Scale (0.5 - 3.0):")
        self.lbl_scale.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.slider_scale = ctk.CTkSlider(self.tab_ui, from_=0.5, to=3.0, number_of_steps=25)
        self.slider_scale.grid(row=2, column=1, padx=10, pady=10)
        self.lbl_scale_val = ctk.CTkLabel(self.tab_ui, text="1.0")
        self.lbl_scale_val.grid(row=2, column=2, padx=(0, 10))
        self.slider_scale.configure(command=lambda v: self.lbl_scale_val.configure(text=f"{v:.1f}"))
        
        # File Paths Tab
        self.lbl_db_dir = ctk.CTkLabel(self.tab_paths, text="Database Directory:")
        self.lbl_db_dir.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_db_dir = ctk.CTkEntry(self.tab_paths, width=200)
        self.entry_db_dir.grid(row=0, column=1, padx=10, pady=10)
        
        self.lbl_log_dir = ctk.CTkLabel(self.tab_paths, text="Logs Directory:")
        self.lbl_log_dir.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_log_dir = ctk.CTkEntry(self.tab_paths, width=200)
        self.entry_log_dir.grid(row=1, column=1, padx=10, pady=10)
        
        # Save / Cancel Buttons
        self.frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_btns.pack(fill="x", padx=20, pady=10)
        
        self.btn_save = ctk.CTkButton(self.frame_btns, text="Save Settings", fg_color="#2EA44F", hover_color="#2c974b", command=self._save)
        self.btn_save.pack(side="right", padx=(10, 0))
        
        self.btn_cancel = ctk.CTkButton(self.frame_btns, text="Cancel", fg_color="transparent", border_width=1, command=self.destroy)
        self.btn_cancel.pack(side="right")
        
    def _populate_fields(self):
        """Populate inputs from current config."""
        self.entry_device.insert(0, getattr(self.config, 'ble_device_name', 'GIGA_WORKSTATION'))
        self.entry_com.insert(0, getattr(self.config, 'com_port', 'COM15'))
        self.combo_baud.set(str(getattr(self.config, 'baud_rate', '115200')))
        self.entry_timeout.insert(0, str(getattr(self.config, 'ble_timeout', 10.0)))
        
        self.entry_win_sec.insert(0, str(getattr(self.config, 'graph_display_window_sec', 10.0)))
        self.entry_line_thick.insert(0, str(getattr(self.config, 'chart_line_thickness', 1.5)))
        
        ui_scale = getattr(self.config, 'ui_scale', 1.0)
        self.slider_scale.set(ui_scale)
        self.lbl_scale_val.configure(text=f"{ui_scale:.1f}")
        
        self.entry_db_dir.insert(0, getattr(self.config, 'sqlite_database_directory', 'data/db'))
        self.entry_log_dir.insert(0, getattr(self.config, 'system_logs_directory', 'data/logs'))
        
    def _save(self):
        """Save settings and call callback."""
        settings = {
            'ble_device_name': self.entry_device.get(),
            'com_port': self.entry_com.get(),
            'baud_rate': int(self.combo_baud.get()),
            'ble_timeout': float(self.entry_timeout.get() or 10.0),
            'graph_display_window_sec': float(self.entry_win_sec.get() or 10.0),
            'chart_line_thickness': float(self.entry_line_thick.get() or 1.5),
            'ui_scale': float(self.slider_scale.get()),
            'sqlite_database_directory': self.entry_db_dir.get(),
            'system_logs_directory': self.entry_log_dir.get()
        }
        self.on_save_callback(settings)
        self.destroy()
