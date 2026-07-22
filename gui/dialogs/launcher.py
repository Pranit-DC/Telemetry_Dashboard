from .settings import SettingsWindow
from .manager import SessionManagerWindow

def open_settings(parent, config, on_save_callback):
    """Open the settings window."""
    window = SettingsWindow(parent, config, on_save_callback)
    window.wait_visibility()
    window.grab_set()

def open_session_manager(parent, db_manager, on_session_load_callback):
    """Open the session manager window."""
    window = SessionManagerWindow(parent, db_manager, on_session_load_callback)
    window.wait_visibility()
    window.grab_set()

def open_analytics_window(parent, db, burst_history):
    """Open the analytics window."""
    from gui.analytics.window import AnalyticsWindow
    window = AnalyticsWindow(db, burst_history)
    window.wait_visibility()
    window.grab_set()
