import csv
import json
import math
import os
import random
import re
import xml.etree.ElementTree as ET
from collections import deque

from harnice import fileio
from harnice.lists import instances_list
from harnice.utils.bundle_network_utils import (
    _as_dict,
    _csys_chain,
    _csys_child_of,
    _point3,
)

COLUMNS = [
    "segment_id",  # id of the 3D segment this row flattens
    "node_at_end_a",  # node id at end A after derive; A is the left end, or the upper end when the segment is vertical
    "node_at_end_b",  # node id at end B
    "length",  # arc length of the 3D curve, recomputed on every derive
    "length_tolerance",  # kept from the previous row with this segment_id; not edited on the 2D page
    "angle",  # heading in degrees from end A to the first bend; 0 is +X and console Y points down
    "angle_constraint",  # match name for that first heading; blank means the heading is independent
    "subdivisions",  # JSON list of {percent, angle, constraint}; percent is in (0, 100) where the next heading starts
]


def spline_points(segment: dict, steps: int = 32) -> list[tuple[float, float, float]]:
    """
    Sample the segment centerline in the network's coordinate units.

    - If ``spline_control_points`` is empty: ``[end_a, end_b]``.
    - Otherwise: a degree-(N-1) Bezier through ``[end_a, *control_points, end_b]``,
      sampled at ``steps`` intervals (endpoints included).

    The 3D page stores each control point as an offset from end A, and adds
    end A when it draws. This sampler places each stored triple in that
    polygon as written, in the same coordinate space as the two ends.
    """

    def control_polygon():
        a = _point3(segment["location_at_end_a"])
        b = _point3(segment["location_at_end_b"])
        control_points = [
            _point3(point) for point in (segment.get("spline_control_points") or [])
        ]
        return [a, *control_points, b]

    def bezier_point(pts, t):
        n = len(pts) - 1
        coeffs = []
        for i in range(n + 1):
            result = 1
            for j in range(i):
                result = result * (n - j) // (j + 1)
            coeffs.append(result)
        point = [0.0, 0.0, 0.0]
        for i, p in enumerate(pts):
            w = coeffs[i] * ((1 - t) ** (n - i)) * (t**i)
            for d in range(3):
                point[d] += w * p[d]
        return (point[0], point[1], point[2])

    pts = control_polygon()
    if len(pts) == 2:
        return pts
    if steps < 1:
        raise ValueError("spline_points needs at least 1 step")
    return [bezier_point(pts, i / steps) for i in range(steps + 1)]


def oriented_spline_points(segment, start_location=None, direction="ab", steps=32):
    """
    Sample a chosen-network segment so the polyline leaves ``start_location``.

    Hop directions are ``ab`` / ``ba`` on the segment instance. Flattening may
    swap that instance's end A and end B so the 2D layout reads left to right,
    while ``location_at_end_a`` / ``location_at_end_b`` stay in solver order.
    Pass the 3D location of the node this hop leaves. The sample is reversed
    when its first point is not that location. With no start location, ``ba``
    reverses the stored geometry.
    """
    pts = list(spline_points(segment, steps=steps))
    if len(pts) < 2:
        return pts
    if start_location not in ("", None):
        start = _point3(start_location)
        if not (
            abs(pts[0][0] - start[0]) <= 1e-6
            and abs(pts[0][1] - start[1]) <= 1e-6
            and abs(pts[0][2] - start[2]) <= 1e-6
        ):
            pts.reverse()
        return pts
    if direction == "ba":
        pts.reverse()
    return pts


