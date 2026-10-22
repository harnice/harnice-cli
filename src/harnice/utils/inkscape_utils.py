"""Find the Inkscape executable used to export drawing PDFs.

PDF pages are SVG. Inkscape turns each page into PDF. It is a separate
program the customer installs; Harnice remembers the path it found.
"""

from __future__ import annotations

import json
import os
import shutil
import sys

from harnice import fileio

INKSCAPE_RELEASE_URL = "https://inkscape.org/release/"


class InkscapeNotFoundError(RuntimeError):
    """PDF export ran and Inkscape is not installed."""


def inkscape_required_message():
    """One sentence a build can show when PDF export cannot run."""
    return (
        "PDF export needs Inkscape. Install it from "
        f"{INKSCAPE_RELEASE_URL} and build again."
    )


def remember_inkscape():
    """Store Inkscape's path when it is installed. Return that path, or None.

    A build calls this before macros run. Drawing export then finds the same
    path. Projects that never export a PDF are unchanged when Inkscape is absent.
    """
    try:
        return resolve_inkscape()
    except InkscapeNotFoundError:
        return None


def resolve_inkscape(*, remember=True, candidates=None):
    """Return a usable Inkscape binary, remembering it for the next build.

    Search order: a working path already saved in ``paths/paths.json``,
    ``inkscape`` on ``PATH``, the macOS app, Homebrew, then Windows
    Program Files. A saved path that no longer exists is skipped.

    **Raises:**
    - `InkscapeNotFoundError`: Nothing on the search list is an executable.
    """
    saved = _saved_path()
    if _usable(saved):
        return saved

    for candidate in _search_list(candidates):
        if not _usable(candidate) or _same_path(candidate, saved):
            continue
        if remember:
            _remember(candidate)
        return candidate

    raise InkscapeNotFoundError(inkscape_required_message())


def _paths_file():
    return os.path.join(fileio.harnice_root(), "paths", "paths.json")


def _read_paths():
    path = _paths_file()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _saved_path():
    value = _read_paths().get("inkscape")
    if isinstance(value, str):
        return value.strip()
    return ""


def _remember(binary):
    """Write ``inkscape`` into paths.json, keeping any other keys."""
    data = _read_paths()
    if data.get("inkscape") == binary:
        return
    data["inkscape"] = binary
    path = _paths_file()
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def _search_list(candidates):
    if candidates is not None:
        return list(candidates)
    found = []
    on_path = shutil.which("inkscape")
    if on_path:
        found.append(on_path)
    if sys.platform == "darwin":
        found.extend(_mac_candidates())
    elif sys.platform == "win32":
        found.extend(_windows_candidates())
    else:
        found.extend(_mac_candidates())
        found.extend(_windows_candidates())
    return found


def _mac_candidates():
    home = os.path.expanduser("~")
    return [
        "/Applications/Inkscape.app/Contents/MacOS/inkscape",
        os.path.join(home, "Applications", "Inkscape.app", "Contents", "MacOS", "inkscape"),
        "/opt/homebrew/bin/inkscape",
        "/usr/local/bin/inkscape",
    ]


def _windows_candidates():
    bases = []
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        bases.append(os.path.join(program_files, "Inkscape", "bin"))
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    if program_files_x86 and program_files_x86 != program_files:
        bases.append(os.path.join(program_files_x86, "Inkscape", "bin"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        bases.append(os.path.join(local, "Programs", "Inkscape", "bin"))
    binaries = []
    for base in bases:
        binaries.append(os.path.join(base, "inkscape.com"))
        binaries.append(os.path.join(base, "inkscape.exe"))
    return binaries


def _usable(path):
    if not path or not isinstance(path, str):
        return False
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _same_path(left, right):
    if not left or not right:
        return False
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))
