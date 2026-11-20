from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from harnice import fileio
from harnice.lists import instances_list


Point3D = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AvailableNode:
    node_id: str
    location: Point3D
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None


@dataclass
class AvailableSegment:
    segment_id: str
    location_at_end_a: Point3D
    location_at_end_b: Point3D
    spline_control_points: list[Point3D] = field(default_factory=list)


@dataclass
class AvailableNetwork:
    segments: list[AvailableSegment] = field(default_factory=list)
    nodes: list[AvailableNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def load():
    """
    Use this when a harness build needs the available network already stored in this revision.

    Load the available network from disk.

    If the file does not exist yet, returns an empty network
    (``{"segments": [], "nodes": []}``) and writes nothing.
    """
    path = Path(fileio.path("available network"))
    if not path.exists():
        return {"segments": [], "nodes": []}
    with open(path) as f:
        return json.load(f)


def save(network):
    """
    Use this when a harness build has changed the available network and the change belongs in ``available.json``.

    Replace this revision's available network file with ``network``.

    Everything the available network editor shows comes from this file, so
    a node or segment a build adds is only visible there once it is saved.

    ## Args

    - **network** — Network dict with ``"nodes"`` and ``"segments"``.
    """
    path = fileio.path("available network")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)


# ---------------------------------------------------------------------------
# Source of truth
# ---------------------------------------------------------------------------

# A node or segment drawn in the available network editor, or added by a
# build step that leaves it for you to edit.
GUI = "gui"
# A node or segment read from the source system's physical model. This is
# the routing context the console lists as "Source part physical model".
SOURCE_SYSTEM_CONTEXT = "source physical model.step"


def source_of_truth(item):
    """
    Use this when a harness build needs to know where an available-network node or segment comes from.

    Return the ``source_of_truth`` of a node or segment: ``"gui"``, or the
    id of the routing context it was read from.

    An item with no ``source_of_truth`` is ``"gui"``, except a node that
    carries a ``mate`` tag, which came from the source system
    (``SOURCE_SYSTEM_CONTEXT``).
    """
    if item.get("source_of_truth"):
        return item["source_of_truth"]
    if item.get("mate") or item.get("mates"):
        return SOURCE_SYSTEM_CONTEXT
    return GUI


def tag_source_of_truth(items, source):
    """
    Use this when a harness build adds nodes or segments read from a routing context to the available network.

    Return copies of ``items`` with ``source_of_truth`` set to ``source``.
    """
    tagged = []
    for item in items:
        item = dict(item)
        item["source_of_truth"] = source
        tagged.append(item)
    return tagged


def keep_only_gui(network):
    """
    Use this when a harness build is about to reload every routing context into the available network.

    Return a copy of ``network`` without the nodes and segments whose
    ``source_of_truth`` is not ``"gui"``. The build then adds them again,
    fresh from their contexts.
    """
    nodes = []
    for node in network.get("nodes", []):
        if source_of_truth(node) == GUI:
            nodes.append(dict(node))
    segments = []
    for segment in network.get("segments", []):
        if source_of_truth(segment) == GUI:
            segments.append(dict(segment))
    return {"nodes": nodes, "segments": segments}


def source_context_from_path(local_path=None, lib_repo=None, relative_path=None):
    """
    Use this when a harness build needs a STEP file copied into networks/contexts/ as routing context for this harness.

    Copy a STEP file into this harness as routing context.

    Pass either ``local_path`` or both ``lib_repo`` and ``relative_path``.
    The file is written to ``networks/contexts/`` under its own filename,
    replacing a context file of that name. Other files already in
    ``contexts/`` are left in place. The 3D available and chosen network
    pages load ``.step`` and ``.stp`` files from that folder.

    **Args:**
    - ``local_path`` (str, optional): Filesystem path to a ``.step`` or ``.stp`` file.
    - ``lib_repo`` (str, optional): Library repository URL from ``repository_locations.csv``.
    - ``relative_path`` (str, optional): Path of the STEP file under that repository.

    **Returns:**
    - ``str``: Path of the context file written into this harness.

    **Raises:**
    - ``ValueError``: If both sources are given, neither source is complete, the
      relative path leaves the repository, or the file is not a STEP file.
    - ``FileNotFoundError``: If the source file does not exist.
    """
    source = _resolve_context_source(local_path, lib_repo, relative_path)
    from harnice.project_types.harness import ensure_contexts_dir

    ensure_contexts_dir()
    destination = os.path.join(fileio.dirpath("contexts"), os.path.basename(source))
    shutil.copy2(source, destination)
    return destination


