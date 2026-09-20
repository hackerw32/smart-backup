"""Έλεγχος για νέες εκδόσεις μέσω GitHub Releases."""

import json
import urllib.error
import urllib.request

from .constants import UPDATE_API, RELEASES_URL

USER_AGENT = "SmartBackup"


def parse_version(text):
    parts = []
    for chunk in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for char in chunk:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(latest, current):
    return parse_version(latest) > parse_version(current)


def check_for_updates(current_version, timeout=8):
    request = urllib.request.Request(
        UPDATE_API,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "no_releases"}
        return {"status": "error", "error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    latest = str(data.get("tag_name") or "").lstrip("vV")
    url = data.get("html_url") or RELEASES_URL
    return {
        "status": "ok",
        "latest": latest,
        "url": url,
        "update": bool(latest) and is_newer(latest, current_version),
    }
