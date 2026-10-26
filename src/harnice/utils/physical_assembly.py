"""System physical assembly.

Each placed device that has ``body.step`` is one solid in the system's
``assembly.step``. Poses and fasten mates live in ``physical.json``, which is
the file the console edits. The STEP file is rewritten from that.

A pose is inches and ZYX Euler degrees, the same frame as a device mate
connector and a harness 3D node: ``R = Rx(alpha) · Ry(beta) · Rz(gamma)``.

A fasten mate locks all six degrees of freedom of device ``b``. Its mate
connector is placed on device ``a``'s with no offset: the two connector
frames coincide, origin and orientation. ``flip`` is still a full lock. It
turns that target 180° about the connector's X axis, so the two Z axes
point opposite ways and the parts sit face to face. There is no residual
translation or rotation, and no degree of freedom is left free. An offset
along a mate, or a mate that unlocks a degree of freedom, is not part of
this model.

The pose stored for ``b`` is the result of that lock, not an input to it.
Solving the mate replaces whatever placement was saved for the moving
device. A device can be the moving side of only one mate. Mates are solved
dependency-first: a device is moved only after the device it fastens to has
been placed, so a chain follows the root.

``fixed`` names devices whose pose is grounded. A grounded device is never
the moving side of a mate, and its placement is left as stored.
"""

import json
import os

from harnice.utils.bundle_network_utils import (
    _euler_zyx_from_matrix,
    _matmul3,
    _rotate3,
    _zyx_rotation_matrix,
)

INCH_TO_MM = 25.4
NEW_DEVICE_GAP_IN = 24.0
_POSE_KEYS = ("x", "y", "z", "alpha", "beta", "gamma")
_ANGLE_KEYS = ("alpha", "beta", "gamma")


def _safe_refdes(name):
    if not isinstance(name, str) or not name.strip() or name.strip() != name:
        return False
    if name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        return False
    return True


def _round_pose(pose):
    return {key: round(float(pose[key]), 6) for key in _POSE_KEYS}


def _identity_pose():
    return {key: 0.0 for key in _POSE_KEYS}


def normalize_assembly(data):
    """Return placements and fasten mates, or raise ValueError."""

    def _number(label, value):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{label} must be a number")
        try:
            got = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number") from exc
        if got != got or got == float("inf") or got == float("-inf"):
            raise ValueError(f"{label} must be a finite number")
        return got

    def _pose(value):
        if not isinstance(value, dict):
            raise ValueError("a placement must be an object")
        pose = {}
        for key in _POSE_KEYS:
            raw = value.get(key, 0)
            pose[key] = _number(key, 0 if raw in (None, "") else raw)
        return pose

    def _endpoint(value, label):
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        device = str(value.get("device") or "").strip()
        mate = str(value.get("mate") or "").strip()
        if not device or not mate:
            raise ValueError(f"{label} needs a device and a mate connector")
        if not _safe_refdes(device):
            raise ValueError(f"{label} device is not a refdes")
        return {"device": device, "mate": mate}

    def _fixed_names(raw):
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError("fixed must be a list")
        names = []
        seen = set()
        for item in raw:
            if not isinstance(item, str):
                raise ValueError("fixed needs a device refdes")
            name = item.strip()
            if name != item or not _safe_refdes(name):
                raise ValueError("fixed needs a device refdes")
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
        return names

    if not isinstance(data, dict):
        raise ValueError("physical assembly must be a JSON object")
    raw_placements = data.get("placements")
    if raw_placements is None:
        raw_placements = {}
    if not isinstance(raw_placements, dict):
        raise ValueError("placements must be an object")
    placements = {}
    for refdes, pose in raw_placements.items():
        name = str(refdes).strip()
        if not _safe_refdes(name):
            raise ValueError("a placement needs a device refdes")
        placements[name] = _pose(pose)

    raw_mates = data.get("mates")
    if raw_mates is None:
        raw_mates = []
    if not isinstance(raw_mates, list):
        raise ValueError("mates must be a list")
    mates = []
    for mate in raw_mates:
        if not isinstance(mate, dict):
            raise ValueError("each mate must be an object")
        flip = mate.get("flip", False)
        if not isinstance(flip, bool):
            raise ValueError("flip must be true or false")
        a = _endpoint(mate.get("a"), "mate a")
        b = _endpoint(mate.get("b"), "mate b")
        if a["device"] == b["device"] and a["mate"] == b["mate"]:
            raise ValueError("a mate cannot fasten a connector to itself")
        if a["device"] == b["device"]:
            raise ValueError("a mate has to join two devices")
        mates.append({"a": a, "b": b, "flip": flip})
    return {"placements": placements, "mates": mates, "fixed": _fixed_names(data.get("fixed"))}


