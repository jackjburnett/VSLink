"""Validated, per-user receiver settings used by the CLI and tray."""

from dataclasses import asdict, dataclass
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceiverSettings:
    wifi_enabled: bool = True
    bluetooth_enabled: bool = True
    wifi_port: int = 8000

    def __post_init__(self):
        if type(self.wifi_enabled) is not bool or type(self.bluetooth_enabled) is not bool:
            raise ValueError("Transport settings must be true or false")
        if type(self.wifi_port) is not int or not 1 <= self.wifi_port <= 65535:
            raise ValueError("Wi-Fi port must be a number between 1 and 65535")


class SettingsStore:
    def __init__(self, path=None):
        directory = Path(os.environ.get("VLR_CONFIG_DIR") or (
            Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VSLink"
        ))
        self.path = Path(path) if path is not None else directory / "settings.json"

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return ReceiverSettings(**data)
        except FileNotFoundError:
            return ReceiverSettings()
        except (OSError, ValueError, TypeError):
            logger.exception("Cannot read settings from %s; using defaults", self.path)
            return ReceiverSettings()

    def save(self, settings):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