def parse_subdivisions(value):
    """
    Interior stations along a flattened segment, ordered from end A.

    Each station is ``{"percent", "angle", "constraint"}``. ``percent`` is where
    that station's heading takes over, in ``(0, 100)`` of the segment length.
    The stretch from A to the first station uses the row's ``angle``. An empty
    value means the segment is one straight stretch.
    """

    def norm_angle_deg(angle):
        if angle in ("", None):
            return 0.0
        try:
            n = float(angle)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(n):
            return 0.0
        return ((n % 360.0) + 360.0) % 360.0

    if value in ("", None):
        return []
    raw = value
    if not isinstance(value, list):
        try:
            raw = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(raw, list):
        return []
    parsed = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            percent = float(item.get("percent"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(percent) or percent <= 0.0 or percent >= 100.0:
            continue
        key = round(percent, 6)
        if key in seen:
            continue
        seen.add(key)
        parsed.append(
            {
                "percent": key,
                "angle": norm_angle_deg(item.get("angle")),
                "constraint": (item.get("constraint") or "").strip(),
            }
        )
    parsed.sort(key=lambda station: station["percent"])
    return parsed


def encode_subdivisions(stations):
    """JSON cell for ``subdivisions``. Empty when the segment is straight."""

    def norm_angle_deg(angle):
        if angle in ("", None):
            return 0.0
        try:
            n = float(angle)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(n):
            return 0.0
        return ((n % 360.0) + 360.0) % 360.0

    if not stations:
        return ""
    payload = [
        {
            "percent": round(float(station["percent"]), 6),
            "angle": round(norm_angle_deg(station.get("angle")), 6),
            "constraint": (station.get("constraint") or "").strip(),
        }
        for station in stations
    ]
    return json.dumps(payload, separators=(",", ":"))


def spans_of(row):
    """
    Straight stretches from A to B.

    Each span is ``{"fraction", "angle", "constraint"}``. Fractions sum to 1.
    Span 0 is the row's ``angle``; each later span starts at a subdivision.
    """

    def norm_angle_deg(angle):
        if angle in ("", None):
            return 0.0
        try:
            n = float(angle)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(n):
            return 0.0
        return ((n % 360.0) + 360.0) % 360.0

    stations = parse_subdivisions(row.get("subdivisions"))
    cuts = [0.0] + [station["percent"] for station in stations] + [100.0]
    angles = [norm_angle_deg(row.get("angle"))] + [
        station["angle"] for station in stations
    ]
    constraints = [(row.get("angle_constraint") or "").strip()] + [
        station["constraint"] for station in stations
    ]
    return [
        {
            "fraction": (cuts[i + 1] - cuts[i]) / 100.0,
            "angle": angles[i],
            "constraint": constraints[i],
        }
        for i in range(len(angles))
    ]


def write_spans(row, spans):
    """Write spans back onto ``angle``, ``angle_constraint``, and ``subdivisions``."""

    def norm_angle_deg(angle):
        if angle in ("", None):
            return 0.0
        try:
            n = float(angle)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(n):
            return 0.0
        return ((n % 360.0) + 360.0) % 360.0

    if not spans:
        return row
    row["angle"] = round(norm_angle_deg(spans[0]["angle"]), 6)
    row["angle_constraint"] = (spans[0]["constraint"] or "").strip()
    stations = []
    covered = 0.0
    for index, span in enumerate(spans[:-1]):
        covered += span["fraction"] * 100.0
        nxt = spans[index + 1]
        stations.append(
            {
                "percent": round(covered, 6),
                "angle": round(norm_angle_deg(nxt["angle"]), 6),
                "constraint": (nxt["constraint"] or "").strip(),
            }
        )
    row["subdivisions"] = encode_subdivisions(stations)
    return row


def reverse_spans(row):
    """
    Walk the segment from B back to A.

    Each heading gains 180° and each constraint stays on the same stretch.
    Does not swap the endpoint node ids.
    """
    spans = spans_of(row)
    reversed_spans = [
        {
            "fraction": span["fraction"],
            "angle": (span["angle"] + 180.0) % 360.0,
            "constraint": span["constraint"],
        }
        for span in reversed(spans)
    ]
    return write_spans(row, reversed_spans)


def enforce_angle_constraints(rows):
    """
    Give every span that shares a constraint key the first member's angle.

    Keys are compared across the segment ``angle_constraint`` and every
    subdivision ``constraint``. A blank key is independent. Mutates ``rows``.
    """
    group_angle = {}
    snapshots = []
    for row in rows:
        spans = spans_of(row)
        snapshots.append(spans)
        for span in spans:
            key = span["constraint"]
            if key and key not in group_angle:
                group_angle[key] = span["angle"]
    for row, spans in zip(rows, snapshots):
        changed = False
        for span in spans:
            key = span["constraint"]
            if not key:
                continue
            target = group_angle[key]
            if abs(span["angle"] - target) > 1e-6:
                span["angle"] = target
                changed = True
        if changed:
            write_spans(row, spans)
    return rows


def layout_delta(row, scale=1.0, y_down=False):
    """
    Displacement from end A to end B along the subdivided path.

    ``scale`` multiplies length (the console layout uses 20 px per model unit).
    ``y_down`` negates the Y component for SVG.
    """
    try:
        length = float(row.get("length"))
    except (TypeError, ValueError):
        length = 50.0
    if not math.isfinite(length):
        length = 50.0
    dx = 0.0
    dy = 0.0
    for span in spans_of(row):
        dist = length * span["fraction"] * scale
        rad = math.radians(span["angle"])
        dx += dist * math.cos(rad)
        sy = dist * math.sin(rad)
        dy += -sy if y_down else sy
    return dx, dy


def polyline_points(x, y, row, scale=1.0, y_down=False):
    """Vertices of the segment centerline, including both ends, from ``(x, y)``."""
    try:
        length = float(row.get("length"))
    except (TypeError, ValueError):
        length = 50.0
    if not math.isfinite(length):
        length = 50.0
    points = [(x, y)]
    cx, cy = x, y
    for span in spans_of(row):
        dist = length * span["fraction"] * scale
        rad = math.radians(span["angle"])
        cx += dist * math.cos(rad)
        sy = dist * math.sin(rad)
        cy += -sy if y_down else sy
        points.append((cx, cy))
    return points


def canonicalize_segment_endpoints_for_save(rows):
    """
    Orient each flattened segment so end A is left of, or vertically above, end B.

    Same rule as block-diagram ``canonicalizeHarnessSegmentEndpointsForSave``:
    in the 2D layout (SVG Y-down), swap ``node_at_end_a`` / ``node_at_end_b`` and
    reverse the spans (each heading +180°) when the first-span angle is in
    ``[90, 270)``. Constraint keys stay on the stretch they belong to, then
    members of a key are set back to one shared angle. Mutates ``rows`` in
    place and returns them.
    """

    def norm_angle_deg(angle):
        if angle in ("", None):
            return 0.0
        try:
            n = float(angle)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(n):
            return 0.0
        return ((n % 360.0) + 360.0) % 360.0

    enforce_angle_constraints(rows)
    for row in rows:
        ang = norm_angle_deg(row.get("angle"))
        if 90.0 <= ang < 270.0:
            row["node_at_end_a"], row["node_at_end_b"] = (
                row.get("node_at_end_b"),
                row.get("node_at_end_a"),
            )
            reverse_spans(row)
    enforce_angle_constraints(rows)
    return rows


def spline_length(segment: dict) -> float:
    """
    Derives the arc length of a segment from its geometry.

    - If spline_control_points is empty: straight-line Pythagorean distance
      between location_at_end_a and location_at_end_b.
    - If spline_control_points exist: numerically integrates the arc length
      of a degree-(N-1) Bezier curve, where N is the total number of points
      [end_a, cp[0], ..., cp[n-1], end_b]. Works for any number of control
      points; degree is derived from N at runtime. Sampled at 100 steps.
    """

    def dist(p, q):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(p, q)))

    pts = spline_points(segment, steps=100)
    if len(pts) < 2:
        return 0.0
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def derive(network: dict) -> list[dict]:
    """
    Use this when a harness build needs networks/flat.csv, and the node and segment instances, updated from the chosen network. Skip it when the project does not need the flat drawing.

    Build the flattened-network CSV from a chosen network, and update the node and segment instances to match.

    The network decides which rows exist and sets ``segment_id``,
    ``node_at_end_a``, ``node_at_end_b``, and ``length``. ``length`` is the
    3D curve length. The 3D page stores each ``spline_control_points`` triple
    as an offset from end A. ``spline_length`` places those stored triples in
    the Bezier polygon with the two ends and does not add end A.

    ``length_tolerance``, ``angle``, ``angle_constraint``, and
    ``subdivisions`` already saved for a ``segment_id`` are kept. ``angle``
    is the heading from end A to the first bend. Each subdivision is a
    percent of length where the next heading starts. When the 3D ends come
    back swapped versus the saved row, those spans are reversed so the
    drawing stays. A first heading in ``[90, 270)`` swaps the CSV ends and
    adds 180° to each heading, so A is left of B, or above B when the
    segment is vertical.

    On the instances list, each node receives ``2d_translate`` ``{x, y}``,
    parent ``origin`` / ``origin``, ``absolute_rotation``, and
    ``3d_translate`` from the network node. A node id with no instance is
    created as ``item_type`` ``"node"``. Each segment is created or updated
    as ``item_type`` ``"segment"``, parented to end A on ``"origin"``, with
    ``length`` rounded to 2 digits.

    **Args:**
    - `network`: Network dict with ``"segments"`` and ``"nodes"``, such as a chosen network.

    **Returns:**
    - `list`: The flattened rows that were written.
    """
    csv_path = fileio.path("flattened network")

    existing = {}
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["segment_id"]] = {
                    "length_tolerance": row.get("length_tolerance", ""),
                    "angle": row.get("angle", ""),
                    "angle_constraint": row.get("angle_constraint", ""),
                    "subdivisions": row.get("subdivisions", ""),
                    "node_at_end_a": row.get("node_at_end_a", ""),
                    "node_at_end_b": row.get("node_at_end_b", ""),
                }

    # builds a dict with locations as keys that returns a node name
    loc_to_node = {tuple(n["location"]): n["node_id"] for n in network.get("nodes", [])}
    node_by_id = {n["node_id"]: n for n in network.get("nodes", [])}

    rows = []
    for seg in network.get("segments", []):
        sid = seg["segment_id"]
        prev = existing.get(sid, {})
        prev_angle = prev.get("angle", "")
        node_a = loc_to_node.get(tuple(seg["location_at_end_a"]), "")
        node_b = loc_to_node.get(tuple(seg["location_at_end_b"]), "")
        # Headings are stored A→B. 3D ends may come back in the opposite order
        # after a prior canonicalize; reverse the spans so the same layout is kept.
        held = {
            "angle": prev_angle if prev_angle != "" else random.uniform(0, 365),
            "angle_constraint": prev.get("angle_constraint", "") if prev_angle != "" else "",
            "subdivisions": prev.get("subdivisions", "") if prev_angle != "" else "",
        }
        prev_a = (prev.get("node_at_end_a") or "").strip()
        prev_b = (prev.get("node_at_end_b") or "").strip()
        node_a_name = (node_a or "").strip()
        node_b_name = (node_b or "").strip()
        ends_reversed = (
            node_a_name
            and node_b_name
            and prev_a
            and prev_b
            and node_a_name == prev_b
            and node_b_name == prev_a
        )
        if prev_angle != "" and ends_reversed:
            reverse_spans(held)
        rows.append(
            {
                "segment_id": sid,
                "node_at_end_a": node_a,
                "node_at_end_b": node_b,
                "length": spline_length(seg),
                "length_tolerance": prev.get("length_tolerance", ""),
                "angle": held["angle"],
                "angle_constraint": held.get("angle_constraint", ""),
                "subdivisions": held.get("subdivisions", ""),
            }
        )

    canonicalize_segment_endpoints_for_save(rows)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Compute node positions by propagating along segments (BFS from root)
    all_node_names = set()
    for row in rows:
        if row.get("node_at_end_a"):
            all_node_names.add(row["node_at_end_a"])
        if row.get("node_at_end_b"):
            all_node_names.add(row["node_at_end_b"])

    if all_node_names:
        root = "origin" if "origin" in all_node_names else rows[0]["node_at_end_a"]
        node_positions = {root: (0.0, 0.0)}
        pending = list(rows)
        changed = True
        while changed and pending:
            changed = False
            still_pending = []
            for row in pending:
                na = row["node_at_end_a"]
                nb = row["node_at_end_b"]
                dx, dy = layout_delta(row)
                if na in node_positions and nb not in node_positions:
                    xa, ya = node_positions[na]
                    node_positions[nb] = (xa + dx, ya + dy)
                    changed = True
                elif nb in node_positions and na not in node_positions:
                    xb, yb = node_positions[nb]
                    node_positions[na] = (xb - dx, yb - dy)
                    changed = True
                else:
                    still_pending.append(row)
            pending = still_pending

        # Compute absolute_rotation for each node: average of the span headings
        # that touch it, with the span arriving at end B flipped by 180°.
        node_to_angles: dict[str, list[float]] = {}
        for row in rows:
            na = row["node_at_end_a"]
            nb = row["node_at_end_b"]
            spans = spans_of(row)
            if na:
                node_to_angles.setdefault(na, []).append(spans[0]["angle"])
            if nb:
                node_to_angles.setdefault(nb, []).append(
                    (spans[-1]["angle"] + 180) % 360
                )  # flip it if b-side
        node_abs_rotation = {}
        for node, angles in node_to_angles.items():
            rads = [math.radians(a) for a in angles]
            mean_sin = sum(math.sin(r) for r in rads) / len(rads)
            mean_cos = sum(math.cos(r) for r in rads) / len(rads)
            circular_mean = math.degrees(math.atan2(mean_sin, mean_cos)) % 360
            node_abs_rotation[node] = (circular_mean + 180) % 360

        # Write positions and rotation into the instances list, creating nodes if missing
        existing_names = {
            inst["instance_name"] for inst in instances_list.read()
        }
        for node_name, (x, y) in node_positions.items():
            abs_rot = node_abs_rotation.get(node_name, "")
            node_data = {
                "2d_translate": {"x": x, "y": y},
                "parent_csys_instance_name": "origin",
                "parent_csys_outputcsys_name": "origin",
                "absolute_rotation": abs_rot,
            }
            net_node = node_by_id.get(node_name)
            if net_node:
                loc = _point3(net_node.get("location"))
                node_data["3d_translate"] = {
                    "x": loc[0],
                    "y": loc[1],
                    "z": loc[2],
                    "alpha": net_node.get("alpha"),
                    "beta": net_node.get("beta"),
                    "gamma": net_node.get("gamma"),
                }
            if node_name in existing_names:
                instances_list.modify(node_name, node_data)
            else:
                node_data.update(
                    {
                        "item_type": "node",
                        "location_type": "node",
                    }
                )
                instances_list.new_instance(node_name, node_data)

    # Create or update an instance for each segment
    for row in rows:
        segment_id = row["segment_id"]
        segment_data = {
            "item_type": "segment",
            "location_type": "segment",
            "segment_group": segment_id,
            "node_at_end_a": row["node_at_end_a"],
            "node_at_end_b": row["node_at_end_b"],
            "parent_csys_instance_name": row["node_at_end_a"],
            "parent_csys_outputcsys_name": "origin",
            "absolute_rotation": row["angle"],
            "length": round(float(row["length"]), 2),
            "length_tolerance": row["length_tolerance"],
            "subdivisions": row.get("subdivisions") or "",
        }
        try:
            instances_list.new_instance(segment_id, segment_data)
        except ValueError:  # assuming this happens if the instance already exists
            instances_list.modify(segment_id, segment_data)

    return rows