def discover(root=None):
    """Devices under ``instance_data/device``. A body is that folder's ``body.step``."""
    from harnice import fileio
    from harnice.utils import physical_body

    def _contained_dir(root, name):
        root_real = os.path.realpath(root)
        path = os.path.realpath(os.path.join(root_real, name))
        if path != root_real and not path.startswith(root_real + os.sep):
            return None
        if not os.path.isdir(path):
            return None
        return path

    if root is None:
        root = os.path.join(fileio.dirpath("instance_data"), "device")
    if not os.path.isdir(root):
        return []
    found = []
    for name in sorted(os.listdir(root)):
        if not _safe_refdes(name):
            continue
        folder = _contained_dir(root, name)
        if folder is None:
            continue
        step_path = os.path.join(folder, "body.step")
        has_body = os.path.isfile(step_path)
        mates = []
        mates_error = ""
        if has_body:
            try:
                body = physical_body.load_body(os.path.join(folder, "attributes.json"))
            except ValueError as exc:
                mates_error = str(exc)
            else:
                if body is not None:
                    mates = body["mate_connectors"]
        found.append({
            "refdes": name,
            "has_body": has_body,
            "step_path": step_path if has_body else "",
            "mates": mates,
            "mates_error": mates_error,
        })
    return found


def _mate_index(discovered):
    index = {}
    for device in discovered:
        if not device["has_body"] or device.get("mates_error"):
            continue
        index[device["refdes"]] = {mate["id"]: mate for mate in device["mates"]}
    return index


def sanitize_mates(mates, discovered, strict=False, fixed=()):
    """Keep fasten mates whose connectors exist. ``strict`` raises instead of dropping."""

    def _closes_cycle(kept, mate):
        def _reaches(graph, start, goal):
            stack = [start]
            seen = set()
            while stack:
                node = stack.pop()
                if node == goal:
                    return True
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(graph.get(node, ()))
            return False

        graph = {}
        for item in kept:
            graph.setdefault(item["b"]["device"], []).append(item["a"]["device"])
        return _reaches(graph, mate["a"]["device"], mate["b"]["device"])

    index = _mate_index(discovered)
    with_body = {device["refdes"] for device in discovered if device["has_body"]}
    fixed_names = set(fixed or ())
    kept = []
    seen_b = set()
    seen_pair = set()
    for mate in mates:
        a = mate["a"]
        b = mate["b"]
        pair = (a["device"], a["mate"], b["device"], b["mate"])
        problem = ""
        if a["device"] not in with_body or b["device"] not in with_body:
            problem = "a mate names a device with no body"
        elif a["device"] not in index or b["device"] not in index:
            problem = "a mate names a device whose connectors could not be read"
        elif a["mate"] not in index[a["device"]]:
            problem = f"{a['device']} has no mate connector {a['mate']}"
        elif b["mate"] not in index[b["device"]]:
            problem = f"{b['device']} has no mate connector {b['mate']}"
        elif b["device"] in fixed_names:
            problem = f"{b['device']} is fixed"
        elif b["device"] in seen_b:
            problem = f"{b['device']} is already held by a mate"
        elif pair in seen_pair:
            problem = "duplicate mate"
        elif _closes_cycle(kept, mate):
            problem = f"mate cycle includes {b['device']}"
        if problem:
            if strict:
                raise ValueError(problem)
            continue
        seen_b.add(b["device"])
        seen_pair.add(pair)
        kept.append(mate)
    return kept


