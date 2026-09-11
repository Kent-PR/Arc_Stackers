"""Presentation translations; ARC_STACKERS_LANGUAGE selects the startup locale."""
import json
import logging
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
SUPPORTED_LANGUAGES = {"en": "English", "ru": "Русский"}
DEFAULT_LANGUAGE = "en"
logger = logging.getLogger(__name__)


def _load_catalog(path):
    """Flatten nested groups so callers can keep using dotted message keys."""
    messages = {}

    def visit(group, prefix=""):
        for name, value in group.items():
            key = f"{prefix}.{name}" if prefix else name
            if isinstance(value, dict):
                visit(value, key)
            elif isinstance(value, str):
                if key in messages:
                    raise ValueError(f"Duplicate translation key: {key}")
                messages[key] = value
            else:
                raise ValueError(f"Translation must be a string: {key}")

    visit(json.loads(path.read_text(encoding="utf-8")))
    return messages


class Translator:
    def __init__(self, language=DEFAULT_LANGUAGE, locales_dir=LOCALES_DIR):
        self.language = language
        directory = Path(locales_dir)
        self.fallback = _load_catalog(directory / "en.json")
        # Do not use an arbitrary locale string as a filesystem path.
        path = next((p for p in directory.glob("*.json") if p.stem == language), None)
        self.messages = _load_catalog(path) if path else {}
        self._missing = set()

    def t(self, key, **parameters):
        template = self.messages.get(key)
        if not template:
            if key not in self._missing:
                logger.warning("Missing translation: %s/%s", self.language, key)
                self._missing.add(key)
            template = self.fallback.get(key)
        return template.format(**parameters) if template else key


def describe_rep(rep, names, translator):
    parts = []
    for key in rep:
        material = names.get(key[1], key[1])
        if key[0] == "raw":
            parts.append(material)
        else:
            parts.append(translator.t(
                "representation.indirect", material=material,
                source=names.get(key[2], key[2]),
            ))
    return translator.t("representation.separator").join(sorted(parts))
