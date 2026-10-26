"""A small CAD model for a device body.

Distances are inches. ``new`` starts a model. ``sketch``, ``extrude``,
``attach_png``, and ``mate`` change that model. ``save_step`` writes the
solid. ``save_mates`` writes the mate connectors. ``import_step`` only copies
a file; it does not build a model, and images are not attached to an imported
file.

``save_step`` writes the STEP file in millimetres, which is what the viewer
reads. The model itself stays in inches. ``extrude`` returns a ``Body``.
``boolean_subtract`` cuts tool bodies out of target bodies.
"""

import os


class Model:
    def __init__(self):
        self.planes = {}
        self.surfaces = {}
        self.solids = []
        self.mates = []


class Body:
    """One solid on a model. Triangles are outward-wound, in inches."""

    def __init__(self, model, triangles):
        self.model = model
        self.triangles = triangles


def new():
    """A model with three datum planes through the origin.

    Each plane is its normal. Sketch coordinates are inches along u and v,
    with u × v equal to that normal:

    - ``top`` ``[1, 0, 0]``, u ``[0, 1, 0]``, v ``[0, 0, 1]``
    - ``front`` ``[0, 1, 0]``, u ``[0, 0, 1]``, v ``[1, 0, 0]``
    - ``right`` ``[0, 0, 1]``, u ``[1, 0, 0]``, v ``[0, 1, 0]``
    """
    model = Model()
    model.planes["top"] = [1.0, 0.0, 0.0]
    model.planes["front"] = [0.0, 1.0, 0.0]
    model.planes["right"] = [0.0, 0.0, 1.0]
    return model