def place_new_devices(placements, refdes_list):
    """Copy ``placements`` and give each missing refdes an open spot on +X."""
    placed = {name: _round_pose(placements[name]) for name in placements}
    for refdes in refdes_list:
        if refdes in placed:
            continue
        pose = _identity_pose()
        if placed:
            pose["x"] = max(item["x"] for item in placed.values()) + NEW_DEVICE_GAP_IN
        placed[refdes] = pose
    return placed


def frame_of(pose, mate, flip=False):
    """Mate connector frame in the system, as ``(rotation, origin)``."""
    device_r = _zyx_rotation_matrix(pose["alpha"], pose["beta"], pose["gamma"])
    mate_r = _zyx_rotation_matrix(mate["alpha"], mate["beta"], mate["gamma"])
    rotation = _matmul3(device_r, mate_r)
    if flip:
        rotation = _matmul3(rotation, _zyx_rotation_matrix(180.0, 0.0, 0.0))
    offset = _rotate3(device_r, tuple(mate["location"]))
    origin = (
        pose["x"] + offset[0],
        pose["y"] + offset[1],
        pose["z"] + offset[2],
    )
    return rotation, origin


def solve_moving_pose(fixed_pose, fixed_mate, moving_mate, flip=False):
    """Pose of the moving device that puts its mate connector on the fixed one."""
    target_r, target_t = frame_of(fixed_pose, fixed_mate, flip=False)
    if flip:
        target_r = _matmul3(target_r, _zyx_rotation_matrix(180.0, 0.0, 0.0))
    moving_r = _zyx_rotation_matrix(
        moving_mate["alpha"], moving_mate["beta"], moving_mate["gamma"]
    )
    device_r = _matmul3(target_r, [[moving_r[row][col] for row in range(3)] for col in range(3)])
    offset = _rotate3(device_r, tuple(moving_mate["location"]))
    alpha, beta, gamma = _euler_zyx_from_matrix(device_r)
    return _round_pose({
        "x": target_t[0] - offset[0],
        "y": target_t[1] - offset[1],
        "z": target_t[2] - offset[2],
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    })


def _ordered_mates(mates):
    """Solve a holding device before any device fastened to it."""
    pending = list(mates)
    ordered = []
    while pending:
        rest = []
        for mate in pending:
            holder = mate["a"]["device"]
            if any(item["b"]["device"] == holder for item in pending):
                rest.append(mate)
                continue
            ordered.append(mate)
        if len(rest) == len(pending):
            ordered.extend(rest)
            break
        pending = rest
    return ordered


def apply_mates(placements, mates, discovered):
    """Replace each moving device's pose with the six-degree lock.

    The stored pose of a moving device is discarded. Its connector frame
    becomes the holding connector's frame, with no offset. ``flip`` turns
    the target 180° about X and still leaves nothing free.
    """
    index = _mate_index(discovered)
    result = {name: _round_pose(placements[name]) for name in placements}
    for mate in _ordered_mates(mates):
        holder = mate["a"]["device"]
        if holder not in result:
            continue
        fixed = index[mate["a"]["device"]][mate["a"]["mate"]]
        moving = index[mate["b"]["device"]][mate["b"]["mate"]]
        result[mate["b"]["device"]] = solve_moving_pose(
            result[holder],
            fixed,
            moving,
            mate["flip"],
        )
    return result


def locked_placements(discovered, model):
    """Placements after every mate has locked the moving device.

    A moving device whose holder is not placed is left out of the solve.
    One further down a chain is solved once its holder has been.
    """
    placements = {
        name: _round_pose(pose) for name, pose in model["placements"].items()
    }
    mates = sanitize_mates(
        model["mates"], discovered, strict=False, fixed=model.get("fixed") or []
    )
    solvable = []
    placed = set(placements)
    for mate in _ordered_mates(mates):
        if mate["a"]["device"] not in placed:
            continue
        solvable.append(mate)
        placed.add(mate["b"]["device"])
    return apply_mates(placements, solvable, discovered)


