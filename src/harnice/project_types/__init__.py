"""Project type modules (harness, system, device, …)."""

import pkgutil

# Helper modules in this package that are not a user-selectable project kind.
_HELPERS = frozenset({"chtype"})
_PRIORITY = ("system", "harness", "device", "macro")
_FALLBACK = (
    "system",
    "harness",
    "device",
    "macro",
    "cable",
    "part",
    "tblock",
    "flagnote",
)


def available_names():
    """Project type names, including when this package is compiled (no ``.py`` files)."""
    names = []
    try:
        names = [
            info.name
            for info in pkgutil.iter_modules(__path__)
            if info.name not in _HELPERS
        ]
    except Exception:
        names = []
    if not names:
        for name in _FALLBACK:
            try:
                __import__(f"harnice.project_types.{name}", fromlist=[name])
            except ImportError:
                continue
            names.append(name)
    ordered = [name for name in _PRIORITY if name in names]
    ordered += sorted(name for name in names if name not in _PRIORITY)
    return ordered