def write_mapped_segment_instances(instance, segment_steps):
    """
    Creates one ``{item_type}-segment`` instance per hop in ``segment_steps``.

    ``segment_steps`` is a list of ``(segment_name, direction)`` pairs, where
    ``direction`` is ``"ab"`` or ``"ba"``. Order in the list becomes
    ``segment_order``.
    """
    for order, (seg_name, direction) in enumerate(segment_steps, start=1):
        instances_list.new_instance(
            f"{instance.get('instance_name')}.{seg_name}",
            {
                "harness": instance.get("harness"),
                "item_type": f"{instance.get('item_type')}-segment",
                "location_type": "segment",
                "print_name": instance.get("print_name"),
                "print_name_at_end_a": instance.get("print_name_at_end_a"),
                "print_name_at_end_b": instance.get("print_name_at_end_b"),
                "segment_group": seg_name,
                "segment_order": f"{order}-{direction}",
                "parent_csys_instance_name": seg_name,
                "channel_group": instance.get("channel_group"),
                "circuit_id": instance.get("circuit_id"),
                "circuit_port_number": instance.get("circuit_port_number"),
                "cable_group": instance.get("cable_group"),
                "cable_identifier": instance.get("cable_identifier"),
                "appearance": instance.get("appearance"),
                "this_harness_from_device_refdes": instance.get(
                    "this_harness_from_device_refdes"
                ),
                "this_harness_from_device_channel_id": instance.get(
                    "this_harness_from_device_channel_id"
                ),
                "this_harness_from_device_connector_name": instance.get(
                    "this_harness_from_device_connector_name"
                ),
                "this_harness_to_device_refdes": instance.get("this_harness_to_device_refdes"),
                "this_harness_to_device_channel_id": instance.get(
                    "this_harness_to_device_channel_id"
                ),
                "this_harness_to_device_connector_name": instance.get(
                    "this_harness_to_device_connector_name"
                ),
                "this_channel_from_device_refdes": instance.get(
                    "this_channel_from_device_refdes"
                ),
                "this_channel_from_device_channel_id": instance.get(
                    "this_channel_from_device_channel_id"
                ),
                "this_channel_to_device_refdes": instance.get(
                    "this_channel_to_device_refdes"
                ),
                "this_channel_to_device_channel_id": instance.get(
                    "this_channel_to_device_channel_id"
                ),
                "this_channel_from_channel_type": instance.get(
                    "this_channel_from_channel_type"
                ),
                "this_channel_to_channel_type": instance.get(
                    "this_channel_to_channel_type"
                ),
                "signal_of_channel_type": instance.get("signal_of_channel_type"),
                "length": instances_list.attribute_of(seg_name, "length"),
            },
        )