def reconcile(discovered, saved, strict_mates=False):
    """Drop missing devices, place new bodies, and solve mates."""

    def _models_close(a, b):
        def _poses_close(a, b):
            for key in _POSE_KEYS:
                delta = a[key] - b[key]
                if key in _ANGLE_KEYS:
                    delta = (delta + 180.0) % 360.0 - 180.0
                if abs(delta) > 1e-4:
                    return False
            return True

        if list(a.get("fixed") or []) != list(b.get("fixed") or []):
            return False
        if list(a["mates"]) != list(b["mates"]):
            return False
        if set(a["placements"]) != set(b["placements"]):
            return False
        for name in a["placements"]:
            if not _poses_close(a["placements"][name], b["placements"][name]):
                return False
        return True

    body_ids = [device["refdes"] for device in discovered if device["has_body"]]
    body_set = set(body_ids)
    placements = {
        name: pose
        for name, pose in saved["placements"].items()
        if name in body_set
    }
    placements = place_new_devices(placements, body_ids)
    fixed = [name for name in saved["fixed"] if name in body_set]
    mates = sanitize_mates(saved["mates"], discovered, strict=strict_mates, fixed=fixed)
    placements = apply_mates(placements, mates, discovered)
    model = {"placements": placements, "mates": mates, "fixed": fixed}
    return model, not _models_close(model, saved)


def load_assembly(path):
    """Read ``physical.json``. Missing file is an empty assembly."""
    if not path or not os.path.isfile(path):
        return {"placements": {}, "mates": [], "fixed": []}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"physical.json could not be read: {exc}") from exc
    return normalize_assembly(data)


