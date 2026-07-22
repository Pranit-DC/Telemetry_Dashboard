# Settings window for configuring BLE, graph, and storage parameters.
# Opens as a modal dialog with three tabs: BLE Hardware, UI & Graphing, Storage.

import os
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
import config


class SettingsWindow(ctk.CTkToplevel):
    """Configuration dialog for modifying dashboard settings."""

    def __init__(self, parent, db_manager, on_save_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.db = db_manager
        self.on_save_callback = on_save_callback

        self.title("System Configuration Panel")
        self.geometry("720x580")
        self.minsize(700, 540)
        # Configure transient window settings for Linux compatibility (avoids hiding under main app)
        self.transient(parent)
        self.after(100, self.lift)
        self.after(100, self.focus_force)
        self.after(100, self.grab_set)

        # Load the current config from the JSON file
        self.current_config = config.load_persistent_config()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self._build_layout()
        self._build_footer()
        self._populate_fields()
        self._select_tab("ble")

    def _build_layout(self):
        """Build the left nav sidebar and the right content panes."""
        # Left navigation sidebar
        nav = ctk.CTkFrame(self, width=180, fg_color="#141416", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew", rowspan=2)
        nav.grid_propagate(False)

        ctk.CTkLabel(
            nav, text="SETTINGS",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color="#5D5D68",
        ).pack(anchor="w", padx=20, pady=(25, 15))

        # Tab buttons
        tab_specs = [
            ("btn_tab_ble", "📡 BLE Hardware", "ble"),
            ("btn_tab_ui", "📉 UI & Graphing", "ui"),
            ("btn_tab_storage", "💾 Storage Engines", "storage"),
        ]
        for attr_name, text, tab_key in tab_specs:
            btn = ctk.CTkButton(
                nav, text=text, anchor="w", height=38, corner_radius=8,
                fg_color="transparent", text_color="#A5A5B2",
                hover_color="#1C1C21", font=ctk.CTkFont("Segoe UI", 12),
                command=lambda k=tab_key: self._select_tab(k),
            )
            btn.pack(fill="x", padx=12, pady=3)
            setattr(self, attr_name, btn)

        # Right content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=25, pady=(20, 10))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._build_ble_pane()
        self._build_ui_pane()
        self._build_storage_pane()

    def _select_tab(self, tab):
        """Show the selected tab pane and highlight its nav button."""
        # Hide all panes
        self.pane_ble.grid_remove()
        self.pane_ui.grid_remove()
        self.pane_storage.grid_remove()

        # Reset all tab button styles
        for btn in [self.btn_tab_ble, self.btn_tab_ui, self.btn_tab_storage]:
            btn.configure(fg_color="transparent", text_color="#A5A5B2", hover_color="#1C1C21")

        # Show the selected pane and highlight its button
        pane_map = {"ble": self.pane_ble, "ui": self.pane_ui, "storage": self.pane_storage}
        btn_map = {"ble": self.btn_tab_ble, "ui": self.btn_tab_ui, "storage": self.btn_tab_storage}

        pane_map[tab].grid(row=0, column=0, sticky="nsew")
        btn_map[tab].configure(fg_color="#3A7DFF", text_color="#FFFFFF", hover_color="#3A7DFF")

    def _build_ble_pane(self):
        """BLE Hardware settings: device name and connection timeout."""
        self.pane_ble = ctk.CTkFrame(self.content, fg_color="transparent")
        card = ctk.CTkFrame(self.pane_ble, fg_color="#141416", corner_radius=12)
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Hardware Bus Connectivity Protocols", font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color="#FFFFFF").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(card, text="Manage BLE device targeting and polling parameters.", font=ctk.CTkFont("Segoe UI", 12), text_color="#6D6D78").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        ctk.CTkLabel(card, text="Target Device Name / MAC Address", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=2, column=0, sticky="w", padx=20, pady=(5, 5))
        self.ent_ble_id = ctk.CTkEntry(card, fg_color="#1C1C21", border_color="#2D2D34", corner_radius=8, height=38, font=ctk.CTkFont("Segoe UI", 12))
        self.ent_ble_id.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))

        ctk.CTkLabel(card, text="Connection Attempt Timeout Window", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=4, column=0, sticky="w", padx=20, pady=(5, 5))

        slider_row = ctk.CTkFrame(card, fg_color="transparent")
        slider_row.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 25))
        slider_row.grid_columnconfigure(0, weight=1)

        self.sld_timeout = ctk.CTkSlider(
            slider_row, from_=5, to=30, number_of_steps=25, height=16,
            button_color="#3A7DFF", button_hover_color="#2A6DDF",
            command=lambda v: self.lbl_timeout_val.configure(text=f"{int(v)}s"),
        )
        self.sld_timeout.grid(row=0, column=0, sticky="ew")
        self.lbl_timeout_val = ctk.CTkLabel(slider_row, text="15s", font=ctk.CTkFont("Consolas", 12, "bold"), text_color="#3A7DFF", width=50)
        self.lbl_timeout_val.grid(row=0, column=1, padx=(15, 0))

    def _build_ui_pane(self):
        """UI & Graphing settings: display window and line thickness."""
        self.pane_ui = ctk.CTkFrame(self.content, fg_color="transparent")
        card = ctk.CTkFrame(self.pane_ui, fg_color="#141416", corner_radius=12)
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Canvas Performance & Vector Controls", font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color="#FFFFFF").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(card, text="Configure chart display depth and line rendering weight.", font=ctk.CTkFont("Segoe UI", 12), text_color="#6D6D78").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        ctk.CTkLabel(card, text="Live Canvas Rolling Display History Depth", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=2, column=0, sticky="w", padx=20, pady=(5, 5))
        self.drop_window = ctk.CTkComboBox(
            card, values=["10 Second Window", "20 Second Window", "30 Second Window"],
            fg_color="#1C1C21", border_color="#2D2D34", button_color="#2D2D34",
            button_hover_color="#3A3A42", dropdown_fg_color="#141416",
            dropdown_hover_color="#2D2D34", corner_radius=8, state="readonly",
            height=38, width=220, font=ctk.CTkFont("Segoe UI", 12),
        )
        self.drop_window.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 20))

        ctk.CTkLabel(card, text="Chart Line Weight", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=4, column=0, sticky="w", padx=20, pady=(5, 5))

        thick_row = ctk.CTkFrame(card, fg_color="transparent")
        thick_row.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 25))
        thick_row.grid_columnconfigure(0, weight=1)

        self.sld_thickness = ctk.CTkSlider(
            thick_row, from_=1, to=5, number_of_steps=4, height=16,
            button_color="#3A7DFF", button_hover_color="#2A6DDF",
            command=lambda v: self.lbl_thick_val.configure(text=f"{int(v)} px"),
        )
        self.sld_thickness.grid(row=0, column=0, sticky="ew")
        self.lbl_thick_val = ctk.CTkLabel(thick_row, text="2 px", font=ctk.CTkFont("Consolas", 12, "bold"), text_color="#3A7DFF", width=50)
        self.lbl_thick_val.grid(row=0, column=1, padx=(15, 0))

    def _build_storage_pane(self):
        """Storage settings: database and log directory paths."""
        self.pane_storage = ctk.CTkFrame(self.content, fg_color="transparent")
        card = ctk.CTkFrame(self.pane_storage, fg_color="#141416", corner_radius=12)
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Local Storage Routing", font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color="#FFFFFF").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(card, text="Set directory paths for the SQLite database and system log files.", font=ctk.CTkFont("Segoe UI", 12), text_color="#6D6D78").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        # Database directory
        ctk.CTkLabel(card, text="SQLite Database Directory", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=2, column=0, sticky="w", padx=20, pady=(5, 5))
        db_row = ctk.CTkFrame(card, fg_color="transparent")
        db_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        db_row.grid_columnconfigure(0, weight=1)
        self.ent_db_dir = ctk.CTkEntry(db_row, fg_color="#1C1C21", border_color="#2D2D34", corner_radius=8, height=38, font=ctk.CTkFont("Segoe UI", 12))
        self.ent_db_dir.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(db_row, text="Browse", width=85, height=38, corner_radius=8, fg_color="#2D2D34", hover_color="#3A3A42", font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self._browse_db).grid(row=0, column=1)

        # Log directory
        ctk.CTkLabel(card, text="System Log Output Directory", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color="#A5A5B2").grid(row=4, column=0, sticky="w", padx=20, pady=(5, 5))
        log_row = ctk.CTkFrame(card, fg_color="transparent")
        log_row.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 25))
        log_row.grid_columnconfigure(0, weight=1)
        self.ent_log_dir = ctk.CTkEntry(log_row, fg_color="#1C1C21", border_color="#2D2D34", corner_radius=8, height=38, font=ctk.CTkFont("Segoe UI", 12))
        self.ent_log_dir.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(log_row, text="Browse", width=85, height=38, corner_radius=8, fg_color="#2D2D34", hover_color="#3A3A42", font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self._browse_logs).grid(row=0, column=1)

    def _build_footer(self):
        """Build the Save/Discard buttons at the bottom."""
        footer = ctk.CTkFrame(self, fg_color="transparent", height=60)
        footer.grid(row=1, column=1, sticky="ew", padx=25, pady=(5, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(footer, text="", font=ctk.CTkFont("Segoe UI", 12), text_color="#2EA44F")
        self.lbl_status.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer, text="Discard", width=100, height=38, corner_radius=8,
            fg_color="transparent", border_width=1, border_color="#D73A49",
            hover_color="#2B1A1D", text_color="#D73A49",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self.destroy,
        ).grid(row=0, column=1, padx=(0, 12))

        ctk.CTkButton(
            footer, text="Save Settings", width=130, height=38, corner_radius=8,
            fg_color="#3A7DFF", hover_color="#2A6DDF", text_color="#FFFFFF",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self._save,
        ).grid(row=0, column=2)

    def _populate_fields(self):
        """Fill all input fields with the current config values."""
        cfg = self.current_config

        # BLE tab
        self.ent_ble_id.insert(0, str(cfg.get("ble_device_identifier", "")))
        self.sld_timeout.set(cfg.get("ble_connection_timeout_s", 15))
        self.lbl_timeout_val.configure(text=f"{int(cfg.get('ble_connection_timeout_s', 15))}s")

        # UI tab
        window_map = {10: "10 Second Window", 20: "20 Second Window", 30: "30 Second Window"}
        self.drop_window.set(window_map.get(cfg.get("graph_display_window_sec", 20), "20 Second Window"))
        self.sld_thickness.set(cfg.get("chart_line_thickness", 2))
        self.lbl_thick_val.configure(text=f"{int(cfg.get('chart_line_thickness', 2))} px")

        # Storage tab
        self.ent_db_dir.insert(0, str(cfg["sqlite_database_directory"]))
        self.ent_log_dir.insert(0, str(cfg["system_logs_directory"]))

    def _browse_db(self):
        initial = self.ent_db_dir.get() if os.path.exists(self.ent_db_dir.get()) else os.getcwd()
        selected = filedialog.askdirectory(parent=self, initialdir=initial, title="Select Database Directory")
        if selected:
            self.ent_db_dir.delete(0, "end")
            self.ent_db_dir.insert(0, os.path.abspath(selected))

    def _browse_logs(self):
        initial = self.ent_log_dir.get() if os.path.exists(self.ent_log_dir.get()) else os.getcwd()
        selected = filedialog.askdirectory(parent=self, initialdir=initial, title="Select Log Directory")
        if selected:
            self.ent_log_dir.delete(0, "end")
            self.ent_log_dir.insert(0, os.path.abspath(selected))

    def _save(self):
        """Validate inputs, write config to JSON, and notify the parent."""
        db_path = self.ent_db_dir.get().strip()
        log_path = self.ent_log_dir.get().strip()
        ble_id = self.ent_ble_id.get().strip()

        if not ble_id:
            messagebox.showerror("Validation Error", "BLE device identifier cannot be blank.", parent=self)
            return
        if not os.path.isdir(db_path):
            messagebox.showerror("Validation Error", "Database directory path is invalid.", parent=self)
            return
        if not os.path.isdir(log_path):
            try:
                os.makedirs(log_path, exist_ok=True)
            except Exception:
                messagebox.showerror("Validation Error", "Could not create the log directory.", parent=self)
                return

        window_map = {"10 Second Window": 10, "20 Second Window": 20, "30 Second Window": 30}
        updated = {
            "ble_device_identifier": ble_id,
            "ble_connection_timeout_s": int(self.sld_timeout.get()),
            "graph_display_window_sec": window_map.get(self.drop_window.get(), 20),
            "chart_line_thickness": int(self.sld_thickness.get()),
            "sqlite_database_directory": os.path.abspath(db_path),
            "system_logs_directory": os.path.abspath(log_path),
        }

        try:
            with open(config.CONFIG_FILE, "w") as f:
                json.dump(updated, f, indent=4)

            if self.on_save_callback:
                self.on_save_callback(updated)

            self.lbl_status.configure(text="Configuration saved.")
            self.after(600, self.destroy)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not write config file:\n{e}", parent=self)