def map_instance_to_segments(instance):
    """
    Use this when cable routing needs one instance split into a segment instance for each segment between its ends. A harness script calls cable_utils.map_cables_and_conductors_to_segments instead.

    Maps a segment-based instance across multiple segments using pathfinding.

    Takes an instance that spans between two nodes and creates segment-specific
    instances for each segment in the path between those nodes. Uses breadth-first
    search to find the path through the segment graph, then creates one
    ``{item_type}-segment`` instance per segment carrying the direction it is
    traversed in and its order along the path.

    **Note:** Cavity endpoints are resolved to the ``node`` in the same connector
    group. If ``node_at_end_a`` / ``node_at_end_b`` are already ``item_type=="node"``
    instances, they are used directly. When both ends resolve to the same node,
    the instance is a loopback: it is mapped out and back on the free stub
    leaving that connector, and each hop's ``length`` is twice the segment
    length.

    **Args:**

    - `instance` (dict): Instance dictionary with `location_type="segment"` that has
        `node_at_end_a` and `node_at_end_b` defined.

    **Raises:**

    - `ValueError`: If the instance is not segment-based, if endpoints are missing,
        if endpoints are not nodes, or if no path is found between the nodes.
    """

    def node_of_endpoint(endpoint_column):
        """Resolve one end of a segment-based instance to a network node.

        Cavities and other connector-group members resolve to the ``node`` in that
        group. If the endpoint is already a ``node`` instance (for example a
        flattened-network node), it is used as-is.
        """
        endpoint = instance.get(endpoint_column)
        if endpoint in ["", None]:
            raise ValueError(
                f"Instance '{instance.get('instance_name')}' has no {endpoint_column}."
            )
        if instances_list.attribute_of(endpoint, "item_type") == "node":
            return endpoint
        if instances_list.attribute_of(endpoint, "location_type") != "node":
            raise ValueError(
                f"While mapping '{instance.get('instance_name')}' to segments, "
                f"location type of '{endpoint}' is not a node."
            )

        connector_group = instances_list.attribute_of(endpoint, "connector_group")
        node = instances_list.instance_in_connector_group_with_item_type(
            connector_group, "node"
        )
        if node == 0:
            raise ValueError(
                f"No 'node' type item found in connector group '{connector_group}' "
                f"while mapping '{instance.get('instance_name')}' to segments."
            )
        return node.get("instance_name")

    if instance.get("location_type") != "segment":
        raise ValueError(
            f"You're trying to map a non segment-based instance "
            f"'{instance.get('instance_name')}' across segments."
        )

    start_node = node_of_endpoint("node_at_end_a")
    end_node = node_of_endpoint("node_at_end_b")

    graph = {}
    segment_lookup = {}  # frozenset({node_a, node_b}) -> segment name
    seg_endpoints = {}  # segment name -> (node_a, node_b) in stored orientation
    connector_nodes = set()
    for row in instances_list.read():
        if (
            row.get("item_type") == "node"
            and row.get("connector_group") not in ("", None)
            and row.get("instance_name") not in ("", None)
        ):
            connector_nodes.add(row.get("instance_name"))
        if row.get("item_type") != "segment":
            continue
        a = row.get("node_at_end_a")
        b = row.get("node_at_end_b")
        if not a or not b:
            continue
        name = row.get("instance_name")
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
        segment_lookup[frozenset([a, b])] = name
        seg_endpoints[name] = (a, b)

    loopback = start_node == end_node
    if loopback:
        stub_graph = {}
        for seg_name, (a, b) in seg_endpoints.items():
            if not a or not b or a == b or not seg_name:
                continue
            if a in connector_nodes and b in connector_nodes:
                continue
            if (a == start_node or a not in connector_nodes) and (
                b == start_node or b not in connector_nodes
            ):
                stub_graph.setdefault(a, set()).add(b)
                stub_graph.setdefault(b, set()).add(a)
        graph = stub_graph

    # BFS recording, for each visited node, the edge it was reached through.
    # A loopback keeps walking the free stub; the target is chosen afterwards.
    pred = {}  # node -> (previous node, segment name, direction)
    visited = {start_node}
    queue = deque([start_node])
    while queue:
        u = queue.popleft()
        if not loopback and u == end_node:
            break
        for v in graph.get(u, []):
            if v in visited:
                continue
            seg_name = segment_lookup.get(frozenset([u, v]))
            if not seg_name:
                continue
            a_end, b_end = seg_endpoints[seg_name]
            pred[v] = (u, seg_name, "ab" if (u == a_end and v == b_end) else "ba")
            visited.add(v)
            queue.append(v)

    if loopback:
        leaves = [
            node
            for node in visited
            if node != start_node and len(graph.get(node, ())) <= 1
        ]
        candidates = leaves or [node for node in visited if node != start_node]
        if not candidates:
            return
        hop_count = {}
        for node in candidates:
            count = 0
            cur = node
            while cur in pred:
                cur = pred[cur][0]
                count += 1
            hop_count[node] = count
        end_node = max(candidates, key=lambda node: (hop_count[node], str(node)))
    elif end_node not in pred and start_node != end_node:
        raise ValueError(f"No segment path found between {start_node} and {end_node}")

    segment_steps = []
    cur = end_node
    while cur != start_node:
        prev, seg_name, direction = pred[cur]
        segment_steps.append((seg_name, direction))
        cur = prev
    segment_steps.reverse()

    write_mapped_segment_instances(instance, segment_steps)
    if loopback:
        for seg_name, _direction in segment_steps:
            base = instances_list.attribute_of(seg_name, "length")
            if base in ("", None):
                continue
            instances_list.modify(
                f"{instance.get('instance_name')}.{seg_name}",
                {"length": float(base) * 2},
            )