def save_assembly(model, path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(model, handle, indent=4)
        handle.write("\n")
    os.replace(temporary, path)


def _assembly_paths():
    from harnice import fileio

    return fileio.path("physical assembly"), fileio.path("assembly")


def _library_by_refdes():
    """Part identity of each placed device, from the block diagram."""
    from harnice import fileio

    try:
        path = fileio.path("block diagram")
    except Exception:
        return {}
    if not path or not os.path.isfile(path):
        return {}
    from harnice.utils import block_diagram_utils

    try:
        root = block_diagram_utils._parse_block_diagram_svg_file(path).getroot()
    except Exception:
        return {}
    parent_map = block_diagram_utils._svg_build_parent_map(root)
    found = {}
    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "g":
            continue
        parent = parent_map.get(el)
        if parent is None or (parent.get("id") or "") not in block_diagram_utils._SVG_DEVICES_PARENT_GROUP_IDS:
            continue
        refdes = block_diagram_utils._refdes_from_device_group(el)
        if not refdes:
            continue
        found[refdes] = {
            "mpn": (el.get("mpn") or "").strip(),
            "lib_repo": (el.get("lib_repo") or "").strip(),
            "lib_subpath": (el.get("lib_subpath") or "").strip(),
            "rev": (el.get("rev") or "").strip(),
        }
    return found


def system_available_network_path():
    """Absolute ``available_network.json`` for the open system."""
    from harnice import fileio

    return fileio.path("available network")


def mating_connector_nodes(discovered, placements):
    """Available-network nodes for mating connectors at their solved locations.

    Connectors that share a point become one node, ``{nodea+nodeb}``. A fasten
    record is not read here: only the world location of each connector is.
    """
    from harnice.lists.chosen_network import _coalesce_coincident_mate_nodes

    raw = []
    for device in discovered:
        if not device.get("has_body") or device.get("mates_error"):
            continue
        pose = placements.get(device["refdes"])
        if not pose:
            continue
        for mate in device.get("mates") or []:
            if not mate.get("id") or not mate.get("location"):
                continue
            rotation, origin = frame_of(pose, mate)
            alpha, beta, gamma = _euler_zyx_from_matrix(rotation)
            raw.append({
                "node_id": f"{device['refdes']}.{mate['id']}",
                "location": [round(float(origin[index]), 3) for index in range(3)],
                "alpha": round(float(alpha), 3),
                "beta": round(float(beta), 3),
                "gamma": round(float(gamma), 3),
                "mate": {"device": device["refdes"], "mate": mate["id"]},
            })

    def near(a, b):
        return all(abs(x - y) <= 0.001 for x, y in zip(a, b))

    return _coalesce_coincident_mate_nodes(raw, near)


def sync_mating_connector_nodes():
    """Write mating-connector nodes into the open system's available network.

    A system build calls this. Nodes placed by hand, and every segment, stay.
    """
    from harnice import fileio
    from harnice.lists.chosen_network import _is_mate_node

    path = system_available_network_path()
    discovered = discover()
    placements = locked_placements(
        discovered, load_assembly(fileio.path("physical assembly"))
    )
    generated = mating_connector_nodes(discovered, placements)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            network = json.load(handle)
        if not isinstance(network, dict):
            network = {}
    elif not generated:
        return
    else:
        network = {}
    kept = [
        node for node in (network.get("nodes") or [])
        if isinstance(node, dict) and not _is_mate_node(node)
    ]
    network["nodes"] = kept + generated
    network.setdefault("segments", [])
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(network, handle, indent=4)
        handle.write("\n")
    os.replace(temporary, path)


def _face_images(step_path):
    """Face names on a body whose linked image file is still present."""
    from harnice.utils import physical_body

    return [
        face for face in physical_body.FACE_NAMES
        if physical_body.face_image_path(step_path, face)
    ]


def _public(discovered, model, step_path, step_error=""):
    held = {}
    for mate in model["mates"]:
        held[mate["b"]["device"]] = {
            "device": mate["a"]["device"],
            "mate": mate["a"]["mate"],
            "flip": mate["flip"],
        }
    fixed = set(model.get("fixed") or [])
    library = _library_by_refdes()
    devices = []
    for device in discovered:
        part = library.get(device["refdes"]) or {}
        item = {
            "refdes": device["refdes"],
            "has_body": device["has_body"],
            "mates": device["mates"],
            "mates_error": device["mates_error"],
            "fixed": device["refdes"] in fixed,
            "mpn": part.get("mpn") or "",
            "lib_repo": part.get("lib_repo") or "",
            "lib_subpath": part.get("lib_subpath") or "",
            "rev": part.get("rev") or "",
            "images": _face_images(device["step_path"]) if device["has_body"] else [],
        }
        if device["has_body"] and device["refdes"] in model["placements"]:
            item["placement"] = model["placements"][device["refdes"]]
            item["held_by"] = held.get(device["refdes"])
        devices.append(item)
    return {
        "devices": devices,
        "mates": model["mates"],
        "assembly_exists": bool(step_path and os.path.isfile(step_path)),
        "step_error": step_error,
    }


def _write_step(step_path, discovered, placements):
    def write_assembly_step(path, discovered, placements, part_number=None):
        """Write one STEP file. Each device body is transformed into the system frame.

        Translations in ``placements`` are inches. The device STEP files are
        millimetres, so the translation is scaled. Returns the path, or None when
        there is no body to write.
        """
        from harnice.utils import step_utils

        try:
            from harnice import state

            fallback_part = state.partnumber("pn")
        except Exception:
            fallback_part = "assembly"

        bodies = []
        for device in discovered:
            if not device["has_body"]:
                continue
            shape = step_utils.read_step_shape(device["step_path"])
            if shape is None:
                failure = step_utils.ocp_import_error()
                if failure is not None:
                    raise ValueError(step_utils.ocp_unavailable_message(failure))
                raise ValueError(f"could not read {device['refdes']} body")
            pose = placements[device["refdes"]]
            shape = step_utils.transform_shape(
                shape,
                pose["x"] * INCH_TO_MM,
                pose["y"] * INCH_TO_MM,
                pose["z"] * INCH_TO_MM,
                pose["alpha"],
                pose["beta"],
                pose["gamma"],
            )
            bodies.append({"name": device["refdes"], "shape": shape})

        if not bodies:
            if path and os.path.isfile(path):
                os.remove(path)
            return None

        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temporary = path + ".tmp.step"
        try:
            step_utils.write_assembly_step(
                temporary,
                part_number or fallback_part,
                bodies,
                description="system physical assembly",
            )
            os.replace(temporary, path)
        except Exception:
            if os.path.isfile(temporary):
                os.remove(temporary)
            if os.path.isfile(path):
                os.remove(path)
            raise
        return path

    try:
        write_assembly_step(step_path, discovered, placements)
    except Exception as exc:
        if step_path and os.path.isfile(step_path):
            os.remove(step_path)
        return str(exc)
    return ""


def open_model():
    """Load the assembly, add every device that now has a body, and refresh the STEP file."""
    json_path, step_path = _assembly_paths()
    discovered = discover()
    saved = load_assembly(json_path)
    model, changed = reconcile(discovered, saved, strict_mates=False)
    has_body = any(device["has_body"] for device in discovered)
    assembly_exists = os.path.isfile(step_path)
    needs_step = has_body != assembly_exists
    step_error = ""
    if changed:
        save_assembly(model, json_path)
    if changed or needs_step:
        step_error = _write_step(step_path, discovered, model["placements"])
    return _public(discovered, model, step_path, step_error)


def save_model(data):
    """Store a console edit, solve fasten mates, and rewrite the assembly STEP."""
    json_path, step_path = _assembly_paths()
    discovered = discover()
    incoming = normalize_assembly(data)
    body_ids = [device["refdes"] for device in discovered if device["has_body"]]
    body_set = set(body_ids)
    unknown = [name for name in incoming["placements"] if name not in body_set]
    if unknown:
        raise ValueError("no body for " + ", ".join(unknown))
    model, _changed = reconcile(discovered, incoming, strict_mates=True)
    save_assembly(model, json_path)
    step_error = _write_step(step_path, discovered, model["placements"])
    return _public(discovered, model, step_path, step_error)


def context_markers(revision):
    """Face images and mate connectors of one system's physical model.

    ``revision`` is that system's revision folder. Placements are inches, with
    every fasten mate solved, so a mated device is shown on its connector
    rather than at a stale stored pose. Bounds are the body solid in the
    device frame, in inches, so a harness can draw the pictures and
    connectors on the source physical model context. A body that cannot be
    measured still contributes its connectors; ``bounds`` is then None.
    """

    def _body_bounds_inches(step_path):
        """Local axis-aligned bounds of one body, in inches, or None."""
        from harnice.utils import step_utils

        shape = step_utils.read_step_shape(step_path)
        if shape is None:
            return None
        try:
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib
        except ImportError:
            return None
        box = Bnd_Box()
        try:
            BRepBndLib.Add_s(shape, box)
        except Exception:
            return None
        if box.IsVoid():
            return None
        try:
            xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
        except Exception:
            return None
        scale = 1.0 / INCH_TO_MM
        return {
            "min": [xmin * scale, ymin * scale, zmin * scale],
            "max": [xmax * scale, ymax * scale, zmax * scale],
        }

    revision = os.path.abspath(revision)
    discovered = discover(os.path.join(revision, "instance_data", "device"))
    model = load_assembly(os.path.join(revision, "physical.json"))
    model = dict(model)
    model["placements"] = locked_placements(discovered, model)
    devices = []
    for device in discovered:
        if not device["has_body"]:
            continue
        refdes = device["refdes"]
        placement = model["placements"].get(refdes)
        if not placement:
            continue
        mates = []
        for mate in device.get("mates") or []:
            location = mate.get("location")
            if not isinstance(location, (list, tuple)) or len(location) != 3:
                continue
            mates.append({
                "id": mate["id"],
                "location": [float(item) for item in location],
                "alpha": float(mate.get("alpha") or 0),
                "beta": float(mate.get("beta") or 0),
                "gamma": float(mate.get("gamma") or 0),
            })
        devices.append({
            "refdes": refdes,
            "placement": placement,
            "images": _face_images(device["step_path"]),
            "bounds": _body_bounds_inches(device["step_path"]),
            "mates": mates,
        })
    return {"devices": devices}


def context_face_path(revision, refdes, face):
    """Absolute face image for one device in a system revision, or ''."""
    from harnice.utils import physical_body

    if face not in physical_body.FACE_NAMES or not _safe_refdes(refdes):
        return ""
    revision = os.path.abspath(revision)
    root = os.path.join(revision, "instance_data", "device")
    for device in discover(root):
        if device["refdes"] == refdes and device["has_body"]:
            return physical_body.face_image_path(device["step_path"], face) or ""
    return ""


def body_step(refdes):
    """Absolute ``body.step`` for one placed device, or None."""
    if not _safe_refdes(refdes):
        raise ValueError("invalid device")
    for device in discover():
        if device["refdes"] == refdes and device["has_body"]:
            return device["step_path"]
    return None
