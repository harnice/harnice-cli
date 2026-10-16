"""Restrict imports while user build-instruction scripts run.

List, utility, and channel-type modules (plus fileio, state, and cli) are
placed in the script namespace before it runs, so build instructions do not
need to import anything from harnice.
"""

import builtins
import importlib
import pkgutil
import runpy

_PUBLIC_FROM_HARNICE = frozenset(
    {"fileio", "state", "cli", "lists", "utils", "project_types"}
)
_PUBLIC_EXACT = frozenset(
    {
        "harnice",
        "harnice.fileio",
        "harnice.state",
        "harnice.cli",
        "harnice.lists",
        "harnice.utils",
        "harnice.project_types",
        "harnice.project_types.chtype",
    }
)

_FALLBACK_LISTS = (
    "available_network",
    "cached_tsv",
    "channel_map",
    "chosen_network",
    "circuits_list",
    "flattened_network",
    "instances_list",
    "library_history",
    "passthrough_map",
    "post_harness_instances_list",
    "rev_history",
    "signals_list",
)
_FALLBACK_UTILS = (
    "appearance",
    "block_diagram_utils",
    "build_utils",
    "bundle_network_utils",
    "cable_utils",
    "circuit_utils",
    "library_utils",
    "note_utils",
    "pdf_drawings_utils",
    "step_utils",
    "svg_utils",
    "system_symbol_utils",
    "system_utils",
)

_PUBLIC_GLOBALS_CACHE = None


def _denied(name):
    return ImportError(
        f"Build instructions cannot import {name}. "
        "List, utility, and channel-type modules (and fileio, state, cli) "
        "are already available by name — see the console ribbon."
    )


def _check_import(name, fromlist=()):
    if not name.startswith("harnice"):
        return
    if name == "harnice":
        for item in fromlist or ():
            if item in ("*",) or str(item).startswith("_"):
                continue
            if item not in _PUBLIC_FROM_HARNICE:
                raise _denied(f"harnice.{item}")
        return
    if name.startswith("harnice.lists.") or name.startswith("harnice.utils."):
        return
    if name.startswith("harnice.lists") or name.startswith("harnice.utils"):
        return
    if name == "harnice.project_types":
        for item in fromlist or ():
            if item in ("*",) or str(item).startswith("_"):
                continue
            if item != "chtype":
                raise _denied(f"harnice.project_types.{item}")
        return
    if name in _PUBLIC_EXACT:
        return
    raise _denied(name)


def _modules_in_package(package, fallback_names):
    found = {}
    names = []
    try:
        names = [
            info.name
            for info in pkgutil.iter_modules(package.__path__)
            if not info.name.startswith("_")
        ]
    except Exception:
        names = []
    if not names:
        names = list(fallback_names)
    for name in names:
        if name.startswith("_"):
            continue
        found[name] = importlib.import_module(f"{package.__name__}.{name}")
    return found


def public_globals():
    """Names already bound when project build instructions (and macros) run."""
    global _PUBLIC_GLOBALS_CACHE
    if _PUBLIC_GLOBALS_CACHE is not None:
        return dict(_PUBLIC_GLOBALS_CACHE)

    import harnice.lists
    import harnice.utils
    from harnice import cli, fileio, state
    from harnice.project_types import chtype

    g = {
        "fileio": fileio,
        "state": state,
        "cli": cli,
        "chtype": chtype,
    }
    g.update(_modules_in_package(harnice.lists, _FALLBACK_LISTS))
    g.update(_modules_in_package(harnice.utils, _FALLBACK_UTILS))
    _PUBLIC_GLOBALS_CACHE = g
    return dict(g)


def run_path(script_path, run_name="__main__", init_globals=None):
    """``runpy.run_path`` with Harnice internals hidden from the script."""
    merged = public_globals()
    if init_globals:
        merged.update(init_globals)

    real_import = builtins.__import__

    def gated_import(name, globals=None, locals=None, fromlist=(), level=0):
        origin = (globals or {}).get("__name__") or ""
        # Harnice's own modules may import each other; only gate the user script.
        if not (isinstance(origin, str) and origin.startswith("harnice")):
            _check_import(name, fromlist)
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = gated_import
    try:
        return runpy.run_path(
            script_path, run_name=run_name, init_globals=merged
        )
    finally:
        builtins.__import__ = real_import
