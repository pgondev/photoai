import json
import os
from datetime import datetime

class HistoryManager:
    def __init__(self, filename="history.json"):
        # Centralized storage in ~/.photoai
        self.config_dir = os.path.join(os.path.expanduser("~"), ".photoai")
        os.makedirs(self.config_dir, exist_ok=True)
        self.history_file = os.path.join(self.config_dir, filename)
        self.history = self._load_history()

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def add_entry(self, action, details, log_content=None):
        log_file = None
        if log_content:
            logs_dir = os.path.join(self.config_dir, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"log_{timestamp_str}.txt"
            log_path = os.path.join(logs_dir, log_filename)
            try:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write(f"Action: {action}\n")
                    f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Summary: {details}\n")
                    f.write("-" * 40 + "\n")
                    if isinstance(log_content, list):
                        f.write("\n".join(log_content))
                    else:
                        f.write(str(log_content))
                log_file = log_path
            except Exception as e:
                print(f"Error writing log file: {e}")

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details,
            "logfile": log_file
        }
        self.history.insert(0, entry) # Newest first
        self.history = self.history[:500]  # Cap at 500 entries
        self._save_history()

    def _save_history(self):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Error saving history: {e}")

    def get_history(self):
        return self.history

    def clear_history(self):
        self.history = []
        self._save_history()
