"""Low-fidelity AP214 STEP envelopes.

Solids are faceted approximations of catalog envelopes (millimetres).
Coordinate frame matches Harnice 2D drawings: +X along the cable/body axis,
+Y up, +Z completing a right-handed triad.
"""

from __future__ import annotations

import math
import os
import sys
from contextlib import contextmanager

# ISO 10303-21 requires a time_stamp in FILE_NAME. A fixed value keeps
# regenerated geometry byte-identical instead of diffing on every build.
_STEP_TIMESTAMP = "1970-01-01T00:00:00"


def _prepare_ocp_dll_search():
    """Let a frozen Windows app load OpenCascade DLLs that sit beside the exe.

    Python 3.8+ does not search ``PATH`` for extension-module dependencies.
    Nuitka copies those DLLs next to ``Harnice.exe`` and into ``OCP/``.
    """
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    from harnice.runtime import _bundle_dir

    bundled = _bundle_dir()
    if bundled is None:
        return
    for folder in (bundled, bundled / "OCP"):
        if not folder.is_dir():
            continue
        try:
            os.add_dll_directory(str(folder))
        except (OSError, ValueError):
            pass


def ocp_import_error():
    """The ImportError from loading OpenCascade, or None when it loads."""
    _prepare_ocp_dll_search()
    try:
        from OCP.STEPControl import STEPControl_Reader  # noqa: F401
    except ImportError as exc:
        return exc
    return None


def ocp_unavailable_message(exc):
    """Say that STEP could not run, and include the real import error."""
    detail = str(exc).strip() if exc is not None else ""
    message = "OpenCascade failed to load, so STEP files cannot be read or written."
    if detail:
        return f"{message} {detail}"
    return message


@contextmanager
def _silence_stdio():
    """Mute C++ stdout/stderr (OpenCascade STEP transfer banners)."""
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        os.close(devnull)


N_SIDES = 16
_EPS = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _len(a):
    return math.sqrt(_dot(a, a))


def _norm(a):
    mag = _len(a)
    if mag < _EPS:
        return (0.0, 0.0, 0.0)
    return _scale(a, 1.0 / mag)


def _fmt(value):
    text = f"{value:.4f}"
    if text == "-0.0000":
        return "0.0000"
    return text


def revolution_triangles(stations, n_sides=N_SIDES):
    """
    Revolve ``(x, radius)`` stations about +X into outward-wound triangles.

    **Args:**
    - `stations` (list): ``(x_mm, radius_mm)`` samples along the axis of revolution.
    - `n_sides` (int): Number of facets around the revolution.

    **Returns:**
    - `list`: Triangles as ``((x,y,z), (x,y,z), (x,y,z))`` tuples in millimetres.
    """
    cleaned = []
    for x, radius in stations:
        if radius <= 0:
            raise ValueError("revolution radius must be positive")
        if cleaned and abs(x - cleaned[-1][0]) < _EPS and abs(radius - cleaned[-1][1]) < _EPS:
            continue
        cleaned.append((float(x), float(radius)))
    if len(cleaned) < 2:
        raise ValueError("need at least two revolution stations")

    rings = []
    for x, radius in cleaned:
        ring = []
        for k in range(n_sides):
            theta = 2.0 * math.pi * k / n_sides
            ring.append((x, radius * math.cos(theta), radius * math.sin(theta)))
        rings.append(ring)

    tris = []
    for i in range(len(rings) - 1):
        for k in range(n_sides):
            k2 = (k + 1) % n_sides
            a, b = rings[i][k], rings[i][k2]
            c, d = rings[i + 1][k2], rings[i + 1][k]
            tris.append((a, b, c))
            tris.append((a, c, d))

    x0, _r0 = cleaned[0]
    x1, _r1 = cleaned[-1]
    hub0 = (x0, 0.0, 0.0)
    hub1 = (x1, 0.0, 0.0)
    for k in range(n_sides):
        k2 = (k + 1) % n_sides
        # Start cap: outward −X. Looking along −X, YZ winding is clockwise of +Y ring.
        tris.append((hub0, rings[0][k2], rings[0][k]))
        # End cap: outward +X.
        tris.append((hub1, rings[-1][k], rings[-1][k2]))
    return _outward(tris)


def _closed_yz(yz):
    ring = [(float(y), float(z)) for y, z in yz]
    if len(ring) < 3:
        raise ValueError("prism profile needs at least 3 vertices")
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        raise ValueError("prism profile needs at least 3 vertices")
    return ring


def prism_segments_triangles(segments):
    """Extruded YZ polygons as triangles. Each segment is (x0, x1, yz_ring)."""
    tris = []
    for x0, x1, yz in segments:
        if abs(x1 - x0) < _EPS:
            continue
        xa, xb = (x0, x1) if x1 > x0 else (x1, x0)
        ring = _closed_yz(yz)
        n = len(ring)
        for i in range(n):
            y0, z0 = ring[i]
            y1, z1 = ring[(i + 1) % n]
            a, b = (xa, y0, z0), (xb, y0, z0)
            c, d = (xb, y1, z1), (xa, y1, z1)
            tris.append((a, b, c))
            tris.append((a, c, d))
        origin = ring[0]
        for i in range(1, n - 1):
            p, q = ring[i], ring[i + 1]
            tris.append(
                ((xb, origin[0], origin[1]), (xb, p[0], p[1]), (xb, q[0], q[1]))
            )
            tris.append(
                ((xa, origin[0], origin[1]), (xa, q[0], q[1]), (xa, p[0], p[1]))
            )
    if not tris:
        raise ValueError("prism segments produced no volume")
    return _outward(tris)


