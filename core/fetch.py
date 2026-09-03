"""Downloads and caches the item data from RaidTheory/arcraiders-data
(https://github.com/RaidTheory/arcraiders-data - MIT license for the data
structure; game content remains (c) Embark Studios AB, not affiliated).

The cache lives OUTSIDE this project's git repo entirely (an OS-appropriate
cache directory via `platformdirs`), so there is nothing data-related to
.gitignore and nothing large to accidentally commit.

Flow on every app start (see ensure_data()):
  1. No cache yet              -> download.
  2. Cache exists, fresh check -> use cache as-is, no network call.
  3. Cache exists, stale check
     (or force_check=True)     -> ask GitHub for the latest commit SHA of
                                   the source repo (one small API call);
                                   only re-download if it changed.
"""
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import platformdirs

REPO = "RaidTheory/arcraiders-data"
BRANCH = "main"
APP_NAME = "arc-storage-optimizer"

CACHE_DIR = Path(platformdirs.user_cache_dir(APP_NAME))
ITEMS_DIR = CACHE_DIR / "items"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # don't hit the GitHub API more than once a day


def _read_manifest():
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_manifest(data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _latest_commit_sha():
    """One small call to the GitHub API - does NOT download any data."""
    url = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["sha"]


def _download_items(ref):
    """Downloads the repo zip at a given ref (branch name OR commit sha) and
    extracts only the items/ folder into ITEMS_DIR (replacing whatever was
    cached before). Uses codeload.github.com directly - this does NOT count
    against the api.github.com rate limit, only the small SHA-lookup does."""
    url = f"https://codeload.github.com/{REPO}/zip/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        zip_bytes = resp.read()

    if ITEMS_DIR.exists():
        for f in ITEMS_DIR.glob("*.json"):
            f.unlink()
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # entries look like "arcraiders-data-<ref>/items/xyz.json"
        item_entries = [n for n in zf.namelist() if "/items/" in n and n.endswith(".json")]
        for entry in item_entries:
            filename = entry.rsplit("/", 1)[-1]
            with zf.open(entry) as src:
                (ITEMS_DIR / filename).write_bytes(src.read())

    return len(item_entries)


def _try_latest_commit_sha():
    """Best-effort SHA lookup - returns None on any failure (offline, rate
    limited, etc.) instead of raising, since this is only used to decide
    whether a re-download is worthwhile, never to gate the download itself."""
    try:
        return _latest_commit_sha()
    except Exception:
        return None


def clear_cache():
    """Deletes the entire cache (data + manifest). Safe to call even if
    nothing was ever downloaded. Meant to be wired to a "Reset data" /
    "Clear cache" button in Settings, so the user never has to go hunting
    for this folder manually."""
    import shutil
    shutil.rmtree(CACHE_DIR, ignore_errors=True)


def open_cache_folder():
    """Opens the cache folder in the OS file explorer, for the rare case
    someone wants to look inside manually. Also wired to Settings."""
    import subprocess
    import sys

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import os
        os.startfile(CACHE_DIR)  # noqa: S606 - intentional, user-triggered only
    elif sys.platform == "darwin":
        subprocess.run(["open", str(CACHE_DIR)], check=False)
    else:
        subprocess.run(["xdg-open", str(CACHE_DIR)], check=False)


def ensure_data(force_check=False, on_status=None):
    """Makes sure ITEMS_DIR has usable data, downloading/updating as needed.
    Returns the path to the items directory.

    on_status: optional callback(str) for UI progress messages (e.g. feed
    into a loading screen). Safe to leave as None for a silent/CLI run.
    """
    def status(msg):
        if on_status:
            on_status(msg)

    manifest = _read_manifest()
    have_data = ITEMS_DIR.exists() and any(ITEMS_DIR.glob("*.json"))
    last_checked = manifest.get("last_checked", 0)
    check_is_stale = (time.time() - last_checked) > CHECK_INTERVAL_SECONDS

    if not have_data:
        status("Downloading item data (first run)...")
        # Download by branch name directly - no API call needed, so this
        # can't be blocked by GitHub's API rate limit (codeload.github.com
        # is a separate, much more generous path).
        count = _download_items(BRANCH)
        sha = _try_latest_commit_sha()  # nice-to-have for future update checks, not required
        _write_manifest({"sha": sha, "last_checked": time.time() if sha else 0, "item_count": count})
        status(f"Downloaded {count} items.")
        return str(ITEMS_DIR)

    if force_check or check_is_stale:
        status("Checking for data updates...")
        sha = _try_latest_commit_sha()
        if sha is None:
            status("Could not check for updates right now, using cached data.")
            return str(ITEMS_DIR)

        if sha != manifest.get("sha"):
            status("New version found, downloading...")
            count = _download_items(sha)
            _write_manifest({"sha": sha, "last_checked": time.time(), "item_count": count})
            status(f"Updated to {count} items.")
        else:
            manifest["last_checked"] = time.time()
            _write_manifest(manifest)
            status("Data is up to date.")

    return str(ITEMS_DIR)
