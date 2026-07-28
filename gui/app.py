import customtkinter as ctk
from datetime import datetime

from config import AppConfig, WINDOW_TITLE, GEOMETRY_SIZE, MIN_GEOMETRY_SIZE
from core.database.manager import DatabaseManager
from core.logging import RollingCSVLogger, export_session_csv
from core.services.acquisition import AcquisitionService

from gui.components import Sidebar
from gui.dashboard import DashboardPage, GraphRenderer
from gui.dialogs.launcher import open_session_manager, open_settings, open_analytics_window

MAX_BURST_HISTORY = 1000

class TelemetryDashboard(ctk.CTk):
    """
    Main application window for the Telemetry Dashboard.
    Manages the GUI structure and bridges UI interactions with backend services.
    """
    def __init__(self, source_type='simulator'):
        super().__init__()
        
        # Load config
        self.config = AppConfig()
        
        # Apply UI scaling from config
        if hasattr(self.config, 'ui_scale') and self.config.ui_scale != 1.0:
            ctk.set_widget_scaling(self.config.ui_scale)
            ctk.set_window_scaling(self.config.ui_scale)
            
        # Window setup
        self.title(WINDOW_TITLE)
        self.geometry(GEOMETRY_SIZE)
        self.minsize(*MIN_GEOMETRY_SIZE)
        
        # Grid layout (1x2) - Sidebar and Main Content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main Content
        
        # Backend services
        self.db = DatabaseManager(config=self.config)
        self.csv_logger = RollingCSVLogger(config=self.config)
        self.service = AcquisitionService(self.db, self.csv_logger, self.config)
        
        # Data state for display
        self.burst_history = []
        self.latest_burst = None
        self._run_state = 'stopped'  # 'stopped' | 'running' | 'paused'
        
        # State callback
        self.service.set_on_state_change(lambda s: self.after(0, lambda: self._on_state_change(s)))
        
        # Build UI
        self._build_ui()
        
        # Initialize Renderer
        self.renderer = GraphRenderer(self.dashboard_page)
        
        # Set initial source and connect
        self.service.set_source(source_type)
        self.service.connect()
        
        # Start queue polling timer
        self._poll_interval = 100  # ms
        self._start_polling()

    def _build_ui(self):
        """Build the main UI components."""
        self.sidebar = Sidebar(
            self,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_clear=self._on_clear,
            on_manage_sessions=self._open_session_manager,
            on_analytics=self._open_analytics_window,
            on_export=self._on_export_csv,
            on_settings=self._open_settings
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.dashboard_page = DashboardPage(self)
        self.dashboard_page.grid(row=0, column=1, sticky="nsew")

    def _start_polling(self):
        """Poll the burst queue every 100ms."""
        bursts = self.service.poll_queue()
        updated = False
        for burst in bursts:
            self.burst_history.append(burst)
            self.latest_burst = burst
            updated = True
            self.log_message(
                f"Burst #{burst.burst_id} | Peak: {burst.peak_voltage:.3f} V | "
                f"Fall Time: {burst.fall_time_us:.1f} μs | Rolling Avg: {burst.avg_fall_time_us:.1f} μs"
            )
        
        # Trim old bursts to prevent memory leak
        if len(self.burst_history) > MAX_BURST_HISTORY:
            self.burst_history = self.burst_history[-MAX_BURST_HISTORY:]
        
        if updated:
            self._refresh_dashboard()
            
        self.after(self._poll_interval, self._start_polling)
        
    def _on_start(self):
        """Single button handler for Start / Pause / Resume.

        Behavior depends on current run state:
          - no session running  -> start a brand new session
          - session running     -> pause (stream stops, session stays open)
          - session paused      -> resume (same session_id, stream restarts)
        """
        if not self.service.session_id:
            # Nothing running: start fresh.
            self.burst_history.clear()
            self.latest_burst = None
            self._reset_canvas()
            self.service.start_session()
            self._run_state = 'running'
            self.sidebar.set_run_state('running')
            self.log_message(f'Started recording: {self.service.session_id}')

        elif self._run_state == 'running':
            self.service.pause_session()
            self._run_state = 'paused'
            self.sidebar.set_run_state('paused')
            self.log_message(f'Paused. Session {self.service.session_id} still open.')

        elif self._run_state == 'paused':
            self.service.resume_session()
            self._run_state = 'running'
            self.sidebar.set_run_state('running')
            self.log_message(f'Resumed session {self.service.session_id}.')

    def _on_stop(self):
        """Fully stop and finalize the current session, from either running or paused."""
        session_id = self.service.stop_session()
        self._run_state = 'stopped'
        self.sidebar.set_run_state('stopped')
        self.log_message(f'Recording stopped. Session {session_id} saved.')

    def _on_clear(self):
        """Clear the current data buffers."""
        self.burst_history.clear()
        self.latest_burst = None
        self._reset_canvas()
        self.log_message("Buffer cleared.")

    def _refresh_dashboard(self):
        """Update the graph and metric cards with latest burst data."""
        self.renderer.refresh(self.latest_burst, self.burst_history)

    def _on_load_session(self, choice):
        """Load a historical session."""
        if not choice or choice == "Select Session":
            return
            
        # Parse session_id from display label 'Name (ID)'
        try:
            session_id = choice.split('(')[-1].strip(')')
            bursts = self.db.get_session_bursts(session_id)
            self.burst_history = bursts
            self.latest_burst = bursts[-1] if bursts else None
            self._refresh_dashboard()
            self.log_message(f"Loaded session {session_id}")
        except Exception as e:
            self.log_message(f"Error loading session: {e}")

    def _on_export_csv(self):
        """Export current session data."""
        if self.burst_history:
            filepath = f'telemetry_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            try:
                export_session_csv(self.burst_history, filepath)
                self.log_message(f"Exported {len(self.burst_history)} bursts to {filepath}")
            except Exception as e:
                self.log_message(f"Export failed: {e}")
        else:
            self.log_message("No data to export.")

    def _open_session_manager(self):
        open_session_manager(self, self.db, self._on_load_session)

    def _open_settings(self):
        open_settings(self, self.config, self._apply_settings)

    def _open_analytics_window(self):
        open_analytics_window(self, self.db, self.burst_history)

    def _apply_settings(self, settings_dict):
        """Apply new settings."""
        self.config.update(**settings_dict)
        self.config.save()
        self.log_message("Settings saved.")

    def _on_state_change(self, new_state):
        """Handle data source state changes."""
        state_colors = {
            'disconnected': '#D73A49',
            'connecting': '#E1B12C',
            'connected': '#7F7F8C',
            'acquiring': '#2EA44F',
            'error': '#D73A49',
        }
        self.sidebar.update_status(
            f'Status: {new_state.upper()}',
            state_colors.get(new_state, '#7F7F8C')
        )
        self.dashboard_page.update_source_status(new_state.upper())

    def log_message(self, message):
        """Log a message to the dashboard terminal."""
        if hasattr(self, 'dashboard_page'):
            self.dashboard_page.log_message(message)
            
    def _reset_canvas(self):
        """Clear the graph to prepare for a fresh live view."""
        self.renderer.clear()

    def cleanup(self):
        """Cleanup resources before exit."""
        self.service.cleanup()
        self.csv_logger.close()
        self.db.close()