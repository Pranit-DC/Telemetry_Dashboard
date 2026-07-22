import os
import csv
import glob
from datetime import datetime
from models.telemetry import TraceBurst

class RollingCSVLogger:
    """Logs trace burst metrics to daily rolling CSV files."""
    
    HEADER = ["Timestamp", "Burst_ID", "Peak_Voltage_V", "Fall_Time_us", "Avg_Fall_Time_us"]
    
    def __init__(self, config):
        self.logs_dir = config.system_logs_directory
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        self.current_date = datetime.now().date()
        self.file = None
        self.writer = None
        self._open_new_file()
        self._cleanup_old_logs(retention_days=7)
        
    def _get_filename(self, date_obj):
        return os.path.join(self.logs_dir, f"telemetry_metrics_{date_obj.strftime('%Y%m%d')}.csv")
        
    def _open_new_file(self):
        self.close()
        filename = self._get_filename(self.current_date)
        file_exists = os.path.exists(filename)
        
        self.file = open(filename, 'a', newline='')
        self.writer = csv.writer(self.file)
        
        if not file_exists:
            self.writer.writerow(self.HEADER)
            self.file.flush()
            
    def _check_rollover(self):
        now_date = datetime.now().date()
        if now_date > self.current_date:
            self.current_date = now_date
            self._open_new_file()
            self._cleanup_old_logs(retention_days=7)
            
    def log_burst(self, burst: TraceBurst):
        self._check_rollover()
        if self.writer:
            self.writer.writerow([
                burst.timestamp.isoformat(),
                burst.burst_id,
                f"{burst.peak_voltage:.4f}",
                f"{burst.fall_time_us:.2f}",
                f"{burst.avg_fall_time_us:.2f}"
            ])
            self.file.flush()
            
    def _cleanup_old_logs(self, retention_days):
        try:
            files = glob.glob(os.path.join(self.logs_dir, "telemetry_metrics_*.csv"))
            now = datetime.now()
            for f in files:
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                if (now - mtime).days > retention_days:
                    os.remove(f)
        except Exception:
            pass
            
    def close(self):
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None

def export_session_csv(bursts: list[TraceBurst], filepath: str):
    """Exports full trace data for a session to a CSV file."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write headers
        writer.writerow(["Burst_ID", "Timestamp", "Sample_Index", "Time_us", "Voltage_V"])
        
        for burst in bursts:
            ts = burst.timestamp.isoformat()
            bid = burst.burst_id
            for pt in burst.trace_points:
                writer.writerow([bid, ts, pt.sample_index, pt.time_us, f"{pt.voltage:.4f}"])
