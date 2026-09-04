"""Lazy, persistent cache for item artwork referenced by item JSON."""

import hashlib
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .fetch import APP_NAME, CACHE_DIR


IMAGES_DIR = CACHE_DIR / "images"
IMAGE_DOWNLOAD_TIMEOUT = 20

_locks_guard = threading.Lock()
_download_locks = {}


def _download_lock(url):
    """Return one process-local lock per URL to prevent duplicate downloads."""
    with _locks_guard:
        return _download_locks.setdefault(url, threading.Lock())


def _cache_path(item_id, url):
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".img"
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in item_id)
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return IMAGES_DIR / f"{safe_id}-{url_hash}{suffix}"


def get_cached_image(item_id, url):
    """Download an image once and return its bytes, or ``None`` on failure.

    The URL hash in the filename automatically invalidates an old cached image
    when the data source changes its URL. A temporary file is renamed only
    after a complete download, so interrupted requests never poison the cache.
    """
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None

    destination = _cache_path(item_id, url)
    with _download_lock(url):
        try:
            if destination.is_file() and destination.stat().st_size:
                return destination.read_bytes()

            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": APP_NAME},
            )
            with urllib.request.urlopen(request, timeout=IMAGE_DOWNLOAD_TIMEOUT) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/") and content_type != "application/octet-stream":
                    return None
                image_bytes = response.read()

            if not image_bytes:
                return None

            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(image_bytes)
            temporary.replace(destination)
            return image_bytes
        except (OSError, ValueError):
            return None