def source_available_network_from_project(project_mpn, project_subpath, project_repo):
    """
    Use this when a harness build should replace this revision's available network with the available network from another project.

    Copy another project's available network into this harness.

    The other project is the library tip (highest revision) of ``project_mpn``
    under ``project_repo`` and ``project_subpath``. Its available-network file
    replaces this harness's available network.

    **Args:**
    - ``project_mpn`` (str): Part-number folder of the source project.
    - ``project_subpath`` (str): Path under the repository that contains that
      part number. ``""`` when the part number sits at the repository root.
    - ``project_repo`` (str): Library repository URL from ``repository_locations.csv``.

    **Returns:**
    - ``dict``: The available network that was written.

    **Raises:**
    - ``ValueError``: If ``project_mpn`` or ``project_repo`` is blank, or the
      subpath leaves the repository.
    - ``FileNotFoundError``: If the part, its revision, or its available network
      file cannot be found.
    """
    project_mpn = (project_mpn or "").strip()
    project_subpath = (project_subpath or "").strip().strip("/\\")
    project_repo = (project_repo or "").strip()
    if not project_mpn:
        raise ValueError("project_mpn is required")
    if not project_repo:
        raise ValueError("project_repo is required")
    if project_mpn in (".", "..") or "/" in project_mpn or "\\" in project_mpn:
        raise ValueError("project_mpn must be a part-number folder name")

    from harnice.utils import library_utils

    root = os.path.normpath(
        library_utils.get_local_path(
            project_repo, mpn=project_mpn, lib_subpath=project_subpath
        )
    )
    source_lib_path = os.path.normpath(os.path.join(root, project_subpath, project_mpn))
    if os.path.commonpath([root, source_lib_path]) != root:
        raise ValueError("project_subpath escapes the library repository")
    if not os.path.isdir(source_lib_path):
        raise FileNotFoundError(
            f"No project {project_mpn!r} at {source_lib_path}"
        )

    source_folder_name, _rev, _highest, _tip = library_utils.resolve_mpn_revision(
        source_lib_path, project_mpn
    )
    rev_folder = os.path.join(source_lib_path, source_folder_name)
    relative = os.path.relpath(fileio.path("available network"), fileio.rev_directory())
    source_file = os.path.join(rev_folder, relative)
    if not os.path.isfile(source_file):
        raise FileNotFoundError(
            f"No available network for {project_mpn!r} at {source_file}"
        )

    destination = fileio.path("available network")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source_file, destination)
    with open(destination, encoding="utf-8") as f:
        return json.load(f)


def _resolve_context_source(local_path, lib_repo, relative_path):
    """Return the STEP path named by a local file or a library-relative path."""
    local_path = (local_path or "").strip()
    lib_repo = (lib_repo or "").strip()
    relative_path = (relative_path or "").strip()
    if local_path and (lib_repo or relative_path):
        raise ValueError(
            "Pass either local_path or lib_repo and relative_path, not both"
        )
    if local_path:
        source = os.path.expanduser(local_path)
    elif lib_repo and relative_path:
        if os.path.isabs(relative_path):
            raise ValueError("relative_path must be relative to the library repository")
        from harnice.utils import library_utils

        root = os.path.normpath(library_utils.get_local_path(lib_repo))
        source = os.path.normpath(os.path.join(root, relative_path))
        if os.path.commonpath([root, source]) != root:
            raise ValueError("relative_path escapes the library repository")
    else:
        raise ValueError("Pass local_path, or both lib_repo and relative_path")

    if not os.path.isfile(source):
        raise FileNotFoundError(f"No routing context STEP at {source}")
    name = os.path.basename(source)
    if name.startswith(".") or Path(name).suffix.lower() not in (".step", ".stp"):
        raise ValueError(f"Routing context must be a .step or .stp file, not {name!r}")
    return source