def calculate_location(lookup_instance, instances):
    """
    Calculates world coordinates for an instance by accumulating transforms through the CSYS chain.

    Traces the coordinate system hierarchy from the instance up to the origin, accumulating
    translations and rotations at each level. Applies child coordinate system transforms,
    instance ``2d_translate`` ``{x, y, rotate}``, and rotations to compute the final world
    position and angle. Older ``translate_x`` / ``translate_y`` / ``rotate_csys`` cells are
    still read when ``2d_translate`` is blank.

    The function handles both Cartesian (x, y) and polar (distance, angle) coordinate
    specifications for child coordinate systems. Absolute rotation overrides accumulated rotation.

    Args:
        lookup_instance (dict): The instance dictionary to calculate coordinates for.
        instances (list): List of all instance dictionaries needed to resolve the parent chain.

    Returns:
        tuple: A tuple of (x_pos, y_pos, angle) representing the world coordinates and
            rotation angle in degrees.

    Raises:
        ValueError: If parent coordinate system information is missing or invalid, or
            if parent instances cannot be found in the instances list.
    """

    def translate_2d(instance):
        def float_or_none(value):
            if value in ("", None):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        td = _as_dict(instance.get("2d_translate"))
        if td:
            return (
                float_or_none(td.get("x")),
                float_or_none(td.get("y")),
                float_or_none(td.get("rotate")),
            )
        return (
            float_or_none(instance.get("translate_x")),
            float_or_none(instance.get("translate_y")),
            float_or_none(instance.get("rotate_csys")),
        )

    chain = _csys_chain(lookup_instance, instances)

    x_pos = 0.0
    y_pos = 0.0
    angle = 0.0

    for chainlink in chain:
        relevant_csys_child = _csys_child_of(chainlink, instances)

        angle_old = angle
        dx = 0.0
        dy = 0.0

        if relevant_csys_child is not None:
            if relevant_csys_child.get("x") not in [
                "",
                None,
            ] and relevant_csys_child.get("y") not in ["", None]:
                dx = float(relevant_csys_child.get("x"))
                dy = float(relevant_csys_child.get("y"))
            elif relevant_csys_child.get("distance") not in [
                "",
                None,
            ] and relevant_csys_child.get("angle") not in ["", None]:
                dist = float(relevant_csys_child.get("distance"))
                ang = math.radians(float(relevant_csys_child.get("angle")))
                dx = dist * math.cos(ang)
                dy = dist * math.sin(ang)

            if relevant_csys_child.get("rotation") not in ["", None]:
                angle += float(relevant_csys_child.get("rotation"))

        x_pos += dx * math.cos(math.radians(angle_old)) - dy * math.sin(
            math.radians(angle_old)
        )
        y_pos += dx * math.sin(math.radians(angle_old)) + dy * math.cos(
            math.radians(angle_old)
        )

        tx, ty, rotate = translate_2d(chainlink)
        if tx is not None:
            x_pos += tx
        if ty is not None:
            y_pos += ty
        if rotate is not None:
            angle += rotate

        if chainlink.get("absolute_rotation") not in ["", None]:
            angle = float(chainlink.get("absolute_rotation"))

    return x_pos, y_pos, angle


# Match harnice_console.html ``buildFlatPts``: model length × scale → SVG px, Y down.
CONSOLE_LAYOUT_SCALE = 20.0

APPLIED_TRACES_GROUP_ID = "applied-traces"
CONDUCTOR_TRACES_GROUP_ID = "conductor_traces"
CABLE_TRACES_GROUP_ID = "cable_traces"
FLATTENED_BASE_GROUP_ID = "flattened-network-base"


def read_rows():
    """Read flattened network CSV rows from ``fileio.path(\"flattened network\")``."""
    csv_path = fileio.path("flattened network")
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_console_network_2d(rows):
    """
    Build a ``draw_segments_across_paths`` network from flattened CSV rows.

    Layout matches the console ``buildFlatPts`` BFS (scale 20, Y negated for SVG).
    Coordinates are SVG user units (pixels). A subdivided segment's end-to-end
    step is the sum of its spans. Interior stations are ``waypoints`` on the
    segment, in the same coordinate space as ``nodes``, ordered from A to B.
    """

    nodes = {}
    segments = {}
    if not rows:
        return {"nodes": nodes, "segments": segments}

    def seg_dx_dy(row):
        return layout_delta(row, scale=CONSOLE_LAYOUT_SCALE, y_down=True)

    first = rows[0]
    na0 = (first.get("node_at_end_a") or "").strip()
    nb0 = (first.get("node_at_end_b") or "").strip()
    if na0:
        nodes[na0] = {"x": 0.0, "y": 0.0}
    if na0 and nb0:
        dx0, dy0 = seg_dx_dy(first)
        nodes[nb0] = {"x": dx0, "y": dy0}

    changed = True
    while changed:
        changed = False
        for row in rows:
            na = (row.get("node_at_end_a") or "").strip()
            nb = (row.get("node_at_end_b") or "").strip()
            if not na or not nb:
                continue
            dx, dy = seg_dx_dy(row)
            a_pos = nodes.get(na)
            b_pos = nodes.get(nb)
            if a_pos is not None and b_pos is None:
                nodes[nb] = {"x": a_pos["x"] + dx, "y": a_pos["y"] + dy}
                changed = True
            elif b_pos is not None and a_pos is None:
                nodes[na] = {"x": b_pos["x"] - dx, "y": b_pos["y"] - dy}
                changed = True

    for row in rows:
        na = (row.get("node_at_end_a") or "").strip()
        nb = (row.get("node_at_end_b") or "").strip()
        if not na or not nb:
            continue
        if na in nodes and nb in nodes:
            continue
        dx, dy = seg_dx_dy(row)
        max_x = max((p["x"] for p in nodes.values()), default=0.0)
        offset_x = max_x + abs(dx) + 100.0
        if na not in nodes:
            nodes[na] = {"x": offset_x, "y": 0.0}
        if nb not in nodes:
            nodes[nb] = {
                "x": nodes[na]["x"] + dx,
                "y": nodes[na]["y"] + dy,
            }

    for row in rows:
        seg_id = (row.get("segment_id") or "").strip()
        na = (row.get("node_at_end_a") or "").strip()
        nb = (row.get("node_at_end_b") or "").strip()
        if not seg_id or not na or not nb or na not in nodes:
            continue
        poly = polyline_points(
            nodes[na]["x"],
            nodes[na]["y"],
            row,
            scale=CONSOLE_LAYOUT_SCALE,
            y_down=True,
        )
        segments[seg_id] = {
            "node_at_end_a": na,
            "node_at_end_b": nb,
            "waypoints": [{"x": px, "y": py} for px, py in poly[1:-1]],
        }

    return {"nodes": nodes, "segments": segments}