def sweep_triangles(points, radii, n_sides=N_SIDES):
    """
    Sweep circular sections along a 3D polyline into outward-wound triangles.

    **Args:**
    - `points` (list): Centerline stations as ``(x, y, z)`` millimetres.
    - `radii` (list): Radius at each station, same length as `points`.
    - `n_sides` (int): Number of facets around each circular section.

    **Returns:**
    - `list`: Triangles as ``((x,y,z), (x,y,z), (x,y,z))`` tuples in millimetres.
    """
    if len(points) != len(radii) or len(points) < 2:
        raise ValueError("sweep needs matching points and radii, at least two stations")
    frames = _miter_frames(points)
    rings = []
    for point, radius, (_tangent, normal, binormal) in zip(points, radii, frames):
        if radius <= 0:
            raise ValueError("sweep radius must be positive")
        ring = []
        for k in range(n_sides):
            theta = 2.0 * math.pi * k / n_sides
            offset = _add(
                _scale(normal, radius * math.cos(theta)),
                _scale(binormal, radius * math.sin(theta)),
            )
            ring.append(_add(point, offset))
        rings.append(ring)

    tris = []
    for i in range(len(rings) - 1):
        for k in range(n_sides):
            k2 = (k + 1) % n_sides
            a, b = rings[i][k], rings[i][k2]
            c, d = rings[i + 1][k2], rings[i + 1][k]
            tris.append((a, b, c))
            tris.append((a, c, d))

    start_p = points[0]
    end_p = points[-1]
    for k in range(n_sides):
        k2 = (k + 1) % n_sides
        tris.append((start_p, rings[0][k2], rings[0][k]))
        tris.append((end_p, rings[-1][k], rings[-1][k2]))
    return _outward(tris)


def _miter_frames(points):
    tangents = []
    for i, point in enumerate(points):
        if i == 0:
            tangents.append(_norm(_sub(points[1], point)))
        elif i == len(points) - 1:
            tangents.append(_norm(_sub(point, points[i - 1])))
        else:
            incoming = _norm(_sub(point, points[i - 1]))
            outgoing = _norm(_sub(points[i + 1], point))
            bisector = _add(incoming, outgoing)
            tangents.append(_norm(bisector) if _len(bisector) > _EPS else incoming)

    frames = []
    for i, tangent in enumerate(tangents):
        if i == 0:
            y_axis = (0.0, 1.0, 0.0)
            normal = _sub(y_axis, _scale(tangent, _dot(y_axis, tangent)))
            if _len(normal) < 0.1:
                z_axis = (0.0, 0.0, 1.0)
                normal = _sub(z_axis, _scale(tangent, _dot(z_axis, tangent)))
            normal = _norm(normal)
        else:
            prev_t, prev_normal, _prev_b = frames[-1]
            axis = _cross(prev_t, tangent)
            sine = _len(axis)
            cosine = max(-1.0, min(1.0, _dot(prev_t, tangent)))
            if sine < _EPS:
                normal = prev_normal
            else:
                axis = _norm(axis)
                angle = math.atan2(sine, cosine)
                normal = _rotate(prev_normal, axis, angle)
            normal = _sub(normal, _scale(tangent, _dot(normal, tangent)))
            normal = _norm(normal)
        binormal = _norm(_cross(tangent, normal))
        normal = _norm(_cross(binormal, tangent))
        frames.append((tangent, normal, binormal))
    return frames


def _rotate(vector, axis, angle):
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return _add(
        _add(_scale(vector, cosine), _scale(_cross(axis, vector), sine)),
        _scale(axis, _dot(axis, vector) * (1.0 - cosine)),
    )


def _outward(tris):
    """Flip any triangle whose normal points toward the solid centroid."""
    cx = cy = cz = 0.0
    count = 0
    for a, b, c in tris:
        for point in (a, b, c):
            cx += point[0]
            cy += point[1]
            cz += point[2]
            count += 1
    centroid = (cx / count, cy / count, cz / count)
    oriented = []
    for a, b, c in tris:
        normal = _cross(_sub(b, a), _sub(c, a))
        face_center = _scale(_add(_add(a, b), c), 1.0 / 3.0)
        if _dot(normal, _sub(face_center, centroid)) < 0:
            oriented.append((a, c, b))
        else:
            oriented.append((a, b, c))
    return oriented


def _ptkey(point):
    return (_fmt(point[0]), _fmt(point[1]), _fmt(point[2]))


def _coords(key):
    return (float(key[0]), float(key[1]), float(key[2]))


def _ref_list(ids):
    """Comma-separated #id list wrapped to ~72 characters (ISO 10303-21)."""
    chunks = []
    line = ""
    for i, eid in enumerate(ids):
        token = f"#{eid}"
        piece = token if i == 0 else "," + token
        if line and len(line) + len(piece) > 70:
            chunks.append(line)
            line = piece
        else:
            line += piece
    if line:
        chunks.append(line)
    return "\n".join(chunks)


