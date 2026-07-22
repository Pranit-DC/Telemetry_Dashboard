# Application entry point.
# Creates the main dashboard window and starts the event loop.

import sys
from gui.app import TelemetryDashboard


def main():
    app = TelemetryDashboard()
    app.protocol("WM_DELETE_WINDOW", lambda: on_close(app))
    app.mainloop()


def on_close(app):
    """Clean up resources and exit when the window is closed."""
    print("[System] Closing application safely...")
    app.cleanup()
    app.destroy()
    sys.exit(0)


if __name__ == "__main__":
    main()