def prepare_analyze_trace_instances(item_type, network_node_ids=None):
    """
    Collect ``conductor`` or ``cable`` instances with ends resolved to network nodes.

    Resolves cavity endpoints the same way as ``map_instance_to_segments``.
    """

    def node_of_endpoint(instance, endpoint_column):
        """Resolve one end of a segment-based instance to a network node.

        Cavities and other connector-group members resolve to the ``node`` in that
        group. If the endpoint is already a ``node`` instance (for example a
        flattened-network node), it is used as-is.
        """
        endpoint = instance.get(endpoint_column)
        if endpoint in ["", None]:
            raise ValueError(
                f"Instance '{instance.get('instance_name')}' has no {endpoint_column}."
            )
        if instances_list.attribute_of(endpoint, "item_type") == "node":
            return endpoint
        if instances_list.attribute_of(endpoint, "location_type") != "node":
            raise ValueError(
                f"While mapping '{instance.get('instance_name')}' to segments, "
                f"location type of '{endpoint}' is not a node."
            )

        connector_group = instances_list.attribute_of(endpoint, "connector_group")
        node = instances_list.instance_in_connector_group_with_item_type(
            connector_group, "node"
        )
        if node == 0:
            raise ValueError(
                f"No 'node' type item found in connector group '{connector_group}' "
                f"while mapping '{instance.get('instance_name')}' to segments."
            )
        return node.get("instance_name")

    out = []
    for instance in instances_list.read():
        if instance.get("item_type") != item_type:
            continue
        if instance.get("location_type") != "segment":
            continue
        try:
            start = node_of_endpoint(instance, "node_at_end_a")
            end = node_of_endpoint(instance, "node_at_end_b")
        except ValueError:
            continue
        if network_node_ids is not None and (
            start not in network_node_ids or end not in network_node_ids
        ):
            continue
        row = dict(instance)
        row["node_at_end_a"] = start
        row["node_at_end_b"] = end
        out.append(row)
    return out


def trace_layer_markup(
    network,
    item_type,
    input_instances=None,
    stroke_width=0.5 / 96,
    segment_spacing=1.5,
    label_font_size=None,
    min_label_segment_length=None,
):
    """
    Raw ``draw_segments_across_paths`` markup for one item type.

    ``input_instances`` optionally restricts the layer to that subset (matched on
    ``instance_name``); instances of other item types are ignored. Pass ``None``
    to draw every ``item_type`` instance in the project.

    The drawing knobs default to the system Analyze overlay values, which suit a
    network laid out at :data:`CONSOLE_LAYOUT_SCALE` px per model unit. Callers
    working in another space (e.g. formboard px, 96 per model inch) should pass
    their own. ``label_font_size`` is in network units; ``min_label_segment_length``
    defaults to a fraction of the network span so it tracks the layout scale.
    """
    from harnice.utils import svg_utils
    from harnice.utils.system_utils import BLOCK_DIAGRAM_TRACE_LABEL_SIZE

    def network_has_path(from_node, to_node):
        if not from_node or not to_node:
            return False
        if from_node == to_node:
            return True
        if from_node not in network["nodes"] or to_node not in network["nodes"]:
            return False
        adj = {}
        for seg in network["segments"].values():
            a = seg.get("node_at_end_a")
            b = seg.get("node_at_end_b")
            if not a or not b:
                continue
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        seen = {from_node}
        queue = deque([from_node])
        while queue:
            u = queue.popleft()
            for v in adj.get(u, ()):
                if v in seen:
                    continue
                if v == to_node:
                    return True
                seen.add(v)
                queue.append(v)
        return False

    if label_font_size is None:
        label_font_size = BLOCK_DIAGRAM_TRACE_LABEL_SIZE

    if not network.get("segments"):
        return ""
    instances = prepare_analyze_trace_instances(
        item_type, network_node_ids=set(network["nodes"])
    )
    if input_instances is not None:
        appearance_by_name = {
            instance.get("instance_name"): instance.get("appearance")
            for instance in input_instances
            if instance.get("instance_name")
        }
        requested_names = set(appearance_by_name)
        instances = [
            instance
            for instance in instances
            if instance.get("instance_name") in requested_names
        ]
        for instance in instances:
            supplied = appearance_by_name[instance.get("instance_name")]
            if supplied not in [None, ""]:
                instance["appearance"] = supplied
    reachable = [
        inst
        for inst in instances
        if network_has_path(inst.get("node_at_end_a"), inst.get("node_at_end_b"))
    ]
    if not reachable:
        return ""

    if min_label_segment_length is None:
        xs = [c["x"] for c in network["nodes"].values()]
        ys = [c["y"] for c in network["nodes"].values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) if xs else 1.0
        span = max(span, 1.0)
        min_label_segment_length = max(15.0, span / 80.0)

    return svg_utils.draw_segments_across_paths(
        input_instances=reachable,
        input_network_2D=network,
        stroke_width=stroke_width,
        segment_spacing=segment_spacing,
        min_label_segment_length=min_label_segment_length,
        label_font_size=label_font_size,
        from_node_id_field="node_at_end_a",
        to_node_id_field="node_at_end_b",
        trace_group_opacity=1,
        connector_node_ids={
            row.get("instance_name")
            for row in instances_list.read()
            if row.get("item_type") == "node"
            and row.get("connector_group") not in ("", None)
            and row.get("instance_name") not in ("", None)
        },
    )


def overlay_view_box(network):
    """``(min_x, min_y, width, height)`` bounding box of the network, with padding."""
    xs = [c["x"] for c in network["nodes"].values()]
    ys = [c["y"] for c in network["nodes"].values()]
    for seg in network.get("segments", {}).values():
        for point in seg.get("waypoints") or []:
            xs.append(point["x"])
            ys.append(point["y"])
    if not xs:
        xs, ys = [0.0], [0.0]
    pad = 40.0
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    return min_x, min_y, width, height