def write_step_file(path, part_number, triangles, description="low-fidelity envelope"):
    """
    Write an AP214 MANIFOLD_SOLID_BREP (mm) from outward triangles.

    Faces use EDGE_LOOP / ORIENTED_EDGE / EDGE_CURVE topology so OpenCascade
    and typical CAD STEP readers can transfer the solid.

    **Args:**
    - `path` (str): Destination ``.step`` path.
    - `part_number` (str): Product name written into the STEP header.
    - `triangles` (list): Outward-wound triangles in millimetres.
    - `description` (str): Product description in the STEP header.

    **Returns:**
    - `str`: The path that was written.
    """
    if not triangles:
        raise ValueError("no triangles to write")

    try:
        _ocp_write_shape(_ocp_solid_from_triangles(triangles), path, part_number)
        return path
    except ImportError:
        pass

    keys_in_order = []
    seen = set()
    for tri in triangles:
        for point in tri:
            key = _ptkey(point)
            if key in seen:
                continue
            seen.add(key)
            keys_in_order.append(key)

    lines = []
    eid = 0

    def next_id():
        nonlocal eid
        eid += 1
        return eid

    def emit(entity):
        i = next_id()
        lines.append(f"#{i}={entity};")
        return i

    def emit_block(first_line, body_lines):
        i = next_id()
        lines.append(f"#{i}={first_line}")
        lines.extend(body_lines)
        return i

    header = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('Harnice low-fidelity catalog envelope'),'2;1');",
        (
            f"FILE_NAME('{_step_string(part_number)}.step','{_STEP_TIMESTAMP}',"
            f"('Harnice'),('Harnice'),'Harnice','','');"
        ),
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
    ]

    app_ctx = emit(
        "APPLICATION_CONTEXT('core data for automotive mechanical design processes')"
    )
    emit(
        f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
        f"'automotive_design',2000,#{app_ctx})"
    )
    prod_ctx = emit(f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')")
    def_ctx = emit(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')")
    product = emit(
        f"PRODUCT('{_step_string(part_number)}','{_step_string(part_number)}',"
        f"'{_step_string(description)}',(#{prod_ctx}))"
    )
    formation = emit(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
    definition = emit(f"PRODUCT_DEFINITION('design','',#{formation},#{def_ctx})")
    shape = emit(f"PRODUCT_DEFINITION_SHAPE('','',#{definition})")
    emit(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{product}))")

    length_unit = emit_block(
        "(",
        [
            "LENGTH_UNIT()",
            "NAMED_UNIT(*)",
            "SI_UNIT(.MILLI.,.METRE.)",
            ");",
        ],
    )
    angle_unit = emit_block(
        "(",
        [
            "NAMED_UNIT(*)",
            "PLANE_ANGLE_UNIT()",
            "SI_UNIT($,.RADIAN.)",
            ");",
        ],
    )
    solid_unit = emit_block(
        "(",
        [
            "NAMED_UNIT(*)",
            "SI_UNIT($,.STERADIAN.)",
            "SOLID_ANGLE_UNIT()",
            ");",
        ],
    )
    uncertainty = emit(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-6),#{length_unit},"
        f"'distance accuracy','')"
    )
    context = emit_block(
        "(",
        [
            "GEOMETRIC_REPRESENTATION_CONTEXT(3)",
            f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty}))",
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit},#{angle_unit},#{solid_unit}))",
            "REPRESENTATION_CONTEXT('Context 1','3D')",
            ");",
        ],
    )

    point_eid = {}
    vertex_eid = {}
    for key in keys_in_order:
        point_eid[key] = emit(f"CARTESIAN_POINT('',({key[0]},{key[1]},{key[2]}))")
    for key in keys_in_order:
        vertex_eid[key] = emit(f"VERTEX_POINT('',#{point_eid[key]})")

    edge_eid = {}
    for tri in triangles:
        keys = [_ptkey(p) for p in tri]
        for i in range(3):
            ka, kb = keys[i], keys[(i + 1) % 3]
            canon = (ka, kb) if ka <= kb else (kb, ka)
            if canon in edge_eid:
                continue
            pa, pb = _coords(canon[0]), _coords(canon[1])
            delta = _sub(pb, pa)
            length = _len(delta)
            if length < _EPS:
                continue
            direction = _norm(delta)
            dir_id = emit(
                f"DIRECTION('',({_fmt(direction[0])},{_fmt(direction[1])},{_fmt(direction[2])}))"
            )
            vec_id = emit(f"VECTOR('',#{dir_id},{_fmt(length)})")
            line_id = emit(f"LINE('',#{point_eid[canon[0]]},#{vec_id})")
            edge_eid[canon] = emit(
                f"EDGE_CURVE('',#{vertex_eid[canon[0]]},#{vertex_eid[canon[1]]},#{line_id},.T.)"
            )

    face_ids = []
    for a, b, c in triangles:
        keys = [_ptkey(a), _ptkey(b), _ptkey(c)]
        ab = _sub(b, a)
        ac = _sub(c, a)
        normal = _norm(_cross(ab, ac))
        xdir = _norm(ab)
        if _len(xdir) < _EPS or _len(normal) < _EPS:
            continue
        oe_ids = []
        valid = True
        for i in range(3):
            ka, kb = keys[i], keys[(i + 1) % 3]
            canon = (ka, kb) if ka <= kb else (kb, ka)
            edge = edge_eid.get(canon)
            if edge is None:
                valid = False
                break
            sense = ".T." if (ka, kb) == canon else ".F."
            oe_ids.append(emit(f"ORIENTED_EDGE('',*,*,#{edge},{sense})"))
        if not valid:
            continue
        loop = emit(f"EDGE_LOOP('',({_ref_list(oe_ids)}))")
        bound = emit(f"FACE_OUTER_BOUND('',#{loop},.T.)")
        axis_dir = emit(
            f"DIRECTION('',({_fmt(normal[0])},{_fmt(normal[1])},{_fmt(normal[2])}))"
        )
        ref_dir = emit(f"DIRECTION('',({_fmt(xdir[0])},{_fmt(xdir[1])},{_fmt(xdir[2])}))")
        placement = emit(
            f"AXIS2_PLACEMENT_3D('',#{point_eid[keys[0]]},#{axis_dir},#{ref_dir})"
        )
        plane = emit(f"PLANE('',#{placement})")
        face_ids.append(emit(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)"))

    if not face_ids:
        raise ValueError("no planar faces produced")
    shell = emit(f"CLOSED_SHELL('',({_ref_list(face_ids)}))")
    solid = emit(f"MANIFOLD_SOLID_BREP('envelope',#{shell})")
    origin0 = emit("CARTESIAN_POINT('',(0.0000,0.0000,0.0000))")
    axis_z = emit("DIRECTION('',(0.0000,0.0000,1.0000))")
    axis_x = emit("DIRECTION('',(1.0000,0.0000,0.0000))")
    abs_placement = emit(f"AXIS2_PLACEMENT_3D('',#{origin0},#{axis_z},#{axis_x})")
    representation = emit(
        f"ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{abs_placement},#{solid}),#{context})"
    )
    emit(f"SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})")
    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")

    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("\n".join(header + lines) + "\n")
    return path


def write_revolution_step(path, part_number, stations, description="low-fidelity envelope"):
    """Write a catalog envelope by revolving ``(x, radius)`` stations about +X."""
    try:
        _ocp_write_shape(_ocp_revolution_solid(stations), path, part_number)
        return path
    except ImportError:
        return write_step_file(
            path, part_number, revolution_triangles(stations), description
        )


def write_prism_segments_step(path, part_number, segments, description="low-fidelity envelope"):
    """Fuse YZ polygons extruded along +X.

    Each segment is ``(x0_mm, x1_mm, [(y_mm, z_mm), ...])``. Profiles are
    closed automatically. Used for D-sub / Micro-D shells and flanges.
    """
    try:
        _ocp_write_shape(_ocp_prism_segments_solid(segments), path, part_number)
        return path
    except ImportError:
        return write_step_file(
            path, part_number, prism_segments_triangles(segments), description
        )


def write_elbow_step(
    path,
    part_number,
    entry,
    corner,
    angle_deg,
    exit_length,
    r_entry,
    r_body,
    r_nut,
    nut_length,
    description="low-fidelity envelope",
    n_arc=16,
):
    """Write a banding-backshell elbow: platform, sharp mitered body, coupling nut.

    Incoming centerline is +X. Each body cylinder is clipped to the planar
    miter through ``corner`` (axis-bisector plane) so the joint is one ellipse.
    """
    layout = _elbow_layout(entry, corner, angle_deg, exit_length, nut_length)
    try:
        _ocp_write_shape(
            _ocp_elbow_solid(entry, r_entry, r_body, r_nut, nut_length, layout),
            path,
            part_number,
        )
        return path
    except ImportError:
        points, radii = _elbow_sweep_stations(
            entry, r_entry, r_body, r_nut, nut_length, layout
        )
        return write_step_file(
            path, part_number, sweep_triangles(points, radii), description
        )


INCH_TO_MM = 25.4


def read_step_shape(path):
    """
    Read a STEP file into an OpenCascade shape.

    **Returns:**
    - The transferred shape, or ``None`` if the file is missing or cannot be read.
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
    except ImportError:
        return None

    reader = STEPControl_Reader()
    with _silence_stdio():
        if reader.ReadFile(path) != IFSelect_RetDone:
            return None
        reader.TransferRoots()
    shape = reader.OneShape()
    if shape is None or shape.IsNull():
        return None
    return shape


def shape_vertices(shape):
    """Cartesian vertices of an OpenCascade shape, in the shape's units."""
    if shape is None:
        return []
    try:
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
    except ImportError:
        return []
    point_of = getattr(BRep_Tool, "Pnt_s", None) or getattr(BRep_Tool, "Pnt", None)
    vertex_of = getattr(TopoDS, "Vertex_s", None) or getattr(TopoDS, "Vertex", None)
    if point_of is None:
        return []
    points = []
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    while explorer.More():
        try:
            current = explorer.Current()
            vertex = vertex_of(current) if vertex_of else current
            pnt = point_of(vertex)
            points.append((pnt.X(), pnt.Y(), pnt.Z()))
        except Exception:
            pass
        explorer.Next()
    return points


def _ocp_iter_solids(shape):
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    found = False
    while explorer.More():
        found = True
        yield TopoDS.Solid_s(explorer.Current())
        explorer.Next()
    if not found:
        yield shape


def _ocp_face_triangulation(face):
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    location = TopLoc_Location()
    triangulation = None
    if hasattr(BRep_Tool, "Triangulation_s"):
        triangulation = BRep_Tool.Triangulation_s(face, location)
    elif hasattr(BRep_Tool, "Triangulation"):
        triangulation = BRep_Tool.Triangulation(face, location)
    return triangulation, location


def tessellate_shape(shape, deflection_mm=0.5, name=None):
    """
    Mesh an OpenCascade shape for the console viewer.

    **Returns:** list of ``{"name", "vertices", "indices"}`` in millimetres.
    ``vertices`` is a flat xyz array. ``indices`` is a flat triangle index array.
    Each solid is named ``{name}-bodyN`` (or ``bodyN`` if ``name`` is blank).
    """
    if shape is None:
        return []
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(shape, float(deflection_mm), False, 0.5, True)
    bodies = []
    for solid_index, solid in enumerate(_ocp_iter_solids(shape), start=1):
        vertices = []
        indices = []
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face_s(explorer.Current())
            triangulation, location = _ocp_face_triangulation(face)
            explorer.Next()
            if triangulation is None:
                continue
            try:
                if triangulation.IsNull():
                    continue
            except Exception:
                pass
            transform = location.Transformation()
            offset = len(vertices) // 3
            node_count = triangulation.NbNodes()
            for i in range(1, node_count + 1):
                point = triangulation.Node(i)
                if not location.IsIdentity():
                    point = point.Transformed(transform)
                vertices.extend((point.X(), point.Y(), point.Z()))
            reversed_face = False
            try:
                reversed_face = face.Orientation() == TopAbs_REVERSED
            except Exception:
                pass
            for i in range(1, triangulation.NbTriangles() + 1):
                triangle = triangulation.Triangle(i)
                try:
                    n1, n2, n3 = triangle.Get()
                except Exception:
                    n1 = triangle.Value(1)
                    n2 = triangle.Value(2)
                    n3 = triangle.Value(3)
                if reversed_face:
                    n1, n2, n3 = n1, n3, n2
                indices.extend((offset + n1 - 1, offset + n2 - 1, offset + n3 - 1))
        if not indices:
            continue
        bodies.append(
            {
                "name": _tessellated_body_name(name, solid_index),
                "vertices": vertices,
                "indices": indices,
            }
        )
    return bodies


def _tessellated_body_name(part_name, solid_index):
    part_name = str(part_name or "").strip()
    if part_name:
        return f"{part_name}-body{solid_index}"
    return f"body{solid_index}"


def _xcaf_label_name(label):
    from OCP.TCollection import TCollection_AsciiString
    from OCP.TDataStd import TDataStd_Name

    attr = TDataStd_Name()
    if not label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return ""
    ext = attr.Get()
    try:
        text = ext.ToExtString()
    except Exception:
        text = TCollection_AsciiString(ext).ToCString()
    return str(text or "").strip()


def _read_named_step_shapes(path):
    """Read a STEP assembly as ``[(name, shape), ...]`` via XCAF names.

    Falls back to ``None`` if XCAF is unavailable or the file has no named
    free shapes. ``name`` is the instance / segment label written by
    ``write_assembly_step``.
    """
    try:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDF import TDF_LabelSequence
        from OCP.TDocStd import TDocStd_Document
        from OCP.XCAFApp import XCAFApp_Application
        from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    except ImportError:
        return None

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    named = []
    try:
        with _silence_stdio():
            if reader.ReadFile(path) != IFSelect_RetDone:
                return None
            if not reader.Transfer(doc):
                return None
        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)

        def walk(label):
            if XCAFDoc_ShapeTool.IsAssembly_s(label):
                children = TDF_LabelSequence()
                XCAFDoc_ShapeTool.GetComponents_s(label, children)
                for index in range(1, children.Length() + 1):
                    walk(children.Value(index))
                return
            shape = XCAFDoc_ShapeTool.GetShape_s(label)
            if shape is None or shape.IsNull():
                return
            named.append((_xcaf_label_name(label) or "body", shape))

        for index in range(1, labels.Length() + 1):
            walk(labels.Value(index))
    finally:
        try:
            app.Close(doc)
        except Exception:
            pass
    return named or None


