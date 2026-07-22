# Rolling CSV logger for daily telemetry backup files.
# Creates one CSV file per day (telemetry_daily_YYYY-MM-DD.csv) and
# automatically rotates to a new file at midnight.
# Also includes a utility function for one-time CSV export.

import os
import csv
import glob
from datetime import datetime, timedelta
import config


class RollingCSVLogger:
    """Writes telemetry data to daily CSV files for backup.

    Each day gets its own file: telemetry_daily_2026-07-15.csv
    Old files beyond the retention period (default 30 days) are cleaned up.
    """

    def __init__(self, log_dir=None, retention_days=30):
        # Use the config directory if no explicit path is given
        if log_dir is None:
            log_dir = getattr(config, 'SYSTEM_LOGS_DIRECTORY', 'logs')

        # Resolve relative paths against the project root
        if os.path.isabs(log_dir):
            self.log_dir = log_dir
        else:
            self.log_dir = os.path.abspath(os.path.join(os.getcwd(), log_dir))

        self.retention_period = timedelta(days=retention_days)
        self._file = None
        self._writer = None
        self._current_date = None

        os.makedirs(self.log_dir, exist_ok=True)
        self._open_daily_file()
        self._cleanup_old_files()

    def _open_daily_file(self):
        """Open (or switch to) today's CSV file."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Already have the right file open
        if self._file and self._current_date == today:
            return

        # Close yesterday's file if we're rolling over at midnight
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass

        self._current_date = today
        path = os.path.join(self.log_dir, f"telemetry_daily_{today}.csv")

        # Check if the file already has content (don't re-write the header)
        needs_header = not os.path.exists(path) or os.path.getsize(path) == 0

        self._file = open(path, mode="a", newline="", buffering=1, encoding="utf-8")
        self._writer = csv.writer(self._file)

        if needs_header:
            header = ["System Timestamp", "Elapsed Time (s)"]
            header += [f"{ch} Potential (V)" for ch in config.AVAILABLE_CHANNELS]
            self._writer.writerow(header)

    def log_packet(self, row):
        """Write one data row to today's CSV file.

        Handles midnight rollover automatically: if the date changed since
        the last write, it opens a new file first.
        """
        if not row:
            return
        # Skip if someone accidentally passes the header row
        if "System Timestamp" in str(row[0]):
            return

        # Check if we crossed midnight
        if datetime.now().strftime("%Y-%m-%d") != self._current_date:
            self._open_daily_file()
            self._cleanup_old_files()

        if self._writer:
            self._writer.writerow(row)
            self._file.flush()

    def _cleanup_old_files(self):
        """Delete CSV files older than the retention period."""
        cutoff = datetime.now() - self.retention_period
        pattern = os.path.join(self.log_dir, "telemetry_daily_*.csv")

        for path in glob.glob(pattern):
            try:
                # Parse the date from the filename
                name = os.path.basename(path)
                date_str = name.replace("telemetry_daily_", "").replace(".csv", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff:
                    # Don't delete the file we currently have open
                    if self._file and os.path.abspath(path) == os.path.abspath(self._file.name):
                        continue
                    os.remove(path)
            except Exception:
                pass

    def close(self):
        """Close the current file handle."""
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass


def export_to_csv(all_history, available_channels):
    """Export all recorded telemetry data to a timestamped CSV file.

    Creates a file like telemetry_20260715_143022.csv in the current directory.
    Returns (filename, message) tuple.
    """
    if not all_history:
        return None, "No data available to export."

    filename = f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header matches the history row format:
            # [timestamp, elapsed_seconds, ch1_voltage, ch2_voltage, ch3_voltage]
            header = ["System Timestamp", "Elapsed Time (s)"]
            header += [f"{ch} Potential (V)" for ch in available_channels]
            writer.writerow(header)
            writer.writerows(all_history)
        return filename, f"Export successful: {filename}"
    except IOError as e:
        return None, f"Export failed: {e}"
