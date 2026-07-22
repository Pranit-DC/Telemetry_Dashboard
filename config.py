import os
import json
import customtkinter as ctk

# Global CustomTkinter Visual Configuration Flags
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Global Settings Map (Static Layout Constants)
WINDOW_TITLE = "Multi-Channel Photodiode Telemetry Dashboard"
GEOMETRY_SIZE = "1400x870"
MIN_GEOMETRY_SIZE = (1200, 780)

AVAILABLE_CHANNELS = ["Channel 1", "Channel 2", "Channel 3"]
CHANNEL_COLORS = {
    "Channel 1": "#3A7DFF",  # Neon Blue
    "Channel 2": "#2EA44F",  # Emerald Green
    "Channel 3": "#E1B12C",  # Amber Gold
    # "Channel 4": "#FFCCC4" # Reserved for future 4th channel
}


CONFIG_FILE = "config_settings.json"


def get_default_config():
    """Standard baseline fallback settings for the JSON payload."""
    return {
        "ble_device_identifier": "Arduino Giga R1",
        "ble_connection_timeout_s": 15,
        "graph_display_window_sec": 20, # Defaulting back to an un-congested 20 seconds
        "chart_line_thickness": 2,
        "sqlite_database_directory": os.path.abspath(os.getcwd()),
        "system_logs_directory": os.path.abspath(os.path.join(os.getcwd(), "logs"))
    }

def load_persistent_config():
    defaults = get_default_config()
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(defaults, f, indent=4)
        except Exception as e:
            print(f"[ERR] Could not initialize configuration file: {e}")
        return defaults
    try:
        with open(CONFIG_FILE, "r") as f:
            loaded = json.load(f)
            # Safe upgrade migration check
            if "graph_display_window_min" in loaded:
                # Migrate old minutes config to seconds automatically
                loaded["graph_display_window_sec"] = loaded.pop("graph_display_window_min") * 60
            for key in defaults:
                if key not in loaded:
                    loaded[key] = defaults[key]
            return loaded
    except Exception as e:
        print(f"[ERR] Failed reading config JSON: {e}. Reverting to defaults.")
        return defaults

_runtime_config = load_persistent_config()

BLE_DEVICE_IDENTIFIER = _runtime_config["ble_device_identifier"]
BLE_CONNECTION_TIMEOUT_S = _runtime_config["ble_connection_timeout_s"]
GRAPH_DISPLAY_WINDOW_SEC = _runtime_config["graph_display_window_sec"] # Changed to seconds
CHART_LINE_THICKNESS = _runtime_config["chart_line_thickness"]
SQLITE_DATABASE_DIRECTORY = _runtime_config["sqlite_database_directory"]
SYSTEM_LOGS_DIRECTORY = _runtime_config["system_logs_directory"]

# 1 packet per second updates means 1 point = 1 second
MAX_BUFFER_POINTS = GRAPH_DISPLAY_WINDOW_SEC