def build_flattened_network_master_svg_text(rows=None):
    """Network skeleton overlay (nodes, edges, labels) — no conductor/cable traces."""

    def overlay_svg_text(layer_group_id, inner_markup, min_x, min_y, width, height):
        """
        SVG holding a single flat layer group, for Analyze only.

        There is intentionally no ``-contents-start`` / ``-contents-end`` wrapper: that
        pair is what marks a file as a placeable PDF master, and these overlays are laid
        out at console scale rather than in 96 dpi drawing space, so they must never
        land on a sheet next to a formboard.
        """

        def indent_markup(markup, spaces):
            raw = (markup or "").strip()
            if not raw:
                return ""
            pad = " " * spaces
            return "\n".join(
                pad + line if line.strip() else "" for line in raw.split("\n")
            )

        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width:.3f}" height="{height:.3f}" '
                f'viewBox="{min_x:.3f} {min_y:.3f} {width:.3f} {height:.3f}">'
            ),
            f'  <g id="{layer_group_id}">',
        ]
        if inner_markup.strip():
            parts.append(indent_markup(inner_markup, 4))
        parts.append("  </g>")
        parts.append("</svg>")
        parts.append("")
        return "\n".join(parts)

    def xml_escape(text):
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def base_network_markup(network):
        def polyline_midpoint(points):
            """Point halfway along a polyline of ``{"x", "y"}`` vertices."""
            if not points:
                return {"x": 0.0, "y": 0.0}
            if len(points) == 1:
                return {"x": points[0]["x"], "y": points[0]["y"]}
            lengths = []
            total = 0.0
            for i in range(len(points) - 1):
                dist = math.hypot(
                    points[i + 1]["x"] - points[i]["x"],
                    points[i + 1]["y"] - points[i]["y"],
                )
                lengths.append(dist)
                total += dist
            if total <= 0.0:
                return {"x": points[0]["x"], "y": points[0]["y"]}
            half = total / 2.0
            covered = 0.0
            for i, dist in enumerate(lengths):
                if covered + dist >= half:
                    t = 0.0 if dist == 0.0 else (half - covered) / dist
                    return {
                        "x": points[i]["x"] + (points[i + 1]["x"] - points[i]["x"]) * t,
                        "y": points[i]["y"] + (points[i + 1]["y"] - points[i]["y"]) * t,
                    }
                covered += dist
            return {"x": points[-1]["x"], "y": points[-1]["y"]}

        lines = []
        for seg_id, seg in network.get("segments", {}).items():
            na = network["nodes"].get(seg.get("node_at_end_a"))
            nb = network["nodes"].get(seg.get("node_at_end_b"))
            if not na or not nb:
                continue
            path = [na] + list(seg.get("waypoints") or []) + [nb]
            points_attr = " ".join(f'{p["x"]:.3f},{p["y"]:.3f}' for p in path)
            lines.append(
                f'<polyline data-segment-id="{xml_escape(seg_id)}" '
                f'points="{points_attr}" fill="none" '
                f'stroke="#3a6ea5" stroke-width="1.8" stroke-linecap="round" '
                f'stroke-linejoin="round" opacity="0.35"/>'
            )
            mid = polyline_midpoint(path)
            mx, my = mid["x"], mid["y"]
            lines.append(
                f'<text x="{mx:.3f}" y="{my - 9:.3f}" text-anchor="middle" '
                f'font-size="11" fill="#7a8fa8" opacity="0.45">{xml_escape(seg_id)}</text>'
            )
        drawn = set()
        for nid, pos in network.get("nodes", {}).items():
            if nid in drawn:
                continue
            drawn.add(nid)
            lines.append(
                f'<circle cx="{pos["x"]:.3f}" cy="{pos["y"]:.3f}" r="2.2" '
                f'fill="#c73652" opacity="0.4"/>'
            )
            lines.append(
                f'<text x="{pos["x"]:.3f}" y="{pos["y"] - 11:.3f}" text-anchor="middle" '
                f'font-size="10" fill="#ccc">{xml_escape(nid)}</text>'
            )
        return "\n".join(lines)

    if rows is None:
        rows = read_rows()
    network = build_console_network_2d(rows)
    min_x, min_y, width, height = overlay_view_box(network)
    return overlay_svg_text(
        FLATTENED_BASE_GROUP_ID,
        base_network_markup(network),
        min_x,
        min_y,
        width,
        height,
    )


def build_circuits_overlay_master_svg_text(rows=None):
    """Conductor-trace overlay only (no network skeleton)."""

    def overlay_svg_text(layer_group_id, inner_markup, min_x, min_y, width, height):
        """
        SVG holding a single flat layer group, for Analyze only.

        There is intentionally no ``-contents-start`` / ``-contents-end`` wrapper: that
        pair is what marks a file as a placeable PDF master, and these overlays are laid
        out at console scale rather than in 96 dpi drawing space, so they must never
        land on a sheet next to a formboard.
        """

        def indent_markup(markup, spaces):
            raw = (markup or "").strip()
            if not raw:
                return ""
            pad = " " * spaces
            return "\n".join(
                pad + line if line.strip() else "" for line in raw.split("\n")
            )

        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width:.3f}" height="{height:.3f}" '
                f'viewBox="{min_x:.3f} {min_y:.3f} {width:.3f} {height:.3f}">'
            ),
            f'  <g id="{layer_group_id}">',
        ]
        if inner_markup.strip():
            parts.append(indent_markup(inner_markup, 4))
        parts.append("  </g>")
        parts.append("</svg>")
        parts.append("")
        return "\n".join(parts)

    if rows is None:
        rows = read_rows()
    network = build_console_network_2d(rows)
    min_x, min_y, width, height = overlay_view_box(network)
    return overlay_svg_text(
        CONDUCTOR_TRACES_GROUP_ID,
        trace_layer_markup(network, "conductor"),
        min_x,
        min_y,
        width,
        height,
    )


def build_cable_overlay_master_svg_text(rows=None):
    """Cable-trace overlay only (no network skeleton)."""

    def overlay_svg_text(layer_group_id, inner_markup, min_x, min_y, width, height):
        """
        SVG holding a single flat layer group, for Analyze only.

        There is intentionally no ``-contents-start`` / ``-contents-end`` wrapper: that
        pair is what marks a file as a placeable PDF master, and these overlays are laid
        out at console scale rather than in 96 dpi drawing space, so they must never
        land on a sheet next to a formboard.
        """

        def indent_markup(markup, spaces):
            raw = (markup or "").strip()
            if not raw:
                return ""
            pad = " " * spaces
            return "\n".join(
                pad + line if line.strip() else "" for line in raw.split("\n")
            )

        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{width:.3f}" height="{height:.3f}" '
                f'viewBox="{min_x:.3f} {min_y:.3f} {width:.3f} {height:.3f}">'
            ),
            f'  <g id="{layer_group_id}">',
        ]
        if inner_markup.strip():
            parts.append(indent_markup(inner_markup, 4))
        parts.append("  </g>")
        parts.append("</svg>")
        parts.append("")
        return "\n".join(parts)

    if rows is None:
        rows = read_rows()
    network = build_console_network_2d(rows)
    min_x, min_y, width, height = overlay_view_box(network)
    return overlay_svg_text(
        CABLE_TRACES_GROUP_ID,
        trace_layer_markup(network, "cable"),
        min_x,
        min_y,
        width,
        height,
    )


