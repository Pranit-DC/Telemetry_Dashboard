# Main application window for the telemetry dashboard.
# This file only handles:
#   1. Wiring user actions to the simulator and graph renderer
#   2. Opening child windows (settings, session manager, analytics)
#
# Data generation: core/telemetry/simulator.py
# Graph updates: gui/dashboard/graph_renderer.py
# Analytics math: core/analysis/signal.py

import threading
from datetime import datetime
import customtkinter as ctk

import config
from core.database import DatabaseManager
from core.telemetry import RollingCSVLogger, export_to_csv, TelemetrySimulator
from gui.dashboard import DashboardPage, GraphRenderer
from gui.components import UXNotification, Sidebar


class TelemetryDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Scaling for Linux testing (remove these two lines on Windows)
        ctk.set_widget_scaling(2.4)
        ctk.set_window_scaling(2.4)

        # Window setup
        self.title(config.WINDOW_TITLE)
        self.geometry(config.GEOMETRY_SIZE)
        self.minsize(*config.MIN_GEOMETRY_SIZE)

        # Backend services
        self.db = DatabaseManager()
        self.csv_logger = RollingCSVLogger()

        # Thread-safety lock for shared data lists.
        # The simulator thread writes to these lists, the GUI thread reads them.
        # This lock prevents them from doing it at the same time.
        self.data_lock = threading.Lock()

        # Shared data containers (simulator writes, renderer reads)
        self.time_data = []
        self.channels_data = {ch: [] for ch in config.AVAILABLE_CHANNELS}
        self.all_history = []

        # Graph normalization toggle
        saved_norm = self.db.get_setting("normalize_graph", "False")
        self.normalize_graph = (saved_norm == "True")

        # Load channel visibility preferences from database
        self.active_channels = {}
        for ch in config.AVAILABLE_CHANNELS:
            saved = self.db.get_setting(f"visibility_{ch}", "True")
            self.active_channels[ch] = (saved == "True")

        # Load which channel is selected for analytics display
        saved_target = self.db.get_setting("selected_analytics_channel", "Channel 1")
        self.selected_analytics_channel = (
            saved_target if saved_target in config.AVAILABLE_CHANNELS else "Channel 1"
        )

        # Grid layout: sidebar on the left, dashboard on the right
        self.grid_columnconfigure(0, weight=0, minsize=200)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Build the sidebar with all controls
        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Map sidebar widgets back to controller properties for convenience
        self.lbl_status = self.sidebar.lbl_status
        self.btn_start = self.sidebar.buttons["btn_start"]
        self.btn_pause = self.sidebar.buttons["btn_pause"]
        self.btn_stop = self.sidebar.buttons["btn_stop"]
        self.btn_clear = self.sidebar.buttons["btn_clear"]
        self.opt_playback = self.sidebar.opt_playback
        self.chk_vars = self.sidebar.chk_vars
        self.opt_analytics = self.sidebar.opt_analytics
        self.btn_csv = self.sidebar.btn_csv

        # Build the main dashboard area (chart + metrics + log)
        self.main_view = DashboardPage(self, self)
        self.main_view.grid(row=0, column=1, sticky="nsew")

        # Sync the normalization switch state
        if self.normalize_graph:
            self.main_view.normalize_switch.select()
        else:
            self.main_view.normalize_switch.deselect()

        # Create the graph renderer (handles all matplotlib updates)
        self.renderer = GraphRenderer(self.main_view)

        # Create the simulator (handles background data generation)
        self.simulator = TelemetrySimulator(
            time_data=self.time_data,
            channels_data=self.channels_data,
            all_history=self.all_history,
            db=self.db,
            csv_logger=self.csv_logger,
            schedule_fn=self.after,
            log_fn=self.log_message,
            refresh_fn=self._refresh_dashboard,
            data_lock=self.data_lock,
        )

        # Apply saved line thickness to the chart
        try:
            thickness = float(config.CHART_LINE_THICKNESS)
            for line in self.main_view.plot_lines.values():
                line.set_linewidth(thickness)
            self.main_view.canvas.draw_idle()
        except Exception:
            pass

        # Sync the channel visibility checkboxes with saved state
        for ch in config.AVAILABLE_CHANNELS:
            if not self.active_channels[ch]:
                self.chk_vars[ch].set(False)
        self.opt_analytics.set(self.selected_analytics_channel)

        self.log_message("System initialized. Storage connection active.")
        self._refresh_playback_dropdown()

    # -- Event handlers --

    def _on_start(self):
        """Start or resume the simulation."""
        is_resuming = self.simulator._pause_start is not None

        if not is_resuming:
            # Fresh start: check if we need to reset from a previous stop
            if self.lbl_status.cget("text") == "Status: STREAM STOPPED":
                self._reset_canvas()

            # Create a new session in the database
            session_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.db.insert_session_metadata(
                session_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            self.simulator.start(session_id)
            self.log_message(f"Started recording: {session_id}")
        else:
            self.simulator.resume()
            self.log_message("Resumed recording.")

        self.lbl_status.configure(text="Status: RUNNING", text_color="#2EA44F")
        self.btn_start.configure(state="disabled", fg_color="#1F5B2E")
        self.btn_pause.configure(state="normal", fg_color="#2D2D34")
        self.btn_stop.configure(state="normal")
        self._set_export_state("disabled")

    def _on_pause(self):
        """Pause the simulation (preserves timing for resume)."""
        self.simulator.pause()
        self.db.flush_frames()
        self.lbl_status.configure(text="Status: PAUSED", text_color="#E1B12C")
        self.log_message("Telemetry paused.")
        self.btn_start.configure(state="normal", text="Resume Stream", fg_color="#2EA44F")
        self.btn_pause.configure(state="disabled")

    def _on_stop(self):
        """Stop the simulation completely."""
        session_id = self.simulator.session_id
        self.simulator.stop()
        self.db.flush_frames()
        self.lbl_status.configure(text="Status: STREAM STOPPED", text_color="#D73A49")
        self.log_message(f"Recording stopped. Session {session_id} saved.")
        self.btn_start.configure(state="normal", text="Start Simulation", fg_color="#2EA44F")
        self.btn_pause.configure(state="disabled")
        self.btn_stop.configure(state="disabled")
        self._refresh_playback_dropdown()
        if self.all_history:
            self._set_export_state("normal")

    def _on_clear(self):
        """Clear all data buffers and reset the display."""
        self._reset_canvas()
        with self.data_lock:
            self.all_history.clear()
        self.simulator.expected_packets = 0
        self.simulator.received_packets = 0
        self.simulator._last_autosave_count = 0
        self.main_view.lbl_loss.configure(text="Dropped Frames: 0")
        self.main_view.lbl_battery.configure(text="Battery: 100%", text_color="#2EA44F")
        self.log_message("Buffer cleared.")
        self._set_export_state("disabled")

    def _on_visibility_changed(self):
        """Handle channel visibility checkbox toggle."""
        for ch in config.AVAILABLE_CHANNELS:
            is_visible = self.chk_vars[ch].get()
            self.active_channels[ch] = is_visible
            self.db.save_setting(f"visibility_{ch}", str(is_visible))

        # Acquire lock to safely read the shared data lists
        with self.data_lock:
            self.renderer.update_visibility(
                self.time_data, self.channels_data,
                self.active_channels, self.normalize_graph,
            )

    def _on_analytics_changed(self, choice):
        """Handle analytics target channel selection change."""
        self.selected_analytics_channel = choice
        self.db.save_setting("selected_analytics_channel", choice)

        # Update the card titles to show the new channel abbreviation
        short = "CH" + choice.split(" ")[1]
        for key in self.main_view.cards:
            title_widget = self.main_view.cards[key]["title"]
            if key == "Max Jitter (Δt)":
                title_widget.configure(text=f"MAX JITTER (vs {short})")
            else:
                title_widget.configure(text=f"{key.upper()} ({short})")

        self.log_message(f"Analytics focus shifted to {choice}.")

    def _on_normalization_changed(self):
        """Handle the normalize toggle switch on the graph toolbar."""
        self.normalize_graph = self.main_view.normalize_switch.get()
        self.db.save_setting("normalize_graph", str(self.normalize_graph))
        state = "Enabled" if self.normalize_graph else "Disabled"
        self.log_message(f"Graph normalization {state}")
        self._refresh_dashboard()

    def _on_load_session(self, choice):
        """Load a historical session from the database and display it."""
        if choice in ["No Sessions Saved", "Select Past Run..."]:
            return
        if self.simulator.is_running:
            self._on_stop()

        self._on_clear()
        records = self.db.get_session_data(choice)
        if not records:
            self.log_message("Error: Session contains no data.")
            return

        self.log_message(f"Replaying session: {choice}")

        # Acquire lock to safely write to shared data lists
        with self.data_lock:
            for elapsed, v1, v2, v3 in records:
                self.time_data.append(elapsed)
                self.channels_data["Channel 1"].append(v1)
                self.channels_data["Channel 2"].append(v2)
                self.channels_data["Channel 3"].append(v3)
                # Build history rows matching the same format as live recording
                self.all_history.append([
                    "loaded-session", elapsed, v1, v2, v3
                ])

        self._refresh_dashboard()
        self._set_export_state("normal")

    def _on_export_csv(self):
        """Export all recorded data to a CSV file."""
        filename, msg = export_to_csv(self.all_history, config.AVAILABLE_CHANNELS)
        self.log_message(msg)
        if filename:
            UXNotification.render_popup(
                self, "File Saved Successfully",
                f"Telemetry file saved to:\n{filename}",
            )
        else:
            UXNotification.render_popup(self, "Export Failed", msg)

    # -- Helper methods --

    def _refresh_dashboard(self):
        """Tell the renderer to update the graph and analytics cards."""
        # Acquire lock so the renderer can safely copy the lists
        with self.data_lock:
            self.renderer.refresh(
                self.time_data, self.channels_data, self.active_channels,
                self.normalize_graph, self.selected_analytics_channel,
                self.simulator.expected_packets, self.simulator.received_packets,
            )

    def _reset_canvas(self):
        """Clear all plot lines and reset axis limits."""
        with self.data_lock:
            self.time_data.clear()
            for ch in config.AVAILABLE_CHANNELS:
                self.channels_data[ch].clear()
                self.main_view.plot_lines[ch].set_data([], [])

        self.main_view.ax.relim()
        if self.normalize_graph:
            self.main_view.ax.set_ylim(0, 1)
        else:
            self.main_view.ax.autoscale_view()
        self.main_view.canvas.draw_idle()

        # Reset analytics card displays
        for key in self.main_view.cards:
            default = "0.00 V" if "Peak" in key else (
                "0.0 Hz" if "Freq" in key else (
                    "0.00 s" if "Time" in key else "0.0 ms"
                )
            )
            self.main_view.cards[key]["value"].configure(text=default)

    def _refresh_playback_dropdown(self):
        """Reload the session list in the historical playback dropdown."""
        sessions = self.db.get_session_display_list()
        if sessions:
            self.opt_playback.configure(values=sessions)
            self.opt_playback.set("Select Past Run...")
        else:
            self.opt_playback.configure(values=["No Sessions Saved"])
            self.opt_playback.set("No Sessions Saved")

    def _set_export_state(self, state):
        """Enable or disable the export button with visual feedback."""
        is_enabled = (state == "normal")
        self.btn_csv.configure(
            state=state,
            fg_color="#3A7DFF" if is_enabled else "#232329",
            text_color="#FFFFFF" if is_enabled else "#52525B",
            hover_color="#2A65D4" if is_enabled else "#232329",
        )

    def log_message(self, message):
        """Append a timestamped message to the log terminal."""
        self.main_view.log_terminal.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.main_view.log_terminal.insert("end", f"[{timestamp}] {message}\n")
        self.main_view.log_terminal.see("end")
        self.main_view.log_terminal.configure(state="disabled")

    # -- Child windows --

    def _open_session_manager(self):
        try:
            from gui.dialogs.launcher import open_session_manager
            open_session_manager(self, self.db, self._on_load_session)
        except Exception as e:
            self.log_message(f"Error opening session manager: {e}")

    def _open_settings(self):
        try:
            from gui.dialogs.launcher import open_settings
            open_settings(self, self.db, self._apply_settings)
        except Exception as e:
            self.log_message(f"Error opening settings: {e}")

    def _open_analytics_window(self):
        try:
            from gui.dialogs.launcher import open_analytics_window
            open_analytics_window(self, self.db, self.time_data, self.channels_data)
        except Exception as e:
            self.log_message(f"Error opening analytics: {e}")

    def _apply_settings(self, cfg):
        """Apply new settings from the settings window to all components."""
        try:
            self.log_message("Applying new settings...")

            # Update the config module's global values
            config.BLE_DEVICE_IDENTIFIER = cfg["ble_device_identifier"]
            config.BLE_CONNECTION_TIMEOUT_S = cfg["ble_connection_timeout_s"]
            config.GRAPH_DISPLAY_WINDOW_SEC = cfg["graph_display_window_sec"]
            config.CHART_LINE_THICKNESS = cfg["chart_line_thickness"]
            config.SQLITE_DATABASE_DIRECTORY = cfg["sqlite_database_directory"]
            config.SYSTEM_LOGS_DIRECTORY = cfg["system_logs_directory"]
            config.MAX_BUFFER_POINTS = config.GRAPH_DISPLAY_WINDOW_SEC

            # Recreate the CSV logger with the new log directory
            try:
                self.csv_logger.close()
            except Exception:
                pass
            self.csv_logger = RollingCSVLogger(log_dir=config.SYSTEM_LOGS_DIRECTORY)
            self.simulator.csv_logger = self.csv_logger

            # Recreate the database connection with the new DB directory
            try:
                self.db.close()
            except Exception:
                pass
            self.db = DatabaseManager()
            self.simulator.db = self.db
            self._refresh_playback_dropdown()

            # Update chart line thickness
            thickness = float(config.CHART_LINE_THICKNESS)
            for line in self.main_view.plot_lines.values():
                line.set_linewidth(thickness)
            self.main_view.canvas.draw_idle()

            self.log_message("Settings applied successfully.")
        except Exception as e:
            self.log_message(f"Failed to apply settings: {e}")

    def cleanup(self):
        """Release resources before the application closes."""
        self.simulator.stop()
        self.db.flush_frames()
        self.csv_logger.close()
        self.db.close()