def tessellate_step_file(path, deflection_mm=0.5):
    """Read a STEP file and mesh it. Returns the same structure as ``tessellate_shape``.

    Assembly labels become ``{instance_name}-bodyN`` so a click can name the
    instance and still distinguish multiple solids in one library part.
    """
    failure = ocp_import_error()
    if failure is not None:
        raise ImportError(ocp_unavailable_message(failure)) from failure
    named = _read_named_step_shapes(path)
    if named:
        bodies = []
        for name, shape in named:
            bodies.extend(tessellate_shape(shape, deflection_mm, name=name))
        if bodies:
            return bodies
    shape = read_step_shape(path)
    if shape is None:
        raise ValueError(f"could not read STEP file: {path}")
    return tessellate_shape(shape, deflection_mm)


def pose_trsf(x, y, z, alpha=0.0, beta=0.0, gamma=0.0):
    """Rigid transform for a ZYX Euler pose. Translation uses the shape's units.

    ``alpha`` is about X, ``beta`` about Y, ``gamma`` about Z
    (``R = Rx(alpha) · Ry(beta) · Rz(gamma)``).
    """
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    origin = gp_Pnt(0.0, 0.0, 0.0)
    rx = gp_Trsf()
    ry = gp_Trsf()
    rz = gp_Trsf()
    translate = gp_Trsf()
    rx.SetRotation(gp_Ax1(origin, gp_Dir(1.0, 0.0, 0.0)), math.radians(float(alpha)))
    ry.SetRotation(gp_Ax1(origin, gp_Dir(0.0, 1.0, 0.0)), math.radians(float(beta)))
    rz.SetRotation(gp_Ax1(origin, gp_Dir(0.0, 0.0, 1.0)), math.radians(float(gamma)))
    translate.SetTranslation(gp_Vec(float(x), float(y), float(z)))
    return translate * rx * ry * rz


