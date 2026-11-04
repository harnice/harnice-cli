"""Orthographic line drawing of a system physical assembly.

OpenCascade hidden-line removal projects each device body to its visible
edges and silhouettes. Each device name is drawn at the body center. The
name is left off when half or more of that silhouette sits behind another
body. Face photos are SVG image links on the same faces the physical-model
viewer paints, drawn from farthest to nearest so a closer screenshot covers
one behind it. A rectangular body fills its bounding box. A rack chassis
back is the 17 inch panel, not the 19 inch ears. The PDF export embeds
those links; this module leaves them as paths.

``orientation`` is a face name or a viewport rotation. ``(0, 0, 0)`` is the
front view: look along +Y, +X to the right, +Z up. A dict or a 3-number
sequence is ``alpha``, ``beta``, ``gamma`` in degrees,
``R = Rx(α) · Ry(β) · Rz(γ)`` applied to that front camera. Named views
look straight at that face of the bounding box, with the picture upright
the way the viewer shows it.
"""

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

# A refdes is omitted when at least this fraction of the silhouette is behind
# some other body. Coverage is the union of whatever is closer to the camera.
_HIDDEN_LABEL_FRACTION = 0.5


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


def _refdes_mostly_hidden(shapes, view, right, up):
    """True for each shape when half or more of its silhouette is behind another.

    Samples are taken on the view plane. A sample counts as hidden when some
    other shape's surface is closer to the camera than this shape's own front
    surface. Flush faces share a depth, so neither one hides the other.
    """

    def _project(point):
        return (_dot(point, right), _dot(point, up), _dot(point, view))

    def _triangles(shape):
        from harnice.utils import step_utils

        projected = []
        try:
            bodies = step_utils.tessellate_shape(shape, deflection_mm=1.0)
        except Exception:
            return []
        for body in bodies:
            vertices = body["vertices"]
            indices = body["indices"]
            for start in range(0, len(indices), 3):
                tri = []
                for index in indices[start:start + 3]:
                    offset = index * 3
                    point = (vertices[offset], vertices[offset + 1], vertices[offset + 2])
                    tri.append(_project(point))
                area = (
                    (tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1])
                    - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1])
                )
                if abs(area) < 1e-8:
                    continue
                projected.append(tri)
        return projected

    def _bounds(tris):
        umin = min(point[0] for tri in tris for point in tri)
        umax = max(point[0] for tri in tris for point in tri)
        vmin = min(point[1] for tri in tris for point in tri)
        vmax = max(point[1] for tri in tris for point in tri)
        return umin, vmin, umax, vmax

    def _overlaps(a, b):
        return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]

    def _depth_at(tri, u, v):
        (u1, v1, d1), (u2, v2, d2), (u3, v3, d3) = tri
        denom = (v2 - v3) * (u1 - u3) + (u3 - u2) * (v1 - v3)
        if abs(denom) < 1e-12:
            return None
        wa = ((v2 - v3) * (u - u3) + (u3 - u2) * (v - v3)) / denom
        wb = ((v3 - v1) * (u - u3) + (u1 - u3) * (v - v3)) / denom
        wc = 1.0 - wa - wb
        if wa < -1e-8 or wb < -1e-8 or wc < -1e-8:
            return None
        return wa * d1 + wb * d2 + wc * d3

    def _paint(tris, umin, vmin, pitch_u, pitch_v, width, height, buffer):
        for tri in tris:
            xs = [point[0] for point in tri]
            ys = [point[1] for point in tri]
            x0 = max(0, int((min(xs) - umin) / pitch_u))
            x1 = min(width, int((max(xs) - umin) / pitch_u) + 1)
            y0 = max(0, int((min(ys) - vmin) / pitch_v))
            y1 = min(height, int((max(ys) - vmin) / pitch_v) + 1)
            for y in range(y0, y1):
                v = vmin + (y + 0.5) * pitch_v
                row = y * width
                for x in range(x0, x1):
                    depth = _depth_at(tri, umin + (x + 0.5) * pitch_u, v)
                    if depth is None:
                        continue
                    slot = row + x
                    if depth < buffer[slot]:
                        buffer[slot] = depth

    if len(shapes) < 2:
        return [False] * len(shapes)
    # A hundred samples on the short side keeps a body split in half from
    # flipping the 50% test because of a single row of pixels.
    samples = 100
    meshes = [_triangles(shape) for shape in shapes]
    boxes = [_bounds(tris) if tris else None for tris in meshes]
    hidden = []
    untouched = float("inf")
    for index, tris in enumerate(meshes):
        box = boxes[index]
        if box is None:
            hidden.append(False)
            continue
        umin, vmin, umax, vmax = box
        span_u = max(umax - umin, 1e-9)
        span_v = max(vmax - vmin, 1e-9)
        pitch = min(span_u, span_v) / samples
        if max(span_u, span_v) / pitch > samples * 4:
            pitch = max(span_u, span_v) / (samples * 4)
        width = max(1, int(round(span_u / pitch)))
        height = max(1, int(round(span_v / pitch)))
        pitch_u = span_u / width
        pitch_v = span_v / height
        own = [untouched] * (width * height)
        ahead = [untouched] * (width * height)
        _paint(tris, umin, vmin, pitch_u, pitch_v, width, height, own)
        for other_index, other_tris in enumerate(meshes):
            if other_index == index or not other_tris:
                continue
            if not _overlaps(box, boxes[other_index]):
                continue
            _paint(other_tris, umin, vmin, pitch_u, pitch_v, width, height, ahead)
        covered = 0
        blocked = 0
        for near, front in zip(own, ahead):
            if near == untouched:
                continue
            covered += 1
            if front < near - _FLUSH_MM:
                blocked += 1
        hidden.append(covered > 0 and blocked / covered >= _HIDDEN_LABEL_FRACTION)
    return hidden


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

    def _content_insets(href):
        """Transparent margin of a linked photo, as fractions of its width and height.

        Returns ``(left, top, right, bottom)``. A missing file or a photo with no
        transparent edge is ``(0, 0, 0, 0)``.
        """
        if not href or href.startswith("data:"):
            return (0.0, 0.0, 0.0, 0.0)
        path = href if os.path.isabs(href) else ""
        if not path:
            from harnice import fileio

            path = os.path.join(fileio.rev_directory(), href)
        if not os.path.isfile(path):
            return (0.0, 0.0, 0.0, 0.0)
        try:
            from PIL import Image
        except ImportError:
            return (0.0, 0.0, 0.0, 0.0)
        try:
            image = Image.open(path).convert("RGBA")
        except Exception:
            return (0.0, 0.0, 0.0, 0.0)
        width, height = image.size
        if width < 2 or height < 2:
            return (0.0, 0.0, 0.0, 0.0)
        pixels = image.load()
        min_x, min_y, max_x, max_y = width, height, -1, -1
        for y in range(height):
            for x in range(width):
                if pixels[x, y][3] <= 8:
                    continue
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
        if max_x < min_x:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            min_x / width,
            min_y / height,
            (width - 1 - max_x) / width,
            (height - 1 - max_y) / height,
        )

    def _cover_face(tl, tr, bl, insets):
        """Quad that maps a photo's opaque pixels onto the face.

        ``insets`` are the transparent margins. The returned corners are the full
        image; the margins land just outside the face and do not paint.
        """
        left, top, right, bottom = insets
        span_u = 1.0 - left - right
        span_v = 1.0 - top - bottom
        if span_u < 0.5 or span_v < 0.5:
            return tl, tr, bl

        def at(u, v):
            return (
                tl[0] + (tr[0] - tl[0]) * u + (bl[0] - tl[0]) * v,
                tl[1] + (tr[1] - tl[1]) * u + (bl[1] - tl[1]) * v,
            )

        u0 = -left / span_u
        v0 = -top / span_v
        return at(u0, v0), at(u0 + 1.0 / span_u, v0), at(u0, v0 + 1.0 / span_v)

    def _photo_in_front(photo, view, intersector):
        """True when no solid sits between the camera and the face center."""
        if intersector is None:
            return True
        from OCP.gp import gp_Dir, gp_Lin, gp_Pnt

        center = tuple((photo["tr"][i] + photo["bl"][i]) / 2.0 for i in range(3))
        distance = 1.0e5
        origin = tuple(center[i] - view[i] * distance for i in range(3))
        line = gp_Lin(gp_Pnt(*origin), gp_Dir(*view))
        try:
            intersector.Perform(line, 0.0, distance * 2.0)
            count = intersector.NbPnt()
        except Exception:
            return True
        if count < 1:
            return True
        nearest = min(intersector.WParameter(index) for index in range(1, count + 1))
        return nearest >= distance - 0.5

    def _load_intersector(shapes):
        if not shapes:
            return None
        try:
            from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
        except ImportError:
            return None
        try:
            intersector = IntCurvesFace_ShapeIntersector()
            intersector.Load(_compound(shapes), 1e-7)
        except Exception:
            return None
        return intersector

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
    intersector = _load_intersector(shapes)
    name_hidden = _refdes_mostly_hidden(shapes, view, right, up)

    photos = []
    labels = []
    for device, skip_name in zip(prepared, name_hidden):
        if skip_name:
            continue
        label_at = _label_point(device["shape"], right, up)
        if device["refdes"] and label_at is not None:
            labels.append((device["refdes"], label_at))
        for photo in device["photos"]:
            normal = photo.get("normal") or (0.0, 0.0, 0.0)
            if _dot(normal, view) >= -1e-8:
                continue
            if not _photo_in_front(photo, view, intersector):
                continue
            photos.append(photo)

    def _photo_depth(photo):
        # ``view`` points into the scene, so a larger value is farther away.
        center = tuple((photo["tr"][i] + photo["bl"][i]) / 2.0 for i in range(3))
        return _dot(center, view)

    photos.sort(key=_photo_depth, reverse=True)

    points = [point for line in polylines for point in line]
    points.extend(label[1] for label in labels)
    for photo in photos:
        for key in ("tl", "tr", "bl"):
            points.append(_project(photo[key], right, up))
    if points:
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
    else:
        min_x = min_y = 0.0

    def shift(point):
        return (point[0] - min_x, point[1] - min_y)

    polylines = [[shift(point) for point in line] for line in polylines]
    labels = [(name, shift(point)) for name, point in labels]
    shifted_photos = []
    for photo in photos:
        tl = shift(_project(photo["tl"], right, up))
        tr = shift(_project(photo["tr"], right, up))
        bl = shift(_project(photo["bl"], right, up))
        shifted_photos.append((photo, tl, tr, bl))

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
        '      <g id="photos">',
    ]
    for photo, tl, tr, bl in shifted_photos:
        width = max(float(photo.get("width") or 0.0), 1e-6) * PX_PER_MM
        height = max(float(photo.get("height") or 0.0), 1e-6) * PX_PER_MM
        tl, tr, bl = _cover_face(tl, tr, bl, _content_insets(photo.get("href") or ""))
        a = (tr[0] - tl[0]) / width
        b = (tr[1] - tl[1]) / width
        c = (bl[0] - tl[0]) / height
        d = (bl[1] - tl[1]) / height
        href = _xml_attr(photo.get("href") or "")
        matrix = " ".join(_num(item) for item in (a, b, c, d, tl[0], tl[1]))
        lines.append(
            f'        <image href="{href}" xlink:href="{href}" '
            f'x="0" y="0" width="{_num(width)}" height="{_num(height)}" '
            f'transform="matrix({matrix})" preserveAspectRatio="none"/>'
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
    lines.append('      <g id="labels">')
    for name, point in labels:
        lines.append(
            f'        <text id="{_xml_attr(name)}-label" x="{_num(point[0])}" y="{_num(point[1])}" '
            f'font-size="{_num(font)}px" font-family="Helvetica, Arial, sans-serif" '
            f'fill="#000000" text-anchor="middle" dominant-baseline="middle">'
            f"{_xml_text(name)}</text>"
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
                for face, record in records.items():
                    image = physical_body.face_image_path(device["step_path"], face)
                    corners = _face_corners(
                        bounds, face, record.get("orientation") or 0.0, vertices
                    )
                    if not image or corners is None:
                        continue
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