def sketch(model, uuid, plane, vertices, edges):
    """Add a surface. ``vertices`` maps a name to ``(u, v)`` inches on ``plane``.

    ``edges`` is a closed loop of ``(start, end)`` vertex names. The new
    surface's id is ``uuid``, which is what ``extrude`` and ``attach_png`` use.
    """
    if not isinstance(uuid, str) or not uuid.strip():
        raise ValueError("surface uuid must be a name")
    uuid = uuid.strip()
    if " " in uuid or "\n" in uuid or "*/" in uuid:
        raise ValueError("surface uuid cannot be stored in a STEP file")
    if uuid in model.surfaces:
        raise ValueError(f"surface {uuid} already exists")
    if plane not in model.planes:
        names = ", ".join(model.planes)
        raise ValueError(f"plane must be one of {names}")
    if not isinstance(vertices, dict) or len(vertices) < 3:
        raise ValueError("sketch needs at least 3 vertices")
    if not isinstance(edges, (list, tuple)) or not edges:
        raise ValueError("sketch needs a closed boundary")

    points = {}
    for name, pair in vertices.items():
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise ValueError("vertex names must be strings")
        if " " in name or "\n" in name or "*/" in name:
            raise ValueError("vertex names cannot be stored in a STEP file")
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"vertex {name} must be a (u, v) pair")
        try:
            u = float(pair[0])
            v = float(pair[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"vertex {name} must be a (u, v) pair") from exc
        if u != u or v != v or abs(u) == float("inf") or abs(v) == float("inf"):
            raise ValueError(f"vertex {name} must be a finite (u, v) pair")
        points[name] = (u, v)

    parsed = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a pair of vertex names")
        start, end = edge
        if start not in points or end not in points:
            raise ValueError("an edge names a vertex the sketch does not have")
        parsed.append((start, end))

    ordered = [parsed.pop(0)]
    while parsed:
        tail = ordered[-1][1]
        found = None
        for index, (start, _end) in enumerate(parsed):
            if start == tail:
                found = index
                break
        if found is None:
            raise ValueError("sketch edges must form one closed loop")
        ordered.append(parsed.pop(found))
    if ordered[-1][1] != ordered[0][0]:
        raise ValueError("sketch edges must form one closed loop")
    if {start for start, _end in ordered} != set(points):
        raise ValueError("every vertex must be on the closed boundary")

    model.surfaces[uuid] = {
        "plane": plane,
        "vertices": points,
        "edges": ordered,
        "png": None,
        "orientation": None,
    }


def extrude(model, uuid, distance):
    """Make a solid from a sketched surface, along that plane's normal.

    ``distance`` is inches and must be greater than zero. The sketch surface
    stays. The face at the far end is ``"{uuid}-end"``. Each side is
    ``"{uuid}-{start}-{end}"`` for an edge of the sketch.
    """
    if uuid not in model.surfaces:
        raise ValueError(f"no surface {uuid}")
    surface = model.surfaces[uuid]
    if "edges" not in surface:
        raise ValueError(f"surface {uuid} is not a sketch")
    if isinstance(distance, bool) or not isinstance(distance, (int, float)):
        raise ValueError("extrude distance must be a number")
    length = float(distance)
    if not 0 < length < float("inf"):
        raise ValueError("extrude distance must be greater than zero")
    end_id = uuid + "-end"
    if end_id in model.surfaces:
        raise ValueError(f"surface {end_id} already exists")
    for start, end in surface["edges"]:
        side_id = uuid + "-" + start + "-" + end
        if side_id in model.surfaces:
            raise ValueError(f"surface {side_id} already exists")

    def add(a, b):
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    axes = {
        "top": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        "front": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
        "right": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    }
    u_axis, v_axis = axes[surface["plane"]]
    ux, uy, uz = u_axis
    vx, vy, vz = v_axis
    nx, ny, nz = model.planes[surface["plane"]]
    loop = []
    for start, _end in surface["edges"]:
        u, v = surface["vertices"][start]
        if loop and abs(u - loop[-1][0]) < 1e-9 and abs(v - loop[-1][1]) < 1e-9:
            continue
        loop.append((u, v))
    if (
        len(loop) >= 2
        and abs(loop[0][0] - loop[-1][0]) < 1e-9
        and abs(loop[0][1] - loop[-1][1]) < 1e-9
    ):
        loop.pop()
    if len(loop) < 3:
        raise ValueError("sketch boundary needs at least 3 points")

    area = 0.0
    for index, (u, v) in enumerate(loop):
        u2, v2 = loop[(index + 1) % len(loop)]
        area += u * v2 - u2 * v
    if abs(area) < 1e-12:
        raise ValueError("sketch boundary has no area")
    if area < 0:
        loop.reverse()

    def place(u, v, scale):
        return (
            u * ux + v * vx + nx * scale,
            u * uy + v * vy + ny * scale,
            u * uz + v * vz + nz * scale,
        )

    bottom = [place(u, v, 0.0) for u, v in loop]
    top = [place(u, v, length) for u, v in loop]
    count = len(loop)
    center = (
        sum(point[0] for point in bottom) / count + nx * length / 2,
        sum(point[1] for point in bottom) / count + ny * length / 2,
        sum(point[2] for point in bottom) / count + nz * length / 2,
    )

    poly = list(loop)

    def turn(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def contains(point, a, b, c):
        first = turn(a, b, point)
        second = turn(b, c, point)
        third = turn(c, a, point)
        has_neg = first < -1e-9 or second < -1e-9 or third < -1e-9
        has_pos = first > 1e-9 or second > 1e-9 or third > 1e-9
        return not (has_neg and has_pos)

    caps = []
    guard = 0
    while len(poly) > 3 and guard < 1000:
        guard += 1
        size = len(poly)
        clipped = False
        for index in range(size):
            prev = poly[(index - 1) % size]
            cur = poly[index]
            nxt = poly[(index + 1) % size]
            if turn(prev, cur, nxt) <= 1e-9:
                continue
            blocked = False
            for other in range(size):
                if other in ((index - 1) % size, index, (index + 1) % size):
                    continue
                if contains(poly[other], prev, cur, nxt):
                    blocked = True
                    break
            if blocked:
                continue
            caps.append((prev, cur, nxt))
            del poly[index]
            clipped = True
            break
        if not clipped:
            raise ValueError("could not triangulate the sketch")
    caps.append((poly[0], poly[1], poly[2]))

    at = {}
    for index, pair in enumerate(loop):
        at[pair] = index

    triangles = []
    for index in range(count):
        nxt = (index + 1) % count
        a = bottom[index]
        b = bottom[nxt]
        c = top[nxt]
        d = top[index]
        outward = cross(sub(b, a), sub(c, a))
        mid = (
            (a[0] + b[0] + c[0] + d[0]) / 4,
            (a[1] + b[1] + c[1] + d[1]) / 4,
            (a[2] + b[2] + c[2] + d[2]) / 4,
        )
        if dot(outward, sub(mid, center)) >= 0:
            triangles.append((a, b, c))
            triangles.append((a, c, d))
        else:
            triangles.append((a, c, b))
            triangles.append((a, d, c))
    for a, b, c in caps:
        i = at[a]
        j = at[b]
        k = at[c]
        triangles.append((top[i], top[j], top[k]))
        triangles.append((bottom[i], bottom[k], bottom[j]))

    model.solids.append(triangles)
    model.surfaces[end_id] = {
        "plane": surface["plane"],
        "png": None,
        "orientation": None,
    }
    for start, end in surface["edges"]:
        model.surfaces[uuid + "-" + start + "-" + end] = {
            "plane": None,
            "png": None,
            "orientation": None,
        }
    return Body(model, triangles)


def boolean_subtract(tools, targets):
    """Cut ``tools`` out of ``targets``. Each argument is a ``Body`` or a list of them.

    Targets are updated in place. Tools are removed from the model they were
    extruded onto. Both bodies have to be rectangular prisms.
    """
    def as_bodies(value, label):
        if isinstance(value, Body):
            return [value]
        if isinstance(value, (list, tuple)) and value and all(isinstance(item, Body) for item in value):
            return list(value)
        raise ValueError(f"{label} must be a body")

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def box_of(triangles):
        xs, ys, zs = [], [], []
        for tri in triangles:
            for point in tri:
                xs.append(point[0])
                ys.append(point[1])
                zs.append(point[2])
        if not xs:
            raise ValueError("a body has no triangles")
        box = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
        for tri in triangles:
            for point in tri:
                for axis in range(3):
                    if abs(point[axis] - box[axis]) > 1e-6 and abs(point[axis] - box[axis + 3]) > 1e-6:
                        raise ValueError("boolean_subtract only supports rectangular prisms")
        return box

    def add_quad(out, corners, outward):
        a, b, c, d = corners
        normal = cross(sub(b, a), sub(d, a))
        if dot(normal, outward) < 0:
            b, d = d, b
        out.append((a, b, c))
        out.append((a, c, d))

    def emit_rect(out, axis, plane, sign, u0, u1, v0, v1):
        if u1 - u0 < 1e-9 or v1 - v0 < 1e-9:
            return
        free = [0, 1, 2]
        free.remove(axis)
        ua, va = free

        def point(u, v):
            got = [0.0, 0.0, 0.0]
            got[axis] = plane
            got[ua] = u
            got[va] = v
            return tuple(got)

        outward = [0.0, 0.0, 0.0]
        outward[axis] = sign
        add_quad(out, (point(u0, v0), point(u1, v0), point(u1, v1), point(u0, v1)), tuple(outward))

    def emit_face(out, axis, plane, sign, bounds, hole):
        u0, u1, v0, v1 = bounds
        if hole is None:
            emit_rect(out, axis, plane, sign, u0, u1, v0, v1)
            return
        hu0, hu1, hv0, hv1 = hole
        hu0 = max(hu0, u0)
        hu1 = min(hu1, u1)
        hv0 = max(hv0, v0)
        hv1 = min(hv1, v1)
        if hu1 - hu0 < 1e-9 or hv1 - hv0 < 1e-9:
            emit_rect(out, axis, plane, sign, u0, u1, v0, v1)
            return
        emit_rect(out, axis, plane, sign, u0, u1, v0, hv0)
        emit_rect(out, axis, plane, sign, u0, u1, hv1, v1)
        emit_rect(out, axis, plane, sign, u0, hu0, hv0, hv1)
        emit_rect(out, axis, plane, sign, hu1, u1, hv0, hv1)

    def overlap(a0, a1, b0, b1):
        lo = max(a0, b0)
        hi = min(a1, b1)
        if hi - lo < 1e-9:
            return None
        return (lo, hi)

    def difference(target_triangles, tool_triangles):
        target = box_of(target_triangles)
        tool = box_of(tool_triangles)
        spans = []
        for axis in range(3):
            span = overlap(target[axis], target[axis + 3], tool[axis], tool[axis + 3])
            if span is None:
                return list(target_triangles)
            spans.append(span)
        cut = tuple(spans[axis][0] for axis in range(3)) + tuple(spans[axis][1] for axis in range(3))
        out = []
        for axis in range(3):
            free = [item for item in range(3) if item != axis]
            face = (target[free[0]], target[free[0] + 3], target[free[1]], target[free[1] + 3])
            hole = (cut[free[0]], cut[free[0] + 3], cut[free[1]], cut[free[1] + 3])
            if abs(cut[axis] - target[axis]) < 1e-8:
                emit_face(out, axis, target[axis], -1, face, hole)
            else:
                emit_face(out, axis, target[axis], -1, face, None)
            if abs(cut[axis + 3] - target[axis + 3]) < 1e-8:
                emit_face(out, axis, target[axis + 3], 1, face, hole)
            else:
                emit_face(out, axis, target[axis + 3], 1, face, None)
            if target[axis] + 1e-8 < cut[axis] < target[axis + 3] - 1e-8:
                wall = (cut[free[0]], cut[free[0] + 3], cut[free[1]], cut[free[1] + 3])
                emit_face(out, axis, cut[axis], 1, wall, None)
            if target[axis] + 1e-8 < cut[axis + 3] < target[axis + 3] - 1e-8:
                wall = (cut[free[0]], cut[free[0] + 3], cut[free[1]], cut[free[1] + 3])
                emit_face(out, axis, cut[axis + 3], -1, wall, None)
        if not out:
            raise ValueError("subtraction removed the whole target")
        return out

    tool_bodies = as_bodies(tools, "tools")
    target_bodies = as_bodies(targets, "targets")
    for tool in tool_bodies:
        for target in target_bodies:
            if tool is target:
                raise ValueError("a body cannot be both a tool and a target")
    for target in target_bodies:
        current = target.triangles
        for tool in tool_bodies:
            current = difference(current, tool.triangles)
        target.triangles[:] = current
    seen = []
    for tool in tool_bodies:
        if tool.triangles in seen:
            continue
        seen.append(tool.triangles)
        if tool.triangles in tool.model.solids:
            tool.model.solids.remove(tool.triangles)
    return targets


def attach_png(model, uuid, filepath, orientation):
    """Store an image path and an orientation, in degrees, on a surface."""
    if uuid not in model.surfaces:
        raise ValueError(f"no surface {uuid}")
    if not isinstance(filepath, str) or not filepath.strip():
        raise ValueError("filepath must be a path")
    if "\n" in filepath or "*/" in filepath or " " in filepath:
        raise ValueError("image path cannot be stored in a STEP file")
    filepath = filepath.strip()
    if not os.path.isfile(filepath):
        raise ValueError(f"image was not found: {filepath}")
    if isinstance(orientation, bool) or not isinstance(orientation, (int, float)):
        raise ValueError("orientation must be a number of degrees")
    angle = float(orientation)
    if angle != angle or abs(angle) == float("inf"):
        raise ValueError("orientation must be a number of degrees")
    model.surfaces[uuid]["png"] = filepath
    model.surfaces[uuid]["orientation"] = angle


def save_step(model, path):
    """Write the solids to ``path``. Image links are comments in that file."""
    if not model.solids:
        raise ValueError("no body to save")

    def relative(image_path):
        from harnice import fileio

        absolute = os.path.realpath(image_path)
        rev = os.path.realpath(fileio.rev_directory())
        try:
            inside = os.path.commonpath([absolute, rev]) == rev
        except ValueError:
            inside = False
        if inside:
            return os.path.relpath(absolute, rev).replace(os.sep, "/")
        return absolute.replace(os.sep, "/")

    triangles = []
    for solid in model.solids:
        for tri in solid:
            triangles.append(tuple(
                (point[0] * 25.4, point[1] * 25.4, point[2] * 25.4)
                for point in tri
            ))
    from harnice import state
    from harnice.utils import step_utils

    try:
        name = state.partnumber("pn")
    except Exception:
        name = "body"
    step_utils.write_step_file(path, name, triangles, description="device body")

    comments = []
    for surface_id in sorted(model.surfaces):
        surface = model.surfaces[surface_id]
        if not surface["png"]:
            continue
        angle = surface["orientation"]
        shown = str(int(angle)) if angle == int(angle) else str(angle)
        link = relative(surface["png"])
        comments.append(f"/* harnice-body-image {surface_id} {link} {shown} */\n")
    if not comments:
        return
    with open(path, "r", encoding="latin-1") as handle:
        text = handle.read()
    block = "".join(comments)
    marker = "END-ISO-10303-21;"
    idx = text.rfind(marker)
    if idx == -1:
        if text and not text.endswith("\n"):
            text += "\n"
        text += block
    else:
        text = text[:idx] + block + text[idx:]
    with open(path, "w", encoding="latin-1", newline="") as handle:
        handle.write(text)


def mate(model, uuid, location, alpha=0, beta=0, gamma=0, source="build"):
    """Add a mate connector. ``location`` is ``[x, y, z]`` inches. Angles are degrees.

    ``source`` is ``build`` or ``gui``. A later build rewrites ``build`` mates
    and keeps the saved pose of ``gui`` mates.
    """
    def number(label, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} must be a number")
        got = float(value)
        if got != got or abs(got) == float("inf"):
            raise ValueError(f"{label} must be a finite number")
        return got

    if not isinstance(uuid, str) or not uuid.strip():
        raise ValueError("mate connector needs an id")
    uuid = uuid.strip()
    for item in model.mates:
        if item["id"] == uuid:
            raise ValueError(f"mate connector {uuid} already exists")
    if source not in ("build", "gui"):
        raise ValueError("mate source must be build or gui")
    if not isinstance(location, (list, tuple)) or len(location) != 3:
        raise ValueError("mate location must be [x, y, z]")
    model.mates.append({
        "id": uuid,
        "location": [number("location", item) for item in location],
        "alpha": number("alpha", alpha),
        "beta": number("beta", beta),
        "gamma": number("gamma", gamma),
        "source": source,
    })


def keep_gui_mates(model, saved):
    """Copy gui mates onto the model. A gui mate replaces a build mate with the same id.

    Saved build mates are left out. This run's build mates stay, and a build
    mate this run did not create is dropped.
    """
    for item in saved:
        if item.get("source") != "gui":
            continue
        name = item["id"]
        model.mates = [mate for mate in model.mates if mate["id"] != name]
        mate(
            model,
            name,
            item["location"],
            item.get("alpha", 0),
            item.get("beta", 0),
            item.get("gamma", 0),
            "gui",
        )


def save_mates(model, path):
    """Write this model's mate connectors into attributes.json."""
    if not model.mates:
        raise ValueError("no mate connectors to save")
    from harnice.utils import physical_body

    physical_body.save_mates(model.mates, path)


def import_step(source, destination):
    """Copy a STEP file. The copy is not a model, and images are not attached."""
    import shutil

    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a path")
    if not isinstance(destination, str) or not destination.strip():
        raise ValueError("destination must be a path")
    source = source.strip()
    destination = destination.strip()
    if not os.path.isfile(source):
        raise ValueError(f"STEP file was not found: {source}")
    folder = os.path.dirname(destination)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if os.path.realpath(source) != os.path.realpath(destination):
        shutil.copyfile(source, destination)
