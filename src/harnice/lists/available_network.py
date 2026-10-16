from __future__ import annotations
import json
import math
import os
import random
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
    Load the available network from disk.

    If the file does not exist yet, generates a starter network from harness node
    instances, writes it, and returns it:

    - **0 or 1 node instances:** raises ``ValueError``.
    - **2:** places them at ``(0, 0, 0)`` and ``(x, 0, 0)`` with ``x`` a random
      integer in ``[6, 18]``, connected by one segment.
    - **3 or more:** places a hub at ``(0, 0, 0)`` and each instance node at
      ``(r cos θ, r sin θ, 0)`` with ``r`` in ``[6, 18]`` and ``θ`` in ``[0, 359]``
      degrees, each connected to the hub by a spoke segment.
    """
    path = Path(fileio.path("available network"))
    if not path.exists():
        return _generate_from_instances(path)
    with open(path) as f:
        return json.load(f)


def _generate_from_instances(path: Path):
    node_names = [
        instance.get("instance_name")
        for instance in instances_list.read()
        if instance.get("item_type") == "node"
    ]

    if len(node_names) < 2:
        raise ValueError(
            "Not enough node instances in the harness to generate an available "
            f"network (found {len(node_names)}; need at least 2)."
        )

    nodes = []
    segments = []

    if len(node_names) == 2:
        x = float(random.randint(6, 18))
        loc_a = [0.0, 0.0, 0.0]
        loc_b = [x, 0.0, 0.0]
        nodes = [
            {
                "node_id": node_names[0],
                "location": loc_a,
                "alpha": None,
                "beta": None,
                "gamma": None,
            },
            {
                "node_id": node_names[1],
                "location": loc_b,
                "alpha": None,
                "beta": None,
                "gamma": None,
            },
        ]
        segments = [
            {
                "segment_id": "segment",
                "location_at_end_a": loc_a,
                "location_at_end_b": loc_b,
                "spline_control_points": [],
            }
        ]
    else:
        hub_loc = [0.0, 0.0, 0.0]
        nodes.append(
            {
                "node_id": "hub",
                "location": hub_loc,
                "alpha": None,
                "beta": None,
                "gamma": None,
            }
        )
        for name in node_names:
            r = random.randint(6, 18)
            theta = math.radians(random.randint(0, 359))
            loc = [r * math.cos(theta), r * math.sin(theta), 0.0]
            nodes.append(
                {
                    "node_id": name,
                    "location": loc,
                    "alpha": None,
                    "beta": None,
                    "gamma": None,
                }
            )
            segments.append(
                {
                    "segment_id": f"{name}_leg",
                    "location_at_end_a": list(hub_loc),
                    "location_at_end_b": loc,
                    "spline_control_points": [],
                }
            )

    network = {"segments": segments, "nodes": nodes}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)
    return network


def source_context_from_path(local_path=None, lib_repo=None, relative_path=None):
    """Copy a STEP file into this harness as routing context.

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
    """Copy another project's available network into this harness.

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
