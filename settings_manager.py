import json
import os

class SettingsManager:
    """
    Handles loading and saving of application settings to a persistent JSON file.
    Settings are stored in the user's home directory under .photoai/settings.json.
    """
    def __init__(self, filename="settings.json"):
        # Store in user's home directory to persist across app updates/moves
        self.config_dir = os.path.join(os.path.expanduser("~"), ".photoai")
        os.makedirs(self.config_dir, exist_ok=True)
        self.filename = os.path.join(self.config_dir, filename)
        self.settings = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings from {self.filename}: {e}")
                return {}
        return {}

    def get(self, key, default=None):
        """Retrieve a setting value or return the default."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Update a setting and save immediately."""
        self.settings[key] = value
        self._save()

    def _save(self):
        """Commit current settings to disk."""
        try:
            with open(self.filename, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings to {self.filename}: {e}")

    def get_config_dir(self):
        """Returns the directory where config files are stored."""
        return self.config_dir
