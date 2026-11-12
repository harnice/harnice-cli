"""Orthographic line drawing of a system physical assembly.

OpenCascade hidden-line removal projects each device body to its visible
edges and silhouettes. Each face turned toward the camera gets its photo,
and each device gets its name at the body center. A face with no photo is
filled white. A photo is drawn when any part of its face can be seen, and
rays cast through each face decide which photo is on top where they
overlap: the body a ray lands on is the one painted there. A name sits on
its own photo and under any closer body. A photo is stretched onto the rectangle of
its face. A rectangular body uses that
side of its bounding box. A face that is not a rectangle, such as a rack
chassis back, uses the rectangle of the solid on that side: the 17 inch
panel between the ears. The PDF export embeds those links; this module
leaves them as paths.

``orientation`` is a face name or a viewport rotation. ``(0, 0, 0)`` is the
front view: look along +Y, +X to the right, +Z up. A dict or a 3-number
sequence is ``alpha``, ``beta``, ``gamma`` in degrees,
``R = Rx(α) · Ry(β) · Rz(γ)`` applied to that front camera. Named views
look straight at that face of the bounding box, with the picture upright
the way the viewer shows it.
"""

import bisect
import heapq
import math
import os

from harnice.utils.bundle_network_utils import _rotate3, _zyx_rotation_matrix

PX_PER_INCH = 96.0
PX_PER_MM = PX_PER_INCH / 25.4
_FACE_NAMES = ("front", "back", "left", "right", "top", "bottom")