def empty_analyze_overlays_svg():
    """Minimal Analyze scaffold when masters are not built yet."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
        'viewBox="0 0 400 300">\n'
        '  <g id="trace_overlays-contents-start">\n'
        f'    <g id="{FLATTENED_BASE_GROUP_ID}"></g>\n'
        f'    <g id="{APPLIED_TRACES_GROUP_ID}" data-harnice-derived="1">\n'
        f'      <g id="{CONDUCTOR_TRACES_GROUP_ID}"></g>\n'
        f'      <g id="{CABLE_TRACES_GROUP_ID}"></g>\n'
        "    </g>\n"
        "  </g>\n"
        '  <g id="trace_overlays-contents-end"></g>\n'
        "</svg>\n"
    )


def build_trace_overlays_svg_text(rows=None):
    """
    Compose the Analyze SVG from the on-disk generated masters.

    Reads ``flattened network svg`` (base), ``circuits overlay``, and
    ``cable overlay`` — the same files the PDF editor uses.
    """

    def parse_svg_root(svg_text):
        return ET.fromstring(svg_text)

    def find_elem_by_id(root, elem_id):
        for el in root.iter():
            if el.get("id") == elem_id:
                return el
        return None

    def elem_to_svg_fragment(elem):
        if elem is None:
            return ""
        from harnice.utils import block_diagram_utils

        return block_diagram_utils._svg_fragment_preserve_bound_prefixes(
            ET.tostring(elem, encoding="unicode")
        )

    del rows  # Analyze always uses the written masters, not a live rebuild.
    base_path = fileio.path("flattened network svg")
    circuits_path = fileio.path("circuits overlay")
    cable_path = fileio.path("cable overlay")
    if (
        not os.path.isfile(base_path)
        and not os.path.isfile(circuits_path)
        and not os.path.isfile(cable_path)
    ):
        return empty_analyze_overlays_svg()

    width, height, view_box = "400", "300", "0 0 400 300"
    base_frag = f'<g id="{FLATTENED_BASE_GROUP_ID}"></g>'
    conductor_frag = f'<g id="{CONDUCTOR_TRACES_GROUP_ID}"></g>'
    cable_frag = f'<g id="{CABLE_TRACES_GROUP_ID}"></g>'

    if os.path.isfile(base_path):
        with open(base_path, encoding="utf-8") as f:
            base_text = f.read()
        root = parse_svg_root(base_text)
        width = root.get("width") or width
        height = root.get("height") or height
        view_box = root.get("viewBox") or view_box
        base_el = find_elem_by_id(root, FLATTENED_BASE_GROUP_ID)
        if base_el is not None:
            base_frag = elem_to_svg_fragment(base_el)

    if os.path.isfile(circuits_path):
        with open(circuits_path, encoding="utf-8") as f:
            circuits_text = f.read()
        root = parse_svg_root(circuits_text)
        if not os.path.isfile(base_path):
            width = root.get("width") or width
            height = root.get("height") or height
            view_box = root.get("viewBox") or view_box
        cond_el = find_elem_by_id(root, CONDUCTOR_TRACES_GROUP_ID)
        if cond_el is not None:
            conductor_frag = elem_to_svg_fragment(cond_el)

    if os.path.isfile(cable_path):
        with open(cable_path, encoding="utf-8") as f:
            cable_text = f.read()
        root = parse_svg_root(cable_text)
        if not os.path.isfile(base_path) and not os.path.isfile(circuits_path):
            width = root.get("width") or width
            height = root.get("height") or height
            view_box = root.get("viewBox") or view_box
        cable_el = find_elem_by_id(root, CABLE_TRACES_GROUP_ID)
        if cable_el is not None:
            cable_frag = elem_to_svg_fragment(cable_el)

    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="{view_box}">'
        ),
        '  <g id="trace_overlays-contents-start">',
        f"    {base_frag}",
        f'    <g id="{APPLIED_TRACES_GROUP_ID}" data-harnice-derived="1">',
        f"      {conductor_frag}",
        f"      {cable_frag}",
        "    </g>",
        "  </g>",
        '  <g id="trace_overlays-contents-end"></g>',
        "</svg>",
        "",
    ]
    return "\n".join(parts)


TRACE_OVERLAYS_FILENAME = "trace_overlays.svg"
# Served bytes for Analyze. Invalidated when Build rewrites the masters.
_trace_overlays_cache = {"key": None, "text": ""}


def trace_overlays_svg_path():
    """Combined Analyze SVG written next to the three overlay masters."""
    return os.path.join(
        os.path.dirname(fileio.path("flattened network svg")),
        TRACE_OVERLAYS_FILENAME,
    )


def read_trace_overlays_svg_text():
    """
    Analyze drawing as one SVG.

    Build writes ``trace_overlays.svg``. A later open reads that file. If it is
    missing or older than the masters, compose once and keep the text until the
    masters change. The view does not re-parse the three SVGs on every request.
    """

    def file_mtime(path):
        try:
            return os.path.getmtime(path) if path and os.path.isfile(path) else 0
        except OSError:
            return 0

    composed = trace_overlays_svg_path()
    masters = [
        fileio.path("flattened network svg"),
        fileio.path("circuits overlay"),
        fileio.path("cable overlay"),
    ]
    key = (file_mtime(composed), tuple(file_mtime(path) for path in masters))
    if _trace_overlays_cache["key"] == key and _trace_overlays_cache["text"]:
        return _trace_overlays_cache["text"]
    text = ""
    composed_mtime, master_mtimes = key
    newest_master = max(master_mtimes) if master_mtimes else 0
    if composed_mtime and composed_mtime >= newest_master:
        try:
            with open(composed, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
    if not text:
        text = build_trace_overlays_svg_text()
    _trace_overlays_cache["key"] = key
    _trace_overlays_cache["text"] = text
    return text


def write_trace_overlays_svg(rows=None):
    """
    Write the Analyze overlays: network skeleton + conductor traces + cable traces.

    Call at the end of harness build. Also writes the combined ``trace_overlays.svg``
    that Analyze serves directly. These are not PDF masters: they have no
    contents-start/end wrapper and are laid out at console scale.
    """
    if rows is None:
        rows = read_rows()
    os.makedirs(fileio.dirpath("generated_svgs"), exist_ok=True)
    _trace_overlays_cache["key"] = None
    _trace_overlays_cache["text"] = ""

    base_path = fileio.path("flattened network svg")
    with open(base_path, "w", encoding="utf-8") as f:
        f.write(build_flattened_network_master_svg_text(rows=rows))

    circuits_path = fileio.path("circuits overlay")
    with open(circuits_path, "w", encoding="utf-8") as f:
        f.write(build_circuits_overlay_master_svg_text(rows=rows))

    cable_path = fileio.path("cable overlay")
    with open(cable_path, "w", encoding="utf-8") as f:
        f.write(build_cable_overlay_master_svg_text(rows=rows))

    composed_path = trace_overlays_svg_path()
    with open(composed_path, "w", encoding="utf-8") as f:
        f.write(build_trace_overlays_svg_text())

    return {
        "flattened network svg": base_path,
        "circuits overlay": circuits_path,
        "cable overlay": cable_path,
        "trace overlays": composed_path,
    }
