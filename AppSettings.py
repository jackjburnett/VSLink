# Creates and manages settings for the receiver, both for CLI and .exe

from dataclasses import asdict, dataclass
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Creates a dataclass for receiver settings
@dataclass(frozen=True)
class ReceiverSettings:
    # Sets Wi-Fi and Bluetooth to enabled by default, with Wi-Fi port set to 8000
    wifi_enabled: bool = True
    bluetooth_enabled: bool = True
    wifi_port: int = 8000

    # Validates the settings
    def __post_init__(self):
        # Checks that Wi-Fi and Bluetooth are booleans
        if type(self.wifi_enabled) is not bool or type(self.bluetooth_enabled) is not bool:
            raise ValueError("Transport settings must be true or false")
        # Checks that Wi-Fi port is an integer between 1 and 65535
        if type(self.wifi_port) is not int or not 1 <= self.wifi_port <= 65535:
            raise ValueError("Wi-Fi port must be a number between 1 and 65535")

# Stores the settings in a JSON file in the user's app data directory
class SettingsStore:
    def __init__(self, path=None):
        # Sets the path to the settings file, either user-provided or the default (LOCALAPPDATA/VSLink)
        directory = Path(os.environ.get("VSL_CONFIG_DIR") or (
            Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VSLink"
        ))
        # If the path is none, stores the settings in the current directory
        self.path = Path(path) if path is not None else directory / "settings.json"

    # Loads the settings from the file
    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return ReceiverSettings(**data)
        # Returns default settings if the file does not exist
        except FileNotFoundError:
            return ReceiverSettings()
        # Logs an exception if the file is corrupted
        except (OSError, ValueError, TypeError):
            logger.exception("Cannot read settings from %s; using defaults", self.path)
            return ReceiverSettings()

    # Saves the settings to the file
    def save(self, settings):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
