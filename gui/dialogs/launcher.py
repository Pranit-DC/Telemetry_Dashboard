# Helper to open sub-windows without cluttering app.py.
# Tracks window instances to prevent duplicates.


def open_settings(parent, db_manager, on_save_callback):
    """Open the settings window (or focus it if already open)."""
    from .settings import SettingsWindow
    if hasattr(parent, "_settings_win") and parent._settings_win.winfo_exists():
        parent._settings_win.focus()
        parent._settings_win.lift()
        return parent._settings_win
    parent._settings_win = SettingsWindow(parent, db_manager, on_save_callback)
    return parent._settings_win


def open_session_manager(parent, db_manager, on_session_load_callback):
    """Open the session manager (or focus it if already open)."""
    from .manager import SessionManagerWindow
    if hasattr(parent, "_session_win") and parent._session_win.winfo_exists():
        parent._session_win.focus()
        parent._session_win.lift()
        return parent._session_win
    parent._session_win = SessionManagerWindow(parent, db_manager, on_session_load_callback)
    return parent._session_win


def open_analytics_window(parent, db, time_data, channels_data):
    """Open the analytics window (or focus it if already open).

    Passes db and live data references so tabs can access real data.
    """
    from gui.analytics.window import AnalyticsWindow
    if hasattr(parent, "_analytics_win") and parent._analytics_win.winfo_exists():
        parent._analytics_win.focus()
        parent._analytics_win.lift()
        return parent._analytics_win
    parent._analytics_win = AnalyticsWindow(db, time_data, channels_data)
    return parent._analytics_win