# (view direction into the scene, screen right, screen up)
_NAMED_VIEWS = {
    "front": ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "back": ((0.0, -1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "bottom": ((0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
}

# Faces closer than this are treated as flush. The smaller face is eased
# toward the camera so a rack rail does not draw through the gear in front of it.
_FLUSH_MM = 0.05
_FLUSH_STEP_MM = 0.05

# Face photos are sampled on a _SAMPLES x _SAMPLES grid of rays. A sample with
# a solid more than _HIDDEN_MM in front of it is hidden.
_SAMPLES = 10
_HIDDEN_MM = 0.5


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


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


def _bounds_mm(shape):
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return None
    return box.Get()


def _require_opencascade():
    from harnice.utils import step_utils

    failure = step_utils.ocp_import_error()
    if failure is not None:
        raise ValueError(step_utils.ocp_unavailable_message(failure))


def view_basis(orientation):
    """Return ``(view_direction, screen_right, screen_up)`` unit vectors.

    ``view_direction`` points from the camera into the scene.
    """

    def _unit(vector):
        length = math.sqrt(_dot(vector, vector))
        if length < 1e-12:
            raise ValueError("orientation produced a zero axis")
        return (vector[0] / length, vector[1] / length, vector[2] / length)

    if orientation is None or orientation == "":
        orientation = "front"
    if isinstance(orientation, str):
        key = orientation.strip().lower()
        if key not in _NAMED_VIEWS:
            names = ", ".join(_FACE_NAMES)
            raise ValueError(
                f"orientation must be {names}, or alpha, beta, gamma"
            )
        view, right, up = _NAMED_VIEWS[key]
        return view, right, up
    if isinstance(orientation, dict):
        angles = (
            orientation.get("alpha", 0),
            orientation.get("beta", 0),
            orientation.get("gamma", 0),
        )
    elif isinstance(orientation, (list, tuple)) and len(orientation) == 3:
        angles = tuple(orientation)
    else:
        raise ValueError(
            "orientation must be a face name or alpha, beta, gamma"
        )
    alpha, beta, gamma = (_number("orientation", item) for item in angles)
    rotation = _zyx_rotation_matrix(alpha, beta, gamma)
    right = _unit(_rotate3(rotation, (1.0, 0.0, 0.0)))
    view = _unit(_rotate3(rotation, (0.0, 1.0, 0.0)))
    up = _unit(_rotate3(rotation, (0.0, 0.0, 1.0)))
    return view, right, up


def _face_corners(bounds, face, angle, points=None):
    """Local millimetre corners of one face, picture upright.

    ``points`` are vertices in the same millimetre frame as ``bounds``. With
    none, the rectangle is that side of the bounding box. With vertices, it
    shrinks to the panel that lies on that side.
    """

    def _cross(a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def _rotate_about(vector, axis, degrees):
        theta = math.radians(degrees)
        cosine, sine = math.cos(theta), math.sin(theta)
        crossed = _cross(axis, vector)
        along = _dot(axis, vector)
        return tuple(
            vector[i] * cosine + crossed[i] * sine + axis[i] * along * (1.0 - cosine)
            for i in range(3)
        )

    from harnice.utils import physical_body

    scale = 1.0 / 25.4
    frame = physical_body.face_frame(
        tuple(value * scale for value in bounds),
        [
            (point[0] * scale, point[1] * scale, point[2] * scale)
            for point in (points or ())
        ],
        face,
    )
    if frame is None:
        return None
    center = tuple(value * 25.4 for value in frame["pos"])
    normal = tuple(frame["normal"])
    up = tuple(frame["up"])
    width = frame["w"] * 25.4
    height = frame["h"] * 25.4
    x_axis = _cross(up, normal)
    y_axis = _cross(normal, x_axis)
    if angle:
        x_axis = _rotate_about(x_axis, normal, angle)
        y_axis = _rotate_about(y_axis, normal, angle)

    def at(su, sv):
        return tuple(
            center[i] + su * (width / 2.0) * x_axis[i] + sv * (height / 2.0) * y_axis[i]
            for i in range(3)
        )

    return {
        "normal": normal,
        "width": width,
        "height": height,
        "tl": at(-1.0, 1.0),
        "tr": at(1.0, 1.0),
        "bl": at(-1.0, -1.0),
    }


def render_svg(artifact_id, devices, scale=1, orientation="front", lineweight=1):
    """SVG text for devices that are already posed in the system frame.

    Each device is ``{"refdes", "shape", "photos"}``. ``shape`` is an
    OpenCascade solid in millimetres. Each photo is ``href``, ``normal``,
    ``tl``, ``tr``, ``bl``, and ``width`` / ``height`` in millimetres.
    """

    def _xml_text(value):
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _xml_attr(value):
        return _xml_text(value).replace('"', "&quot;")

    def _num(value):
        text = f"{float(value):.4f}".rstrip("0").rstrip(".")
        if text in ("", "-0", "-"):
            return "0"
        return text

    def _compound(shapes):
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound

        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for shape in shapes:
            builder.Add(compound, shape)
        return compound

    def _project(point, right, up):
        return (
            _dot(point, right) * PX_PER_MM,
            -_dot(point, up) * PX_PER_MM,
        )

    def _unify(shape):
        """Merge coplanar faces so a triangle mesh does not draw its diagonals."""
        try:
            from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
        except ImportError:
            return shape
        try:
            tool = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
            tool.Build()
            unified = tool.Shape()
        except Exception:
            return shape
        if unified is None or unified.IsNull():
            return shape
        return unified

    def _edge_polylines(shape, flip_y=False):
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.GCPnts import GCPnts_QuasiUniformDeflection
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        if shape is None or shape.IsNull():
            return []
        lines = []
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        while explorer.More():
            edge = TopoDS.Edge_s(explorer.Current())
            explorer.Next()
            try:
                curve = BRepAdaptor_Curve(edge)
                sampled = GCPnts_QuasiUniformDeflection(curve, 0.15)
            except Exception:
                continue
            if not sampled.IsDone() or sampled.NbPoints() < 2:
                continue
            points = []
            for index in range(1, sampled.NbPoints() + 1):
                point = sampled.Value(index)
                y = -point.Y() if flip_y else point.Y()
                points.append((point.X() * PX_PER_MM, y * PX_PER_MM))
            length = 0.0
            for start, end in zip(points, points[1:]):
                length += math.hypot(end[0] - start[0], end[1] - start[1])
            if length < 0.05:
                continue
            lines.append(points)
        return lines

    def _separate_flush_fronts(shapes, view):
        """Copies for hidden-line removal.

        Flush fronts have no depth order, so both outlines are drawn and a rail
        cuts through the device in front of it. The smaller face is moved a
        fraction of a millimetre toward the camera. The originals are unchanged.
        """

        def _front_depth(shape, view):
            bounds = _bounds_mm(shape)
            if bounds is None:
                return 0.0
            xmin, ymin, zmin, xmax, ymax, zmax = bounds
            depth = None
            for x in (xmin, xmax):
                for y in (ymin, ymax):
                    for z in (zmin, zmax):
                        got = x * view[0] + y * view[1] + z * view[2]
                        depth = got if depth is None else min(depth, got)
            return depth

        def _section_area(shape, view):
            """Bounding-box area of the face turned toward the camera."""
            bounds = _bounds_mm(shape)
            if bounds is None:
                return 0.0
            extents = (
                max(bounds[3] - bounds[0], 0.0),
                max(bounds[4] - bounds[1], 0.0),
                max(bounds[5] - bounds[2], 0.0),
            )
            axis = max(range(3), key=lambda index: abs(view[index]))
            area = 1.0
            for index, extent in enumerate(extents):
                if index != axis:
                    area *= extent
            return area

        def _translate_shape(shape, vector):
            from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
            from OCP.gp import gp_Trsf, gp_Vec

            trsf = gp_Trsf()
            trsf.SetTranslation(gp_Vec(vector[0], vector[1], vector[2]))
            return BRepBuilderAPI_Transform(shape, trsf, True).Shape()

        if len(shapes) < 2:
            return list(shapes)
        depths = [_front_depth(shape, view) for shape in shapes]
        areas = [_section_area(shape, view) for shape in shapes]
        buckets = {}
        for index, depth in enumerate(depths):
            buckets.setdefault(round(depth / _FLUSH_MM), []).append(index)
        ordered = list(shapes)
        for members in buckets.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda index: (areas[index], index))
            for rank, index in enumerate(members):
                steps = len(members) - 1 - rank
                if steps <= 0:
                    continue
                distance = steps * _FLUSH_STEP_MM
                ordered[index] = _translate_shape(
                    shapes[index],
                    (-view[0] * distance, -view[1] * distance, -view[2] * distance),
                )
        return ordered

    def _visible_polylines(shapes, view, right):
        from OCP.HLRAlgo import HLRAlgo_Projector
        from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

        if not shapes:
            return []
        shapes = _separate_flush_fronts(shapes, view)
        algo = HLRBRep_Algo()
        algo.Add(_compound(shapes))
        # The projector Z axis points toward the camera. ``view`` points the
        # other way, from the camera into the scene.
        axis = gp_Ax2(
            gp_Pnt(0.0, 0.0, 0.0),
            gp_Dir(-view[0], -view[1], -view[2]),
            gp_Dir(*right),
        )
        algo.Projector(HLRAlgo_Projector(axis))
        algo.Update()
        algo.Hide()
        drawn = HLRBRep_HLRToShape(algo)
        lines = []
        for compound in (drawn.VCompound(), drawn.OutLineVCompound()):
            lines.extend(_edge_polylines(compound, flip_y=True))
        return lines

    def _label_point(shape, right, up):
        bounds = _bounds_mm(shape)
        if bounds is None:
            return None
        xmin, ymin, zmin, xmax, ymax, zmax = bounds
        center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
        return _project(center, right, up)

    def _ray_caster(shapes, view):
        """``cast(point)`` -> ``(offset_mm, body_index)`` of the first body hit.

        The ray runs along ``view`` through ``point``. ``offset_mm`` is how far
        in front of ``point`` the hit is, so a hit on the plane of ``point`` is
        about 0 and a hit behind it is negative. ``cast`` returns None when the
        ray meets nothing. ``_ray_caster`` returns None when OpenCascade cannot
        cast rays; then every face is kept and painted in depth order.
        """
        if not shapes:
            return None
        try:
            from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
            from OCP.TopAbs import TopAbs_FACE
            from OCP.TopExp import TopExp
            from OCP.TopTools import TopTools_IndexedMapOfShape
            from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
        except ImportError:
            return None
        try:
            intersector = IntCurvesFace_ShapeIntersector()
            intersector.Load(_compound(shapes), 1e-7)
            # One face map in body order, so a face index falls in its
            # body's range.
            faces = TopTools_IndexedMapOfShape()
            ends = []
            for shape in shapes:
                TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
                ends.append(faces.Extent())
        except Exception:
            return None
        direction = gp_Dir(*view)
        reach = 1.0e5

        def cast(point):
            origin = gp_Pnt(*(point[i] - view[i] * reach for i in range(3)))
            try:
                intersector.Perform(gp_Lin(origin, direction), 0.0, reach * 2.0)
                count = intersector.NbPnt()
                if count < 1:
                    return None
                nearest = min(range(1, count + 1), key=intersector.WParameter)
                found = faces.FindIndex(intersector.Face(nearest))
                distance = intersector.WParameter(nearest)
            except Exception:
                return None
            owner = None
            if found > 0:
                owner = bisect.bisect_left(ends, found)
            return reach - distance, owner

        return cast

    def _paint_order(prepared, view, right, up):
        """Photos and refdes in the order they are written to the SVG.

        Only faces turned toward the camera count. A face is kept when any
        part of it can be seen. Each face is sampled on a grid, and a sample
        is seen when no solid sits more than ``_HIDDEN_MM`` in front of it.
        Where a ray lands on a body, that body's face is painted over every
        other face covering that spot. That holds for gear inside an open
        rack frame and for flush faces. Anything the rays leave open paints
        from farthest to nearest. Flush faces paint largest first. A refdes
        is painted over its own photo and under whatever body the ray at its
        center meets first.
        """

        def flat(point):
            return (_dot(point, right), _dot(point, up))

        def box_of(points):
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return (min(xs), min(ys), max(xs), max(ys))

        def boxes_touch(a, b):
            return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]

        def inside(face, point):
            ox, oy = face["origin"]
            ax, ay = face["a"]
            bx, by = face["b"]
            det = face["det"]
            x, y = point[0] - ox, point[1] - oy
            s = (x * by - y * bx) / det
            t = (ax * y - ay * x) / det
            return 0.0 < s < 1.0 and 0.0 < t < 1.0

        def grid(photo):
            tl, tr, bl = photo["tl"], photo["tr"], photo["bl"]
            for i in range(_SAMPLES):
                for j in range(_SAMPLES):
                    u = (i + 0.5) / _SAMPLES
                    v = (j + 0.5) / _SAMPLES
                    yield tuple(
                        tl[k] + u * (tr[k] - tl[k]) + v * (bl[k] - tl[k])
                        for k in range(3)
                    )

        def front_depth(bounds):
            xmin, ymin, zmin, xmax, ymax, zmax = bounds
            return min(
                x * view[0] + y * view[1] + z * view[2]
                for x in (xmin, xmax)
                for y in (ymin, ymax)
                for z in (zmin, zmax)
            )

        bodies = []
        for device in prepared:
            bounds = _bounds_mm(device["shape"])
            if bounds is None:
                bodies.append(None)
                continue
            xmin, ymin, zmin, xmax, ymax, zmax = bounds
            corners = [
                (x, y, z) for x in (xmin, xmax) for y in (ymin, ymax) for z in (zmin, zmax)
            ]
            bodies.append({
                "box": box_of([flat(corner) for corner in corners]),
                "center": ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0),
                "front": front_depth(bounds),
            })

        faces = []
        for index, device in enumerate(prepared):
            for photo in device["photos"]:
                normal = photo.get("normal") or (0.0, 0.0, 0.0)
                if _dot(normal, view) >= -1e-8:
                    continue
                origin = flat(photo["tl"])
                tr = flat(photo["tr"])
                bl = flat(photo["bl"])
                a = (tr[0] - origin[0], tr[1] - origin[1])
                b = (bl[0] - origin[0], bl[1] - origin[1])
                det = a[0] * b[1] - a[1] * b[0]
                if abs(det) < 1e-12:
                    continue
                corner = (tr[0] + bl[0] - origin[0], tr[1] + bl[1] - origin[1])
                center = tuple((photo["tr"][i] + photo["bl"][i]) / 2.0 for i in range(3))
                faces.append({
                    "device": index,
                    "photo": photo,
                    "origin": origin,
                    "a": a,
                    "b": b,
                    "det": det,
                    "box": box_of([origin, tr, bl, corner]),
                    "depth": _dot(center, view),
                    "area": float(photo.get("width") or 0.0) * float(photo.get("height") or 0.0),
                    "kept": True,
                })

        cast = _ray_caster([device["shape"] for device in prepared], view)
        # Which body each ray lands on, at the 2D spot the ray passes through,
        # and how much screen area that sample stands for.
        seen = []
        if cast is not None:
            for face in faces:
                crowded = any(
                    other is not None
                    and index != face["device"]
                    and boxes_touch(other["box"], face["box"])
                    for index, other in enumerate(bodies)
                )
                if not crowded:
                    continue
                share = abs(face["det"]) / (_SAMPLES * _SAMPLES)
                visible = False
                for point in grid(face["photo"]):
                    hit = cast(point)
                    if hit is None or hit[0] <= _HIDDEN_MM:
                        visible = True
                    if hit is not None and hit[1] is not None:
                        seen.append((flat(point), hit[1], share))
                face["kept"] = visible

        def covering(point, device=None, skip=None):
            return [
                index for index, face in enumerate(faces)
                if face["kept"]
                and (device is None or face["device"] == device)
                and face["device"] != skip
                and face["box"][0] <= point[0] <= face["box"][2]
                and face["box"][1] <= point[1] <= face["box"][3]
                and inside(face, point)
            ]

        # A ray that lands on a body shows that body, even where its own
        # samples were all covered.
        for point, owner, _share in seen:
            for index in covering(point, device=owner):
                faces[index]["kept"] = True

        nodes = []
        node_of_face = {}
        for index, face in enumerate(faces):
            if not face["kept"]:
                continue
            node_of_face[index] = len(nodes)
            nodes.append({
                "item": ("photo", face["photo"]),
                "key": (-round(face["depth"] / _FLUSH_MM), -face["area"], 0, len(nodes)),
            })
        # (before, after) -> screen area that is wrong if ``after`` paints first.
        edges = {}

        def need(before, after, weight):
            edges[(before, after)] = edges.get((before, after), 0.0) + weight

        for point, owner, share in seen:
            mine = covering(point, device=owner)
            if not mine:
                continue
            top = min(mine, key=lambda index: faces[index]["depth"])
            for index in covering(point, skip=owner):
                need(node_of_face[index], node_of_face[top], share)

        for index, device in enumerate(prepared):
            body = bodies[index]
            if not device["refdes"] or body is None:
                continue
            label = len(nodes)
            point = flat(body["center"])
            mine = covering(point, device=index)
            own_faces = [
                face for face in faces if face["kept"] and face["device"] == index
            ]
            if own_faces:
                nearest = min(own_faces, key=lambda face: face["depth"])
                key = (-round(nearest["depth"] / _FLUSH_MM), -nearest["area"], 1, label)
            else:
                key = (-round(body["front"] / _FLUSH_MM), 0.0, 1, label)
            nodes.append({"item": ("label", index), "key": key})
            # A refdes is a point, so give it more weight than any face sample.
            for face_index in mine:
                need(node_of_face[face_index], label, float("inf"))
            hit = cast(body["center"]) if cast is not None else None
            seer = hit[1] if hit is not None else None
            if seer == index:
                for face_index in covering(point, skip=index):
                    need(node_of_face[face_index], label, 1.0)
            elif seer is not None:
                for face_index in covering(point, device=seer):
                    need(label, node_of_face[face_index], 1.0)

        # Topological order. Ties go farthest first. Faces that overlap each
        # other, like a rack frame and the gear seen through it, can form a
        # cycle. Then the face whose waiting costs the least area goes next.
        after = [[] for _node in nodes]
        incoming = [{} for _node in nodes]
        for (before, later), weight in edges.items():
            if before == later:
                continue
            after[before].append(later)
            incoming[later][before] = weight
        ready = [(node["key"], index) for index, node in enumerate(nodes) if not incoming[index]]
        heapq.heapify(ready)
        done = [False] * len(nodes)
        order = []
        while len(order) < len(nodes):
            if not ready:
                stuck = min(
                    (sum(incoming[index].values()), nodes[index]["key"], index)
                    for index in range(len(nodes))
                    if not done[index]
                )
                ready.append((nodes[stuck[2]]["key"], stuck[2]))
            _key, index = heapq.heappop(ready)
            if done[index]:
                continue
            done[index] = True
            order.append(nodes[index]["item"])
            for later in after[index]:
                incoming[later].pop(index, None)
                if not incoming[later] and not done[later]:
                    heapq.heappush(ready, (nodes[later]["key"], later))
        return order

    _require_opencascade()
    factor = _number("scale", 1 if scale is None else scale)
    if factor <= 0:
        raise ValueError("scale must be greater than zero")
    weight = _number("lineweight", 1 if lineweight is None else lineweight)
    if weight < 0:
        raise ValueError("lineweight must be zero or greater")
    view, right, up = view_basis(orientation)
    prepared = []
    for device in devices:
        shape = device.get("shape")
        if shape is None:
            continue
        prepared.append({
            "refdes": device.get("refdes") or "",
            "shape": _unify(shape),
            "photos": list(device.get("photos") or []),
        })
    shapes = [device["shape"] for device in prepared]
    polylines = _visible_polylines(shapes, view, right)
    paint = []
    for kind, item in _paint_order(prepared, view, right, up):
        if kind == "photo":
            paint.append(("photo", item))
            continue
        device = prepared[item]
        label_at = _label_point(device["shape"], right, up)
        if label_at is not None:
            paint.append(("label", (device["refdes"], label_at)))

    points = [point for line in polylines for point in line]
    for kind, item in paint:
        if kind == "label":
            points.append(item[1])
            continue
        for key in ("tl", "tr", "bl"):
            points.append(_project(item[key], right, up))
    if points:
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
    else:
        min_x = min_y = 0.0

    def shift(point):
        return (point[0] - min_x, point[1] - min_y)

    polylines = [[shift(point) for point in line] for line in polylines]
    shifted = []
    for kind, item in paint:
        if kind == "label":
            name, point = item
            shifted.append(("label", name, shift(point)))
            continue
        shifted.append((
            "photo",
            item,
            shift(_project(item["tl"], right, up)),
            shift(_project(item["tr"], right, up)),
            shift(_project(item["bl"], right, up)),
        ))

    content_w = 0.0
    content_h = 0.0
    if points:
        content_w = max(point[0] for point in points) - min_x
        content_h = max(point[1] for point in points) - min_y
    page_w = max(content_w * factor, 1.0)
    page_h = max(content_h * factor, 1.0)
    if not points:
        page_w = page_h = 1000.0

    stroke = weight / factor
    font = 12.0 / factor
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            f'version="1.1" width="{_num(page_w)}" height="{_num(page_h)}">'
        ),
        f'  <g id="{_xml_attr(artifact_id)}-contents-start">',
        f'    <g id="{_xml_attr(artifact_id)}-scale_group" transform="scale({_num(factor)})">',
        '      <g id="bodies">',
    ]
    for entry in shifted:
        if entry[0] == "photo":
            _kind, photo, tl, tr, bl = entry
            width = max(float(photo.get("width") or 0.0), 1e-6) * PX_PER_MM
            height = max(float(photo.get("height") or 0.0), 1e-6) * PX_PER_MM
            a = (tr[0] - tl[0]) / width
            b = (tr[1] - tl[1]) / width
            c = (bl[0] - tl[0]) / height
            d = (bl[1] - tl[1]) / height
            href = photo.get("href") or ""
            if not href:
                corner = (tr[0] + bl[0] - tl[0], tr[1] + bl[1] - tl[1])
                outline = " ".join(
                    f"{_num(point[0])} {_num(point[1])}"
                    for point in (tl, tr, corner, bl)
                )
                lines.append(
                    f'        <path d="M {outline} Z" fill="#ffffff" stroke="none"/>'
                )
                continue
            href = _xml_attr(href)
            matrix = " ".join(_num(value) for value in (a, b, c, d, tl[0], tl[1]))
            lines.append(
                f'        <image href="{href}" xlink:href="{href}" '
                f'x="0" y="0" width="{_num(width)}" height="{_num(height)}" '
                f'transform="matrix({matrix})" preserveAspectRatio="none"/>'
            )
            continue
        _kind, name, point = entry
        lines.append(
            f'        <text id="{_xml_attr(name)}-label" x="{_num(point[0])}" y="{_num(point[1])}" '
            f'font-size="{_num(font)}px" font-family="Helvetica, Arial, sans-serif" '
            f'fill="#000000" text-anchor="middle" dominant-baseline="middle">'
            f"{_xml_text(name)}</text>"
        )
    lines.append("      </g>")
    lines.append('      <g id="edges">')
    for line in polylines:
        rendered = " ".join(f"{_num(x)},{_num(y)}" for x, y in line)
        lines.append(
            f'        <polyline points="{rendered}" fill="none" stroke="#000000" '
            f'stroke-width="{_num(stroke)}" stroke-linejoin="round" stroke-linecap="round"/>'
        )
    lines.append("      </g>")
    lines.append("    </g>")
    lines.append("  </g>")
    lines.append(f'  <g id="{_xml_attr(artifact_id)}-contents-end"></g>')
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