def transform_shape(shape, x, y, z, alpha=0.0, beta=0.0, gamma=0.0):
    """Apply a ZYX Euler pose (degrees) and translation (same units as the shape).

    ``alpha`` is about X, ``beta`` about Y, ``gamma`` about Z, matching the
    console node triad and ``bundle_network_utils.adjacent_nodes``
    (``R = Rx(alpha) · Ry(beta) · Rz(gamma)``).
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    combined = pose_trsf(x, y, z, alpha, beta, gamma)
    return BRepBuilderAPI_Transform(shape, combined, True).Shape()


def write_assembly_step(path, part_number, bodies, description="harness assembly"):
    """
    Write one STEP file containing every named body.

    Each body is a dict with ``name`` and either ``triangles`` (outward-wound
    millimetre triangles) or ``shape`` (an OpenCascade shape).

    Prefers OpenCascade. Without it, only triangle bodies are written.
    """
    if not bodies:
        raise ValueError("no bodies to write")

    ocp_failure = None
    try:
        named_shapes = []
        for body in bodies:
            name = body.get("name") or "body"
            shape = body.get("shape")
            if shape is None:
                triangles = body.get("triangles") or []
                if not triangles:
                    continue
                shape = _ocp_solid_from_triangles(triangles)
            named_shapes.append((name, shape))
        if not named_shapes:
            raise ValueError("no bodies to write")
        _ocp_write_shapes(named_shapes, path, part_number)
        return path
    except ImportError as exc:
        ocp_failure = exc

    named_triangles = []
    for body in bodies:
        triangles = body.get("triangles") or []
        if not triangles:
            continue
        named_triangles.append((body.get("name") or "body", triangles))
    if not named_triangles:
        if ocp_failure is not None:
            raise ValueError(ocp_unavailable_message(ocp_failure)) from ocp_failure
        raise ValueError("no triangle bodies to write without OpenCascade")
    return write_step_file_solids(path, part_number, named_triangles, description)


def write_step_file_solids(path, part_number, named_triangles, description="harness assembly"):
    """Write several triangle solids into one AP214 STEP file."""
    if not named_triangles:
        raise ValueError("no triangles to write")

    try:
        named_shapes = [
            (name, _ocp_solid_from_triangles(triangles))
            for name, triangles in named_triangles
        ]
        _ocp_write_shapes(named_shapes, path, part_number)
        return path
    except ImportError:
        pass

    lines = []
    eid = 0

    def next_id():
        nonlocal eid
        eid += 1
        return eid

    def emit(entity):
        i = next_id()
        lines.append(f"#{i}={entity};")
        return i

    def emit_block(first_line, body_lines):
        i = next_id()
        lines.append(f"#{i}={first_line}")
        lines.extend(body_lines)
        return i

    header = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('Harnice harness assembly'),'2;1');",
        (
            f"FILE_NAME('{_step_string(part_number)}.step','{_STEP_TIMESTAMP}',"
            f"('Harnice'),('Harnice'),'Harnice','','');"
        ),
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
    ]

    app_ctx = emit(
        "APPLICATION_CONTEXT('core data for automotive mechanical design processes')"
    )
    emit(
        f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
        f"'automotive_design',2000,#{app_ctx})"
    )
    prod_ctx = emit(f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')")
    def_ctx = emit(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')")
    product = emit(
        f"PRODUCT('{_step_string(part_number)}','{_step_string(part_number)}',"
        f"'{_step_string(description)}',(#{prod_ctx}))"
    )
    formation = emit(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
    definition = emit(f"PRODUCT_DEFINITION('design','',#{formation},#{def_ctx})")
    shape = emit(f"PRODUCT_DEFINITION_SHAPE('','',#{definition})")
    emit(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{product}))")

    length_unit = emit_block(
        "(",
        [
            "LENGTH_UNIT()",
            "NAMED_UNIT(*)",
            "SI_UNIT(.MILLI.,.METRE.)",
            ");",
        ],
    )
    angle_unit = emit_block(
        "(",
        [
            "NAMED_UNIT(*)",
            "PLANE_ANGLE_UNIT()",
            "SI_UNIT($,.RADIAN.)",
            ");",
        ],
    )
    solid_unit = emit_block(
        "(",
        [
            "NAMED_UNIT(*)",
            "SI_UNIT($,.STERADIAN.)",
            "SOLID_ANGLE_UNIT()",
            ");",
        ],
    )
    uncertainty = emit(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-6),#{length_unit},"
        f"'distance accuracy','')"
    )
    context = emit_block(
        "(",
        [
            "GEOMETRIC_REPRESENTATION_CONTEXT(3)",
            f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty}))",
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit},#{angle_unit},#{solid_unit}))",
            "REPRESENTATION_CONTEXT('Context 1','3D')",
            ");",
        ],
    )

    solid_ids = []
    for name, triangles in named_triangles:
        if not triangles:
            continue
        keys_in_order = []
        seen = set()
        for tri in triangles:
            for point in tri:
                key = _ptkey(point)
                if key in seen:
                    continue
                seen.add(key)
                keys_in_order.append(key)

        point_eid = {}
        vertex_eid = {}
        for key in keys_in_order:
            point_eid[key] = emit(f"CARTESIAN_POINT('',({key[0]},{key[1]},{key[2]}))")
        for key in keys_in_order:
            vertex_eid[key] = emit(f"VERTEX_POINT('',#{point_eid[key]})")

        edge_eid = {}
        for tri in triangles:
            keys = [_ptkey(p) for p in tri]
            for i in range(3):
                ka, kb = keys[i], keys[(i + 1) % 3]
                canon = (ka, kb) if ka <= kb else (kb, ka)
                if canon in edge_eid:
                    continue
                pa, pb = _coords(canon[0]), _coords(canon[1])
                delta = _sub(pb, pa)
                length = _len(delta)
                if length < _EPS:
                    continue
                direction = _norm(delta)
                dir_id = emit(
                    f"DIRECTION('',({_fmt(direction[0])},{_fmt(direction[1])},{_fmt(direction[2])}))"
                )
                vec_id = emit(f"VECTOR('',#{dir_id},{_fmt(length)})")
                line_id = emit(f"LINE('',#{point_eid[canon[0]]},#{vec_id})")
                edge_eid[canon] = emit(
                    f"EDGE_CURVE('',#{vertex_eid[canon[0]]},#{vertex_eid[canon[1]]},#{line_id},.T.)"
                )

        face_ids = []
        for a, b, c in triangles:
            keys = [_ptkey(a), _ptkey(b), _ptkey(c)]
            ab = _sub(b, a)
            ac = _sub(c, a)
            normal = _norm(_cross(ab, ac))
            xdir = _norm(ab)
            if _len(xdir) < _EPS or _len(normal) < _EPS:
                continue
            oe_ids = []
            valid = True
            for i in range(3):
                ka, kb = keys[i], keys[(i + 1) % 3]
                canon = (ka, kb) if ka <= kb else (kb, ka)
                edge = edge_eid.get(canon)
                if edge is None:
                    valid = False
                    break
                sense = ".T." if (ka, kb) == canon else ".F."
                oe_ids.append(emit(f"ORIENTED_EDGE('',*,*,#{edge},{sense})"))
            if not valid:
                continue
            loop = emit(f"EDGE_LOOP('',({_ref_list(oe_ids)}))")
            bound = emit(f"FACE_OUTER_BOUND('',#{loop},.T.)")
            axis_dir = emit(
                f"DIRECTION('',({_fmt(normal[0])},{_fmt(normal[1])},{_fmt(normal[2])}))"
            )
            ref_dir = emit(
                f"DIRECTION('',({_fmt(xdir[0])},{_fmt(xdir[1])},{_fmt(xdir[2])}))"
            )
            placement = emit(
                f"AXIS2_PLACEMENT_3D('',#{point_eid[keys[0]]},#{axis_dir},#{ref_dir})"
            )
            plane = emit(f"PLANE('',#{placement})")
            face_ids.append(emit(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)"))

        if not face_ids:
            continue
        shell = emit(f"CLOSED_SHELL('',({_ref_list(face_ids)}))")
        solid_ids.append(emit(f"MANIFOLD_SOLID_BREP('{_step_string(name)}',#{shell})"))

    if not solid_ids:
        raise ValueError("no planar faces produced")
    origin0 = emit("CARTESIAN_POINT('',(0.0000,0.0000,0.0000))")
    axis_z = emit("DIRECTION('',(0.0000,0.0000,1.0000))")
    axis_x = emit("DIRECTION('',(1.0000,0.0000,0.0000))")
    abs_placement = emit(f"AXIS2_PLACEMENT_3D('',#{origin0},#{axis_z},#{axis_x})")
    items = [abs_placement] + solid_ids
    representation = emit(
        f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({_ref_list(items)}),#{context})"
    )
    emit(f"SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})")
    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")

    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("\n".join(header + lines) + "\n")
    return path


def _ocp_write_shapes(named_shapes, path, part_number):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for name, shape in named_shapes:
        label = shape_tool.AddShape(shape, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(str(name)))
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    with _silence_stdio():
        if not writer.Transfer(doc):
            raise RuntimeError("STEPCAFControl_Writer.Transfer failed")
        status = writer.Write(path)
    try:
        app.Close(doc)
    except Exception:
        pass
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEPCAFControl_Writer.Write failed: {status}")
    return path


def _elbow_layout(entry, corner, angle_deg, exit_length, nut_length):
    angle = math.radians(angle_deg)
    ux, uy = math.cos(angle), math.sin(angle)
    p_face = (
        float(corner[0]) + float(exit_length) * ux,
        float(corner[1]) + float(exit_length) * uy,
        0.0,
    )
    p_nut = (
        p_face[0] - float(nut_length) * ux,
        p_face[1] - float(nut_length) * uy,
        0.0,
    )
    return {
        "angle": angle,
        "ux": ux,
        "uy": uy,
        "corner": (float(corner[0]), float(corner[1]), 0.0),
        "p_face": p_face,
        "p_nut": p_nut,
        "exit_length": float(exit_length),
    }


def _elbow_sweep_stations(entry, r_entry, r_body, r_nut, nut_length, layout):
    ux, uy = layout["ux"], layout["uy"]
    corner, p_nut, p_face = layout["corner"], layout["p_nut"], layout["p_face"]
    step = 0.4
    return (
        [
            tuple(entry),
            (0.0, 0.0, 0.0),
            (step, 0.0, 0.0),
            corner,
            p_nut,
            (p_nut[0] + step * ux, p_nut[1] + step * uy, 0.0),
            p_face,
        ],
        [r_entry, r_entry, r_body, r_body, r_body, r_nut, r_nut],
    )


def _ocp_cylinder(origin, direction, radius, height):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction)), radius, height
    ).Shape()


def _ocp_fuse(a, b, fuzzy=0.05):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

    op = BRepAlgoAPI_Fuse(a, b)
    op.SetFuzzyValue(fuzzy)
    op.Build()
    if not op.IsDone() or op.Shape().IsNull():
        raise RuntimeError("OpenCascade boolean fuse failed")
    return op.Shape()


def _ocp_clip_halfspace(shape, plane_point, plane_normal, keep_point, fuzzy=0.02):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    face = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(*plane_point), gp_Dir(*plane_normal))
    ).Face()
    half = BRepPrimAPI_MakeHalfSpace(face, gp_Pnt(*keep_point)).Solid()
    op = BRepAlgoAPI_Common(shape, half)
    op.SetFuzzyValue(fuzzy)
    op.Build()
    if not op.IsDone() or op.Shape().IsNull():
        raise RuntimeError("OpenCascade miter clip failed")
    return op.Shape()


def _ocp_elbow_solid(entry, r_entry, r_body, r_nut, nut_length, layout):
    ux, uy = layout["ux"], layout["uy"]
    corner = layout["corner"]
    extra = max(r_body * 2.0, 4.0)
    platform_len = max(0.2, -float(entry[0]))
    # Miter plane through the corner, normal along the axis bisector.
    bx, by = 1.0 + ux, uy
    blen = math.hypot(bx, by)
    bx, by = bx / blen, by / blen

    incoming = _ocp_cylinder((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), r_body, corner[0] + extra)
    outgoing = _ocp_cylinder(
        (corner[0] - extra * ux, corner[1] - extra * uy, 0.0),
        (ux, uy, 0.0),
        r_body,
        layout["exit_length"] + extra,
    )
    incoming = _ocp_clip_halfspace(
        incoming, corner, (bx, by, 0.0), (corner[0] - 1.0, 0.0, 0.0)
    )
    outgoing = _ocp_clip_halfspace(
        outgoing, corner, (bx, by, 0.0), (corner[0] + ux, corner[1] + uy, 0.0)
    )
    body = _ocp_fuse(incoming, outgoing, fuzzy=0.02)
    platform = _ocp_cylinder(entry, (1.0, 0.0, 0.0), r_entry, platform_len + 1.0)
    nut = _ocp_cylinder(layout["p_nut"], (ux, uy, 0.0), r_nut, nut_length)
    return _ocp_fuse(_ocp_fuse(body, platform), nut)


def _ocp_write_shape(shape, path, part_number):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    label = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()).AddShape(shape, False)
    TDataStd_Name.Set_s(label, TCollection_ExtendedString(str(part_number)))
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    with _silence_stdio():
        if not writer.Transfer(doc):
            raise RuntimeError("STEPCAFControl_Writer.Transfer failed")
        status = writer.Write(path)
    try:
        app.Close(doc)
    except Exception:
        pass
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEPCAFControl_Writer.Write failed: {status}")
    return path


def _ocp_revolution_solid(stations):
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    cleaned = []
    for x, radius in stations:
        if radius <= 0:
            raise ValueError("revolution radius must be positive")
        point = (float(x), float(radius))
        if cleaned and abs(point[0] - cleaned[-1][0]) < _EPS and abs(point[1] - cleaned[-1][1]) < _EPS:
            continue
        cleaned.append(point)
    if len(cleaned) < 2:
        raise ValueError("need at least two revolution stations")

    x0, _r0 = cleaned[0]
    x1, _r1 = cleaned[-1]
    profile = [(x0, 0.0)] + cleaned + [(x1, 0.0)]
    wire = BRepBuilderAPI_MakeWire()
    for (xa, ra), (xb, rb) in zip(profile, profile[1:]):
        if abs(xa - xb) < _EPS and abs(ra - rb) < _EPS:
            continue
        wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(xa, ra, 0.0), gp_Pnt(xb, rb, 0.0)).Edge())
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0))).Shape()


def _ocp_prism_segments_solid(segments):
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    solid = None
    for x0, x1, yz in segments:
        if abs(x1 - x0) < _EPS:
            continue
        xa, xb = (x0, x1) if x1 > x0 else (x1, x0)
        ring = _closed_yz(yz)
        wire = BRepBuilderAPI_MakeWire()
        pts = [(xa, y, z) for y, z in ring]
        pts.append(pts[0])
        for a, b in zip(pts, pts[1:]):
            if abs(a[1] - b[1]) < _EPS and abs(a[2] - b[2]) < _EPS:
                continue
            wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())
        face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
        prism = BRepPrimAPI_MakePrism(face, gp_Vec(xb - xa, 0.0, 0.0)).Shape()
        solid = prism if solid is None else _ocp_fuse(solid, prism)
    if solid is None:
        raise ValueError("prism segments produced no volume")
    return solid


def _ocp_solid_from_triangles(triangles):
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_Sewing,
    )
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopoDS import TopoDS

    sewing = BRepBuilderAPI_Sewing()
    for a, b, c in triangles:
        poly = BRepBuilderAPI_MakePolygon()
        poly.Add(gp_Pnt(a[0], a[1], a[2]))
        poly.Add(gp_Pnt(b[0], b[1], b[2]))
        poly.Add(gp_Pnt(c[0], c[1], c[2]))
        poly.Close()
        sewing.Add(BRepBuilderAPI_MakeFace(poly.Wire()).Face())
    sewing.Perform()
    sewn = sewing.SewedShape()
    if sewn.IsNull():
        raise ValueError("OpenCascade sewing produced an empty shape")
    if sewn.ShapeType() == TopAbs_SOLID:
        return sewn
    if sewn.ShapeType() == TopAbs_SHELL:
        maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(sewn))
        if not maker.IsDone():
            raise ValueError("OpenCascade could not make a solid from the sewn shell")
        return maker.Solid()
    raise ValueError(f"unexpected sewn shape type {sewn.ShapeType()}")


def _step_string(text):
    return str(text).replace("'", "''")
