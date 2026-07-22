import os
import json

WINDOW_TITLE = "Photodetector Decay Analyzer Dashboard"
GEOMETRY_SIZE = "1400x870"
MIN_GEOMETRY_SIZE = (1200, 780)
CONFIG_FILE = "config_settings.json"

class AppConfig:
    """Centralized configuration manager. Loads from JSON, provides typed access."""
    def __init__(self):
        self._data = self._load()
    
    def _load(self) -> dict:
        defaults = self.get_defaults()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                print(f"[ERR] Failed reading config JSON: {e}")
        return defaults
    
    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self._data, f, indent=4)
    
    @property
    def ble_device_name(self) -> str:
        return self._data.get('ble_device_name', 'GIGA_WORKSTATION')
        
    @property
    def ble_timeout(self) -> int:
        return self._data.get('ble_timeout', 15)
        
    @property
    def com_port(self) -> str:
        return self._data.get('com_port', '')
        
    @property
    def baud_rate(self) -> int:
        return self._data.get('baud_rate', 115200)
        
    @property
    def graph_display_window_sec(self) -> int:
        return self._data.get('graph_display_window_sec', 20)
        
    @property
    def chart_line_thickness(self) -> int:
        return self._data.get('chart_line_thickness', 2)
        
    @property
    def sqlite_database_directory(self) -> str:
        return self._data.get('sqlite_database_directory', os.path.abspath(os.getcwd()))
        
    @property
    def system_logs_directory(self) -> str:
        return self._data.get('system_logs_directory', os.path.abspath(os.path.join(os.getcwd(), 'logs')))
        
    @property
    def ui_scale(self) -> float:
        return self._data.get('ui_scale', 2.4)
    
    def update(self, **kwargs):
        self._data.update(kwargs)
        self.save()
    
    @staticmethod
    def get_defaults() -> dict:
        return {
            'ble_device_name': 'GIGA_WORKSTATION',
            'ble_timeout': 15,
            'com_port': '',
            'baud_rate': 115200,
            'graph_display_window_sec': 20,
            'chart_line_thickness': 2,
            'sqlite_database_directory': os.path.abspath(os.getcwd()),
            'system_logs_directory': os.path.abspath(os.path.join(os.getcwd(), 'logs')),
            'ui_scale': 2.4,
        }

def load_persistent_config() -> dict:
    """Backward compatibility for settings dialog."""
    config = AppConfig()
    return config._data