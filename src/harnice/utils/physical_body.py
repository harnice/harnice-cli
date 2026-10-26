"""Device mate connectors, and the image links stored on a body STEP file.

The solid is ``fileio.path("body")`` (body.step), written by a macro through
``cad``. Mates stay in ``fileio.path("attributes")`` (attributes.json), under
``mate_connectors``: location [x, y, z] inches, ZYX Euler degrees
(R = Rx(alpha) · Ry(beta) · Rz(gamma)), and ``source`` ``build`` or ``gui``.
A build mate is placed again on the next build. A gui mate keeps its pose.
Other attributes in that file are kept.
"""

import json
import os

from harnice import fileio
from harnice.lists import signals_list

FACE_NAMES = ("front", "back", "left", "right", "top", "bottom")

# A vertex this close to a bounding-box face, in inches, lies on that face.
_FACE_PLANE_EPS_IN = 0.01
# Thinner than this, and not filling the box, is an ear or a point contact.
_FACE_SLIVER_IN = 0.125

# axis, True when the face is the maximum on that axis, outward normal, up
_FACE_SPEC = {
    "front": (1, False, (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "back": (1, True, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "left": (0, False, (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "right": (0, True, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "bottom": (2, False, (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "top": (2, True, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
}


def face_frame(bounds, points, face):
    """Rectangle a face picture covers, in inches.

    ``bounds`` is ``(xmin, ymin, zmin, xmax, ymax, zmax)``. ``points`` are
    vertices of the solid in that same frame. The picture sits on the solid
    at that side of the box. A rack chassis is 19 inches across the ears and
    17 inches across the rear panel, so the back picture is 17 inches wide.
    A face that is only a sliver, or that has no vertices, keeps the full
    side of the box. Returns None for an unknown face.
    """
    spec = _FACE_SPEC.get(face)
    if spec is None:
        return None
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 6:
        raise ValueError("bounds must be xmin, ymin, zmin, xmax, ymax, zmax")
    axis, at_max, normal, up = spec
    box = tuple(float(value) for value in bounds)
    at = box[axis + 3] if at_max else box[axis]
    free = [index for index in range(3) if index != axis]
    samples = []
    for point in points or ():
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            continue
        try:
            samples.append(tuple(float(value) for value in point))
        except (TypeError, ValueError):
            continue
    if samples:
        at = max(point[axis] for point in samples) if at_max else min(point[axis] for point in samples)
    center = [0.0, 0.0, 0.0]
    center[axis] = at
    spans = []
    for index in free:
        start = box[index]
        end = box[index + 3]
        center[index] = (start + end) / 2.0
        spans.append(max(end - start, 1e-9))
    fitted = _panel_on_plane(box, samples, axis, at, free)
    if fitted is not None:
        for index, value in zip(free, fitted["center"]):
            center[index] = value
        spans = fitted["spans"]
    return {
        "pos": center,
        "normal": [normal[0], normal[1], normal[2]],
        "up": [up[0], up[1], up[2]],
        "w": spans[0],
        "h": spans[1],
    }


def _panel_on_plane(box, points, axis, at, free):
    """In-plane center and spans of vertices on one face, or None.

    None keeps the bounding-box face. A panel is used when each in-plane
    span is a real edge, or already fills the box on that axis. The outer
    face of a rack ear is thinner than ``_FACE_SLIVER_IN`` and does not fill
    the depth, so that side stays the bounding box.
    """
    if len(points) < 2:
        return None
    mins = [float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf")]
    found = False
    for point in points:
        if abs(point[axis] - at) > _FACE_PLANE_EPS_IN:
            continue
        found = True
        for index, axis_index in enumerate(free):
            value = point[axis_index]
            if value < mins[index]:
                mins[index] = value
            if value > maxs[index]:
                maxs[index] = value
    if not found:
        return None
    spans = []
    center = []
    for index, axis_index in enumerate(free):
        span = maxs[index] - mins[index]
        box_span = box[axis_index + 3] - box[axis_index]
        fills = span >= box_span - _FACE_PLANE_EPS_IN
        if span < _FACE_SLIVER_IN and not fills:
            return None
        spans.append(max(span, 1e-9))
        center.append((mins[index] + maxs[index]) / 2.0)
    return {"spans": spans, "center": center}


def empty_body():
    """Mates file used until the page saves one. The solid comes from the body file."""
    return {"mate_connectors": []}


def normalize_body(data):
    """Return a canonical body dict, or raise ValueError."""

    def number(label, value):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{label} must be a number")
        try:
            got = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number") from exc
        if got != got or got == float("inf") or got == float("-inf"):
            raise ValueError(f"{label} must be a finite number")
        return got

    def mate_source(mate_id, raw):
        if raw in (None, ""):
            if len(mate_id) > 1 and mate_id[0] == "U" and mate_id[1:].isdigit():
                return "build"
            return "gui"
        if raw not in ("build", "gui"):
            raise ValueError("mate source must be build or gui")
        return raw

    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")

    raw_mates = data.get("mate_connectors")
    if raw_mates is None:
        raw_mates = []
    if not isinstance(raw_mates, list):
        raise ValueError("mate_connectors must be a list")
    mates = []
    seen = set()
    for mate in raw_mates:
        if not isinstance(mate, dict):
            raise ValueError("each mate connector must be an object")
        mate_id = (mate.get("id") or "").strip()
        if not mate_id:
            raise ValueError("a mate connector needs an id")
        if mate_id in seen:
            raise ValueError(f"duplicate mate connector id: {mate_id}")
        seen.add(mate_id)
        location = mate.get("location")
        if not isinstance(location, (list, tuple)) or len(location) != 3:
            raise ValueError("mate location must be [x, y, z]")
        mates.append({
            "id": mate_id,
            "location": [number("location", item) for item in location],
            "alpha": number("alpha", 0 if mate.get("alpha") in (None, "") else mate.get("alpha")),
            "beta": number("beta", 0 if mate.get("beta") in (None, "") else mate.get("beta")),
            "gamma": number("gamma", 0 if mate.get("gamma") in (None, "") else mate.get("gamma")),
            "source": mate_source(mate_id, mate.get("source")),
        })

    return {"mate_connectors": mates}


def load_body(path=None):
    """Read mate_connectors from attributes.json. None when that key is absent."""
    path = path or fileio.path("attributes")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"attributes.json could not be read: {exc}") from exc
    if not isinstance(data, dict) or "mate_connectors" not in data:
        return None
    return normalize_body(data)


def save_mates(mates, path=None):
    """Store mate connectors on attributes.json. Other keys in the file stay."""
    path = path or fileio.path("attributes")
    body = normalize_body({"mate_connectors": mates})
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"attributes.json could not be read: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("attributes.json must be a JSON object")
    data["mate_connectors"] = body["mate_connectors"]
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)
        handle.write("\n")
    os.replace(temporary, path)


def require_saved_mates():
    """Fail the build when saved mates are missing a signals-list connector.

    A device whose attributes have no mate_connectors still builds. Once that
    key is present, every distinct connector_id needs a mate with that same id.
    """
    body = load_body()
    if body is None:
        return
    have = {mate["id"] for mate in body["mate_connectors"]}
    missing = []
    for connector_id in signals_list.unique_connector_ids():
        if connector_id not in have:
            missing.append(connector_id)
    if not missing:
        return
    joined = ", ".join(missing)
    pronoun = "it" if len(missing) == 1 else "them"
    raise ValueError(
        "Physical model is missing a mate connector for signals-list "
        f"connector(s): {joined}. Open the physical model page and place {pronoun}."
    )


_LINK = "harnice-body-image "


def read_image_records(path):
    """Surface uuid to ``{"path", "orientation"}`` stored in a body STEP file.

    ``path`` is as written. ``orientation`` is degrees, or 0 when the comment
    has no angle.
    """
    records = {}
    if not path or not os.path.isfile(path):
        return records
    with open(path, "r", encoding="latin-1") as handle:
        for line in handle:
            stripped = line.strip()
            prefix = "/* " + _LINK
            if not stripped.startswith(prefix) or not stripped.endswith("*/"):
                continue
            body = stripped[len(prefix):-2].strip()
            face, _, rest = body.partition(" ")
            if not face or not rest:
                continue
            image_path, sep, orient = rest.rpartition(" ")
            angle = 0.0
            if not sep:
                image_path = rest
            else:
                try:
                    angle = float(orient)
                except ValueError:
                    image_path = rest
                    angle = 0.0
            if image_path:
                records[face] = {"path": image_path, "orientation": angle}
    return records


def read_image_links(path):
    """Surface uuid to image path stored in a body STEP file. Paths are as written."""
    return {face: record["path"] for face, record in read_image_records(path).items()}


def resolve_image_link(rel):
    """Absolute path for a link stored in the body file."""
    if os.path.isabs(rel):
        return rel
    return os.path.normpath(os.path.join(fileio.rev_directory(), rel))


def face_image_path(step_path, face):
    """Absolute image for one face of a body STEP file, or '' when it is missing.

    A relative link is resolved beside that STEP file, then inside ``lib/<rev>``
    when the body was copied into a system instance and the picture stayed with
    the library snapshot.
    """
    rel = read_image_links(step_path).get(face)
    if not rel:
        return ""
    if os.path.isabs(rel):
        return rel if os.path.isfile(rel) else ""
    rel = rel.replace("/", os.sep)
    step_dir = os.path.dirname(os.path.abspath(step_path))
    roots = [step_dir]
    lib = os.path.join(step_dir, "lib")
    if os.path.isdir(lib):
        for name in sorted(os.listdir(lib)):
            candidate = os.path.join(lib, name)
            if os.path.isdir(candidate):
                roots.append(candidate)
    for root in roots:
        path = os.path.normpath(os.path.join(root, rel))
        try:
            if os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) != os.path.realpath(root):
                continue
        except ValueError:
            continue
        if os.path.isfile(path):
            return path
    return ""


def _store_image_links(path, links):
    """Rewrite only the image comments in an existing STEP file."""
    with open(path, "r", encoding="latin-1") as handle:
        lines = handle.read().splitlines(keepends=True)
    kept = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("/* " + _LINK) and stripped.endswith("*/"):
            continue
        kept.append(line)
    block = "".join(
        f"/* {_LINK}{name} {links[name]} */\n"
        for name in sorted(links)
    )
    joined = "".join(kept)
    marker = "END-ISO-10303-21;"
    idx = joined.rfind(marker)
    if idx == -1:
        if joined and not joined.endswith("\n"):
            joined += "\n"
        joined += block
    else:
        joined = joined[:idx] + block + joined[idx:]
    with open(path, "w", encoding="latin-1", newline="") as handle:
        handle.write(joined)


def set_image_link(path, face, image_path):
    """Point one face in an existing body STEP file at an image."""
    def relative_link(image):
        absolute = os.path.realpath(image)
        rev = os.path.realpath(fileio.rev_directory())
        try:
            inside = os.path.commonpath([absolute, rev]) == rev
        except ValueError:
            inside = False
        if inside:
            return os.path.relpath(absolute, rev).replace(os.sep, "/")
        return absolute.replace(os.sep, "/")

    if face not in FACE_NAMES:
        raise ValueError("face must be one of front, back, left, right, top, bottom")
    if not isinstance(image_path, str) or not image_path.strip():
        raise ValueError(f"image path for {face} must be a path")
    if "*/" in image_path or "\n" in image_path:
        raise ValueError(f"image path for {face} cannot be stored in a STEP file")
    image_path = image_path.strip()
    if not os.path.isfile(image_path):
        raise ValueError(f"image for {face} was not found: {image_path}")
    links = read_image_links(path)
    links[face] = relative_link(image_path)
    _store_image_links(path, links)
    return links


def clear_image_link(path, face):
    """Remove one face link from a body STEP file."""
    links = read_image_links(path)
    links.pop(face, None)
    _store_image_links(path, links)
    return links
