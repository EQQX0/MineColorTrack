"""Checks GitHub for a newer release and downloads its installer.

Uses the public GitHub API (no account needed), so the repository must be public.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from . import APP_NAME, UPDATE_REPO, __version__

API = "https://api.github.com/repos/%s/releases/latest"
TIMEOUT = 10


class UpdateError(Exception):
    pass


def parse_version(text):
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def is_newer(latest, current=__version__):
    return parse_version(latest) > parse_version(current)


def _get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "%s/%s" % (APP_NAME, __version__)})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def latest_release(repo=UPDATE_REPO):
    """{'version', 'tag', 'url', 'notes', 'installer': {'name', 'url', 'size'} or None}."""
    try:
        with _get(API % repo) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("No releases found. The repository %s may be private; the update check needs it to "
                              "be public." % repo)
        if exc.code == 403:
            raise UpdateError("GitHub refused the request (too many checks from this network). Try later.")
        raise UpdateError("GitHub answered %s." % exc.code)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError("Could not reach GitHub: %s" % getattr(exc, "reason", exc))
    installer = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.lower().startswith("minecolortrack-setup") and name.lower().endswith(".exe"):
            installer = {"name": name, "url": asset.get("browser_download_url"), "size": asset.get("size", 0)}
            break
    tag = data.get("tag_name", "")
    return {"version": ".".join(str(n) for n in parse_version(tag)), "tag": tag, "url": data.get("html_url", ""),
            "notes": data.get("body", "") or "", "installer": installer}


def check(repo=UPDATE_REPO):
    """Result for the app and `mct update`: current, latest, newer, url, installer."""
    rel = latest_release(repo)
    return {"current": __version__, "latest": rel["version"], "newer": is_newer(rel["version"]),
            "url": rel["url"], "installer": rel["installer"], "notes": rel["notes"]}


def download(installer, progress=None, folder=None):
    """Download the installer to a temp folder; progress(done_bytes, total_bytes) is called while it runs."""
    if not installer or not installer.get("url"):
        raise UpdateError("This release has no installer to download.")
    folder = folder or tempfile.mkdtemp(prefix="mct_update_")
    path = os.path.join(folder, os.path.basename(installer["name"]))
    total = int(installer.get("size") or 0)
    done = 0
    try:
        with _get(installer["url"], accept="application/octet-stream") as resp, open(path, "wb") as fh:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError("Download failed: %s" % getattr(exc, "reason", exc))
    if total and done != total:
        raise UpdateError("Download incomplete (%d of %d bytes)." % (done, total))
    return path


def run_installer(path):
    """Start the installer for an in-place update; it reopens MineColorTrack when it is done."""
    if sys.platform != "win32":
        raise UpdateError("Installing updates is only possible on Windows.")
    subprocess.Popen([path, "/SILENT", "/NORESTART", "/UPDATE=1"], close_fds=True)
