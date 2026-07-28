import customtkinter as ctk
from gui.app import TelemetryDashboard

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = TelemetryDashboard(source_type="ble")
    
    def on_close():
        try:
            app.cleanup()
        finally:
            app.destroy()
    
    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()

if __name__ == "__main__":
    main()