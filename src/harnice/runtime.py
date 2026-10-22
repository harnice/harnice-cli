"""How this process was launched (dev interpreter vs standalone app)."""

import os
import subprocess
import sys
from pathlib import Path

# Nuitka sets this in compiled modules; it is absent when running from source.
_COMPILED = "__compiled__" in globals()

# Public download / release notes (harnice.io points here, not the source repo).
HARNICE_APP_RELEASES_LATEST = (
    "https://github.com/harnice/harnice-app-releases/releases/latest"
)
HARNICE_WEBSITE_URL = "https://harnice.io/"
HARNICE_BUY_URL = "https://buy.stripe.com/dRmaER6AK2Eh5hs2KFb7y00"


def _macos_bundle_executable():
    """``Harnice.app`` binary from Launch Services, or None when not in a bundle."""
    if sys.platform != "darwin":
        return None
    try:
        from Foundation import NSBundle
    except ImportError:
        return None
    path = NSBundle.mainBundle().executablePath()
    if not path:
        return None
    exe = Path(path)
    if not exe.is_file() or exe.name != "Harnice":
        return None
    return exe


def _bundle_dir():
    """Folder that contains the Harnice binary and ``harnice-data``, or None.

    Nuitka standalone leaves ``sys.executable`` pointing at the system Python,
    and Finder often starts the app with a bare ``sys.argv[0]``, so also ask
    the macOS bundle and walk a few parents for ``harnice-data``.
    """
    candidates = []
    mac_exe = _macos_bundle_executable()
    if mac_exe is not None:
        candidates.append(mac_exe)
    if sys.argv and sys.argv[0]:
        raw = Path(sys.argv[0])
        candidates.append(raw.resolve() if raw.exists() else raw)
    candidates.append(Path(sys.executable).resolve())
    seen = set()
    for binary in candidates:
        start = binary.parent if binary.suffix or binary.is_file() else binary
        for folder in (start, *start.parents[:4]):
            if folder in seen:
                continue
            seen.add(folder)
            if (folder / "harnice-data").is_dir():
                return folder
            if (
                folder.name == "MacOS"
                and folder.parent.name == "Contents"
                and (folder / "Harnice").is_file()
            ):
                return folder
    return None


def is_standalone_app():
    """True when running as Harnice.app / Harnice.exe, not a system Python."""
    if _COMPILED or getattr(sys, "frozen", False):
        return True
    return _bundle_dir() is not None


def app_executable():
    """Path used to re-invoke this process (binary when frozen, else Python)."""
    bundled = _bundle_dir()
    if bundled is not None:
        name = "Harnice.exe" if sys.platform == "win32" else "Harnice"
        candidate = bundled / name
        if candidate.is_file():
            return candidate
        if sys.argv and sys.argv[0]:
            argv0 = Path(sys.argv[0]).resolve()
            if argv0.is_file():
                return argv0
    return Path(sys.executable).resolve()


def standalone_install_root():
    """``.app`` bundle or Windows folder this process should replace.

    ``None`` for a source checkout, or when the layout is not a shipped build.
    """
    if not is_standalone_app():
        return None
    bundled = _bundle_dir()
    if bundled is None:
        return None
    if sys.platform == "darwin":
        if bundled.name == "MacOS" and bundled.parent.name == "Contents":
            app = bundled.parent.parent
            binary = app / "Contents" / "MacOS" / "Harnice"
            if app.suffix == ".app" and binary.is_file():
                return app
        return None
    if sys.platform == "win32":
        if (bundled / "Harnice.exe").is_file() and (bundled / "harnice-data").is_dir():
            return bundled
        return None
    return None


def source_src_dir():
    """``src/`` of the Harnice checkout that provided this ``runtime`` module."""
    return Path(__file__).resolve().parents[1]


def source_checkout_root():
    """Clone root of the Harnice checkout that provided this ``runtime`` module."""
    return Path(__file__).resolve().parents[2]


