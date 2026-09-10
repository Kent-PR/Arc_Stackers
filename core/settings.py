"""User preferences, separate from disposable game-data caches."""
import json
import logging
import os
from pathlib import Path
import tempfile

from platformdirs import user_config_dir

SETTINGS_PATH = Path(user_config_dir("arc-storage-optimizer")) / "settings.json"
logger = logging.getLogger(__name__)


class Settings:
    """Load once per session; update individual keys without losing other settings."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else SETTINGS_PATH
        self.values = {}
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(values, dict):
                raise ValueError("Settings must be a JSON object")
            self.values = values
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            logger.warning("Cannot read settings %s: %s", self.path, error)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def update(self, **changes):
        """Atomically save changes. Return False on I/O failure, retaining old data."""
        values = {**self.values, **changes}
        payload = json.dumps(values, ensure_ascii=False, indent=2) + "\n"
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix="settings-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            logger.exception("Cannot save settings %s", self.path)
            return False
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Cannot remove temporary settings file %s", temporary)
        self.values = values
        return True