def render_system_drawing(
    artifact_id, scale=1, orientation="front", hidden_instances=None, lineweight=1
):
    """Master SVG of the open system's physical model."""

    def load_devices(hidden_instances=None):
        """Posed device solids and face photos from the open system's physical model."""
        _require_opencascade()
        from OCP.gp import gp_Pnt, gp_Vec

        from harnice import fileio
        from harnice.utils import physical_assembly, physical_body, step_utils

        def _apply_point(trsf, point):

            moved = gp_Pnt(*point)
            moved.Transform(trsf)
            return (moved.X(), moved.Y(), moved.Z())

        if hidden_instances is None:
            hidden = set()
        elif isinstance(hidden_instances, str):
            name = hidden_instances.strip()
            hidden = {name} if name else set()
        elif isinstance(hidden_instances, (list, tuple, set)):
            hidden = {str(item).strip() for item in hidden_instances if str(item).strip()}
        else:
            raise ValueError("hidden_instances must be a list of device names")
        discovered = physical_assembly.discover()
        json_path = fileio.path("physical assembly")
        model = physical_assembly.load_assembly(json_path)
        placements = physical_assembly.locked_placements(discovered, model)
        body_names = [
            device["refdes"] for device in discovered
            if device["has_body"] and device["refdes"] not in hidden
        ]
        placements = physical_assembly.place_new_devices(placements, body_names)
        devices = []
        for device in discovered:
            refdes = device["refdes"]
            if not device["has_body"] or refdes in hidden:
                continue
            shape = step_utils.read_step_shape(device["step_path"])
            if shape is None:
                raise ValueError(f"could not read {refdes} body")
            pose = placements[refdes]
            trsf = step_utils.pose_trsf(
                pose["x"] * physical_assembly.INCH_TO_MM,
                pose["y"] * physical_assembly.INCH_TO_MM,
                pose["z"] * physical_assembly.INCH_TO_MM,
                pose["alpha"],
                pose["beta"],
                pose["gamma"],
            )
            world = step_utils.transform_shape(
                shape,
                pose["x"] * physical_assembly.INCH_TO_MM,
                pose["y"] * physical_assembly.INCH_TO_MM,
                pose["z"] * physical_assembly.INCH_TO_MM,
                pose["alpha"],
                pose["beta"],
                pose["gamma"],
            )
            bounds = _bounds_mm(shape)
            photos = []
            if bounds is not None:
                records = physical_body.read_image_records(device["step_path"])
                vertices = step_utils.shape_vertices(shape)
                for face in physical_body.FACE_NAMES:
                    record = records.get(face) or {}
                    image = ""
                    if record:
                        image = physical_body.face_image_path(device["step_path"], face)
                    corners = _face_corners(
                        bounds, face, record.get("orientation") or 0.0, vertices
                    )
                    if corners is None:
                        continue
                    href = ""
                    if image:
                        absolute = os.path.realpath(image)
                        try:
                            rev = os.path.realpath(fileio.rev_directory())
                            inside = os.path.commonpath([absolute, rev]) == rev
                        except ValueError:
                            inside = False
                        if inside:
                            href = os.path.relpath(absolute, rev).replace(os.sep, "/")
                        else:
                            href = absolute.replace(os.sep, "/")
                    moved = gp_Vec(*corners["normal"])
                    moved.Transform(trsf)
                    photos.append({
                        "href": href,
                        "normal": (moved.X(), moved.Y(), moved.Z()),
                        "tl": _apply_point(trsf, corners["tl"]),
                        "tr": _apply_point(trsf, corners["tr"]),
                        "bl": _apply_point(trsf, corners["bl"]),
                        "width": corners["width"],
                        "height": corners["height"],
                    })
            devices.append({"refdes": refdes, "shape": world, "photos": photos})
        return devices

    if not str(artifact_id or "").strip():
        raise ValueError("artifact_id is required")
    devices = load_devices(hidden_instances)
    return render_svg(
        artifact_id,
        devices,
        scale=scale,
        orientation=orientation,
        lineweight=lineweight,
    )