def no_console_kwargs():
    """Stop Windows from opening a console for a child process.

    Harnice.exe is a windowed app. A console program such as git otherwise
    gets its own console, which flashes open and closed.
    """
    if sys.platform != "win32":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _git_describe(cwd):
    """``git describe --tags --always`` for *cwd*, or ``""`` if unavailable."""
    try:
        return (
            subprocess.check_output(
                ["git", "describe", "--tags", "--always"],
                cwd=str(cwd),
                stderr=subprocess.DEVNULL,
                **no_console_kwargs(),
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return ""


def harnice_tag():
    """Version tag this process is running (e.g. ``v0.7.9`` or ``v0.7.9-2-gabc``).

    Source checkouts prefer ``git describe`` so a stale editable install does not
    misreport. Standalone apps use the installed package version from metadata.
    """
    if not is_standalone_app():
        described = _git_describe(source_checkout_root())
        if described:
            return described
    try:
        from importlib.metadata import version

        ver = (version("harnice") or "").strip()
        if ver:
            return ver if ver[:1] in "vV" else f"v{ver}"
    except Exception:
        pass
    return ""


def apply_source_checkout_env(env=None):
    """Pin ``PYTHONPATH`` and ``HARNICE_ROOT`` to this source checkout.

    ``python -m harnice`` otherwise follows a pip editable install, which can
    be a different clone than the one that launched ``serve_console.py``.
    Standalone apps leave *env* unchanged.
    """
    target = os.environ if env is None else env
    if is_standalone_app():
        return target
    src = str(source_src_dir())
    if not (target.get("HARNICE_ROOT") or "").strip():
        target["HARNICE_ROOT"] = str(source_checkout_root())
    existing = target.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    src_norm = os.path.normpath(src)
    parts = [p for p in parts if os.path.normpath(p) != src_norm]
    target["PYTHONPATH"] = src if not parts else src + os.pathsep + os.pathsep.join(parts)
    return target


def harnice_argv(*args):
    """Argv to invoke Harnice with ``args`` (e.g. ``'-b'``).

    From source, callers must pass ``env=apply_source_checkout_env(os.environ.copy())``
    (or inherit an environment already pinned by ``apply_source_checkout_env()``)
    so the child uses this clone instead of another checkout's editable install.
    """
    if is_standalone_app():
        return [str(app_executable()), *args]
    return [sys.executable, "-m", "harnice", *args]


def bundled_data_root():
    """Folder of GUI/defaults/favicon copied into the standalone app, or None."""
    parent = _bundle_dir()
    if parent is None:
        return None
    path = parent / "harnice-data"
    return path if path.is_dir() else None


def bundled_gui_dir():
    root = bundled_data_root()
    if root is None:
        return None
    gui = root / "gui"
    return gui if gui.is_dir() else None


def bundled_defaults_dir():
    root = bundled_data_root()
    if root is None:
        return None
    defaults = root / "defaults"
    return defaults if defaults.is_dir() else None


def bundled_favicon():
    root = bundled_data_root()
    if root is None:
        return None
    icon = root / "favicon.png"
    return icon if icon.is_file() else None


def hide_from_dock():
    """Hide this process from the Dock (macOS GUI-server children)."""
    if sys.platform != "darwin":
        return
    try:
        import AppKit
    except ImportError:
        return
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)


def user_data_dir():
    """Writable Harnice data (console state, repository_locations.csv, setup progress).

    Source checkouts use that clone's root (or ``HARNICE_ROOT`` if set) so each
    ``serve_console.py`` keeps its own ``repository_locations.csv``. The
    standalone app always uses the OS app-data folder.
    """
    if is_standalone_app():
        if sys.platform == "darwin":
            path = Path.home() / "Library" / "Application Support" / "Harnice"
        elif sys.platform == "win32":
            path = Path(os.environ.get("APPDATA", str(Path.home()))) / "Harnice"
        else:
            path = Path.home() / ".harnice"
        path.mkdir(parents=True, exist_ok=True)
        return path
    override = (os.environ.get("HARNICE_ROOT") or "").strip()
    if override:
        return Path(override)
    return source_checkout_root()
