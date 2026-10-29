import os
import ast
import csv
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from harnice import build_sandbox, cli, fileio, state
from harnice.lists import circuits_list, instances_list
from harnice.project_types import device, system
from harnice.utils import block_diagram_utils, library_utils, svg_utils

# ElementTree defaults to ``xmlns:ns0`` + ``<ns0:tag>`` unless the default SVG namespace is
# registered; unprefixed overlay markup must live in the same namespace as the diagram.
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("schem", "https://example.com/schema/v1")


def mpn_of_device_refdes(refdes):
    """
    Use this when a system build needs the manufacturer part number of a device reference designator.

    Looks up manufacturer part number information for a device reference designator.

    Searches the BOM (Bill of Materials) for a device with the given reference designator
    and returns its manufacturer, part number, and revision.

    **Args:**
    - `refdes` (str): Device reference designator to look up (e.g., `"J1"`, `"X1"`).

    **Returns:**
    - `tuple`: A tuple of `(MFG, MPN, rev)` if found, or `(None, None, None)` if not found.
    """
    for row in fileio.read_tsv("bom"):
        if row.get("device_refdes") == refdes:
            return row.get("MFG"), row.get("MPN"), row.get("rev")
    return None, None, None


def _component_kind(class_attr):
    parts = (class_attr or "").split()
    if "component" not in parts:
        return None
    if "subsystem" in parts or "system" in parts:
        return "subsystem"
    if "device" in parts:
        return "device"
    return None


def export_bom_from_block_diagram():
    """
    Build the system BOM from the block diagram SVG (placed components: ``component device``
    or ``component subsystem``, plus harnesses that have an MPN on
    a refdes marker).

    Reads ``fileio.path("block diagram")``, collects each item's refdes and pull metadata
    attributes on the root ``<g>``, writes ``fileio.path("bom")`` as a TSV with the
    standard system BOM columns, and returns the list of refdes in document order.
    Only direct children of the devices parent group are counted as placed components
    (graphics nested inside a subsystem/device symbol are ignored). Rows for
    ``component subsystem`` have ``system`` set to ``TRUE``.
    When a device ``<g>`` has a ``<configuration>`` child, its JSON object is written to
    the ``configuration`` column (compact one-line JSON).

    Harnesses are taken from ``circle.harness-refdes-marker`` elements that have both a
    non-empty ``data-refdes`` and ``data-pn``. Library fields come from ``data-lib-repo``,
    ``data-lib-subpath``, and ``data-rev``. Those rows have ``harness`` set to ``TRUE``.
    One BOM row is emitted per unique harness refdes (first marker wins).

    **Returns:**
    - `list[str]`: Reference designators for each placed component and harness in the diagram.
    """

    bom_labels = [
        "device_refdes",
        "MFG",
        "MPN",
        "lib_repo",
        "lib_subpath",
        "rev",
        "harness",
        "system",
        "configuration",
    ]
    bd_path = fileio.path("block diagram")
    if not os.path.isfile(bd_path):
        raise FileNotFoundError(f"Block diagram not found at expected path:\n{bd_path}")

    tree = block_diagram_utils._parse_block_diagram_svg_file(bd_path)
    root = tree.getroot()
    parent_map = block_diagram_utils._svg_build_parent_map(root)
    rows = []
    refdes_list = []

    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "g":
            continue
        # Only top-level placed instances under the devices parent group — nested
        # ``component`` markup inside a subsystem/device symbol is graphics only.
        parent = parent_map.get(el)
        if parent is None or (parent.get("id") or "") not in block_diagram_utils._SVG_DEVICES_PARENT_GROUP_IDS:
            continue
        comp_kind = _component_kind(el.get("class"))
        if not comp_kind:
            continue
        if el.get("data-harnice-gui-temp-place") == "1":
            continue

        refdes = block_diagram_utils._refdes_from_device_group(el)
        if not refdes:
            continue

        configuration = ""
        for child in list(el):
            if block_diagram_utils._svg_local_tag(child.tag) != "configuration":
                continue
            raw = (child.text or "").strip()
            if not raw:
                break
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                configuration = raw
            else:
                configuration = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            break

        rows.append(
            {
                "device_refdes": refdes,
                "MFG": (el.get("mfg") or el.get("MFG") or "").strip(),
                "MPN": (el.get("mpn") or "").strip(),
                "lib_repo": (el.get("lib_repo") or "").strip(),
                "lib_subpath": (el.get("lib_subpath") or "").strip(),
                "rev": (el.get("rev") or "").strip(),
                "harness": "",
                "system": "TRUE" if comp_kind == "subsystem" else "",
                "configuration": configuration,
            }
        )
        refdes_list.append(refdes)

    # Harnesses with MPN on a refdes marker (same pull columns as devices).
    seen_harness_refdes = set()
    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "circle":
            continue
        cls = el.get("class") or ""
        if "harness-refdes-marker" not in cls.split():
            continue
        # Markers baked into a placed device/subsystem symbol are not harness instances.
        if block_diagram_utils._svg_placed_component_root_g_for_descendant(el, parent_map) is not None:
            continue
        refdes = (el.get("data-refdes") or "").strip()
        mpn = (el.get("data-pn") or "").strip()
        if not refdes or not mpn:
            continue
        if refdes in seen_harness_refdes:
            continue
        seen_harness_refdes.add(refdes)
        rows.append(
            {
                "device_refdes": refdes,
                "MFG": (el.get("data-mfg") or el.get("mfg") or el.get("MFG") or "").strip(),
                "MPN": mpn,
                "lib_repo": (el.get("data-lib-repo") or "").strip(),
                "lib_subpath": (el.get("data-lib-subpath") or "").strip(),
                "rev": (el.get("data-rev") or "").strip(),
                "harness": "TRUE",
                "system": "",
                "configuration": "",
            }
        )
        refdes_list.append(refdes)

    with open(fileio.path("bom"), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bom_labels, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    return refdes_list


def placed_signals_list_path(refdes):
    """
    Absolute path to the signals list (or ICD) for a placed instance.

    Looks under ``instance_data/device/{refdes}/`` first, then
    ``instance_data/system/{refdes}/`` (subsystem ICD). Returns ``None`` if neither
    file exists.
    """
    refdes = (refdes or "").strip()
    if not refdes:
        return None
    instance_data = fileio.dirpath("instance_data")
    for kind in ("device", "system"):
        path = os.path.join(instance_data, kind, refdes, "signals.tsv")
        if os.path.isfile(path):
            return path
    return None


# Sentinel in ``mating_harness_refdes`` for device connectors with no harness wire mate.
UNMATED_HARNESS_REFDES = "<unmated>"


def _is_real_harness_refdes(h):
    """True when ``h`` is a non-blank harness refdes (not the unmated sentinel)."""
    h = (h or "").strip()
    return bool(h) and h != UNMATED_HARNESS_REFDES


def make_connector_list():
    """
    Use this when a system build needs the system connector list rebuilt from the block diagram. system.build() writes it before the script.

    Build the system connector list TSV from the block diagram SVG.

    Reads ``fileio.path("block diagram")``, writes ``fileio.path("system connector list")``,
    and updates ``system.connector_list``.
    Each row is one harness connector circle under a placed **device**
    symbol—every connector on every placed instance, whether or not a harness wire mates to
    it. When a harness wire endpoint is within mate tolerance of the connector,
    ``mating_harness_refdes`` is taken from that harness cluster's refdes marker (blank if the
    cluster has no marker). When no harness wire mates to the connector,
    ``mating_harness_refdes`` is ``<unmated>``. Multiple wire segments meeting the same
    connector still produce a single row. ``device_connector_mpn`` is resolved from each
    instance's signals list by ``connector_id``. The
    ``external_interface_flag`` column is ``TRUE`` when the block diagram has an
    ``external-interface-flag`` polygon whose ``data-mating-pos`` matches that connector's
    rounded world position (same key as the editor's yellow mating connector). The
    ``mating_harness_asserted_connector_name`` column is the ``data-name`` on the yellow
    ``mating connector`` circle at that same rounded world position (empty when unnamed).

    **Columns:** ``device_refdes``, ``device_connector``,
    ``mating_harness_asserted_connector_name``, ``mating_harness_refdes``,
    ``group_of_connected_harnesses``, ``device_connector_mpn``,
    ``external_interface_flag``.

    ``group_of_connected_harnesses`` is the equivalence class of ``mating_harness_refdes``
    values linked through passthroughs: harnesses mated to the two faces of the same
    passthrough channel are unioned. Labels are sorted harness names joined by ``+``
    (e.g. ``H1+H2``). ``<unmated>`` is not grouped; those rows keep an empty
    ``group_of_connected_harnesses``.
    """

    def connector_mpn_from_signals(device_refdes, device_connector):
        """Resolve connector MPN from a placed instance's signals list.

        Devices and subsystems use the unified signals list: match ``connector_id``
        and return ``device_connector_mpn`` or ``harness_connector_mpn``, whichever
        is set.
        """
        if not device_refdes or not device_connector:
            return ""
        side = device_connector.strip()

        paths = []
        device_or_system_path = placed_signals_list_path(device_refdes)
        if device_or_system_path:
            paths.append(device_or_system_path)

        for signals_path in paths:
            if not os.path.isfile(signals_path):
                continue
            for row in fileio.read_tsv(signals_path):
                if (row.get("connector_id") or "").strip() != side:
                    continue
                return (
                    (row.get("device_connector_mpn") or "").strip()
                    or (row.get("harness_connector_mpn") or "").strip()
                )

        return ""

    def group_of_connected_harnesses_labels_from_rows(rows):
        """
        Harnesses mated to the two faces of a passthrough belong to one group.
        Transitive chains (H1—device—H2—device—H3) collapse to one component.
        Mixers and other multi-connector devices without a passthrough stay split.
        ``<unmated>`` rows are excluded from grouping.
        """
        from harnice.lists import signals_list

        parent = {}

        def _ensure(x):
            if x not in parent:
                parent[x] = x

        def _find(x):
            _ensure(x)
            if parent[x] != x:
                parent[x] = _find(parent[x])
            return parent[x]

        for r in rows:
            h = (r.get("mating_harness_refdes") or "").strip()
            if _is_real_harness_refdes(h):
                _ensure(h)

        harness_by_device_connector = defaultdict(dict)
        for r in rows:
            refdes = (r.get("device_refdes") or "").strip()
            connector_id = (r.get("device_connector") or "").strip()
            harness = (r.get("mating_harness_refdes") or "").strip()
            if refdes and connector_id:
                harness_by_device_connector[refdes][connector_id] = harness

        for refdes, connectors in harness_by_device_connector.items():
            path = placed_signals_list_path(refdes)
            if not path:
                continue
            for _channel_id, sides in signals_list.passthrough_channels(path).items():
                hs = sorted(
                    {
                        connectors.get(connector_id, "")
                        for connector_id in sides
                        if _is_real_harness_refdes(connectors.get(connector_id))
                    }
                )
                for i in range(1, len(hs)):
                    a, b = hs[0], hs[i]
                    if not a or not b or a == b:
                        continue
                    ra, rb = _find(a), _find(b)
                    if ra != rb:
                        parent[rb] = ra

        buckets = defaultdict(set)
        for x in parent:
            buckets[_find(x)].add(x)
        out = {}
        for members in buckets.values():
            ordered = sorted(members)
            lab = "+".join(ordered)
            for m in ordered:
                out[m] = lab
        return out

    bd_path = fileio.path("block diagram")
    if not os.path.isfile(bd_path):
        raise FileNotFoundError(f"Block diagram not found at expected path:\n{bd_path}")

    tree = block_diagram_utils._parse_block_diagram_svg_file(bd_path)
    root = tree.getroot()
    parent_map = block_diagram_utils._svg_build_parent_map(root)

    # Mating positions marked with an external-interface-flag polygon (editor ``data-mating-pos``).
    external_interface_pos_keys = set()
    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "polygon":
            continue
        cls = el.get("class") or ""
        if "external-interface-flag" not in cls.split():
            continue
        pos_key = (el.get("data-mating-pos") or "").strip()
        if pos_key:
            external_interface_pos_keys.add(pos_key)

    # Yellow mating-connector names keyed by rounded world position (same as editor pos key).
    asserted_name_by_pos = {}
    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "circle":
            continue
        cls = el.get("class") or ""
        if "mating" not in cls.split() or "connector" not in cls.split():
            continue
        try:
            cx = float(el.get("cx", 0))
            cy = float(el.get("cy", 0))
        except (TypeError, ValueError):
            continue
        pos_key = f"{round(cx)},{round(cy)}"
        name = (el.get("data-name") or "").strip()
        if name:
            asserted_name_by_pos[pos_key] = name

    harness_lines = []
    for el in root.iter():
        if not block_diagram_utils._svg_is_harness_wire_line(el):
            continue
        wid = el.get("id").strip()
        x1 = float(el.get("x1", 0))
        y1 = float(el.get("y1", 0))
        x2 = float(el.get("x2", 0))
        y2 = float(el.get("y2", 0))
        sw = float(el.get("stroke-width") or 1)
        harness_lines.append(
            {"id": wid, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "sw": sw}
        )

    # segment id -> cluster key (sorted segment ids in connected component)
    seg_by_id = {h["id"]: h for h in harness_lines}
    adj = {hid: set() for hid in seg_by_id}
    for h in harness_lines:
        k1 = block_diagram_utils._svg_wire_coord_key(h["x1"], h["y1"])
        k2 = block_diagram_utils._svg_wire_coord_key(h["x2"], h["y2"])
        for o in harness_lines:
            if o["id"] == h["id"]:
                continue
            ok1 = block_diagram_utils._svg_wire_coord_key(o["x1"], o["y1"])
            ok2 = block_diagram_utils._svg_wire_coord_key(o["x2"], o["y2"])
            if ok1 == k1 or ok2 == k1 or ok1 == k2 or ok2 == k2:
                adj[h["id"]].add(o["id"])
                adj[o["id"]].add(h["id"])

    cluster_key_by_seg = {}
    visited = set()
    for hid in seg_by_id:
        if hid in visited:
            continue
        stack = [hid]
        comp = []
        while stack:
            u = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            comp.append(u)
            stack.extend(v for v in adj[u] if v not in visited)
        ckey = "|".join(sorted(comp))
        for u in comp:
            cluster_key_by_seg[u] = ckey

    hit_tol = 8.0

    harness_refdes_by_cluster = {}
    for el in root.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "circle":
            continue
        cls = el.get("class") or ""
        if "harness-refdes-marker" not in cls.split():
            continue
        try:
            cx = float(el.get("cx", 0))
            cy = float(el.get("cy", 0))
        except (TypeError, ValueError):
            continue
        sid = None
        best_d = float("inf")
        for h in harness_lines:
            d = block_diagram_utils._svg_dist_point_to_segment(
                cx, cy, h["x1"], h["y1"], h["x2"], h["y2"]
            )
            tol = max(h["sw"] * 2.0, hit_tol)
            if d <= tol and d < best_d:
                best_d = d
                sid = h["id"]
        if not sid:
            continue
        ckey = cluster_key_by_seg.get(sid)
        if not ckey:
            continue
        rd = (el.get("data-refdes") or "").strip()
        if rd and (
            ckey not in harness_refdes_by_cluster
            or not harness_refdes_by_cluster.get(ckey)
        ):
            harness_refdes_by_cluster[ckey] = rd

    device_connectors = []
    for el in root.iter():
        if not block_diagram_utils._svg_is_device_harness_connector_circle(el, parent_map):
            continue
        try:
            cx = float(el.get("cx", 0))
            cy = float(el.get("cy", 0))
        except (TypeError, ValueError):
            continue
        wx, wy = block_diagram_utils._svg_world_point_for_element(
            el, cx, cy, parent_map
        )
        pin_name = block_diagram_utils.device_connector_identity(el)
        root_g = block_diagram_utils._svg_placed_component_root_g_for_descendant(
            el, parent_map
        )
        if root_g is None:
            continue
        refdes = block_diagram_utils._refdes_from_device_group(root_g)
        device_connectors.append(
            {
                "wx": wx,
                "wy": wy,
                "device_refdes": refdes,
                "device_connector": pin_name,
            }
        )

    fieldnames = [
        "device_refdes",
        "device_connector",
        "mating_harness_asserted_connector_name",
        "mating_harness_refdes",
        "group_of_connected_harnesses",
        "device_connector_mpn",
        "external_interface_flag",
    ]
    # Rounded world position -> mating_harness_refdes from a mating harness wire endpoint.
    mate_harness_by_pos = {}

    for h in harness_lines:
        x1, y1, x2, y2 = h["x1"], h["y1"], h["x2"], h["y2"]
        ckey = cluster_key_by_seg.get(h["id"], "")
        h_ref = harness_refdes_by_cluster.get(ckey, "") if ckey else ""

        endpoints = (
            [(x1, y1), (x2, y2)]
            if abs(x1 - x2) > 1e-9 or abs(y1 - y2) > 1e-9
            else [(x1, y1)]
        )
        for ex, ey in endpoints:
            match = None
            best_d = float("inf")
            mate_tol = 6.0
            for c in device_connectors:
                d = math.hypot(ex - c["wx"], ey - c["wy"])
                if d <= mate_tol and d < best_d:
                    best_d = d
                    match = c
            if not match:
                continue
            mwx = round(float(match["wx"]))
            mwy = round(float(match["wy"]))
            pos_key = (mwx, mwy)
            existing = mate_harness_by_pos.get(pos_key)
            if existing is None or (not existing and h_ref):
                mate_harness_by_pos[pos_key] = h_ref

    pending_rows = []
    emitted_pos = set()
    for c in sorted(
        device_connectors,
        key=lambda r: (
            r.get("device_refdes") or "",
            r.get("device_connector") or "",
            round(float(r["wx"])),
            round(float(r["wy"])),
        ),
    ):
        mwx = round(float(c["wx"]))
        mwy = round(float(c["wy"]))
        pos_key = (mwx, mwy)
        if pos_key in emitted_pos:
            continue
        emitted_pos.add(pos_key)

        if pos_key in mate_harness_by_pos:
            h_ref = mate_harness_by_pos[pos_key]
        else:
            h_ref = UNMATED_HARNESS_REFDES

        dev = c.get("device_refdes") or ""
        dcon = c.get("device_connector") or ""
        mpn = connector_mpn_from_signals(dev, dcon) if dev and dcon else ""
        mate_pos_key = f"{mwx},{mwy}"
        ext_flag = "TRUE" if mate_pos_key in external_interface_pos_keys else ""
        pending_rows.append(
            {
                "device_refdes": dev,
                "device_connector": dcon,
                "mating_harness_asserted_connector_name": asserted_name_by_pos.get(
                    mate_pos_key, ""
                ),
                "mating_harness_refdes": h_ref,
                "device_connector_mpn": mpn,
                "external_interface_flag": ext_flag,
            }
        )

    group_by_harness = group_of_connected_harnesses_labels_from_rows(pending_rows)
    rows = []
    for pr in pending_rows:
        h_raw = (pr.get("mating_harness_refdes") or "").strip()
        if _is_real_harness_refdes(h_raw):
            group = group_by_harness.get(h_raw, h_raw)
        else:
            # Unmated (or blank mated-but-unnamed) rows do not join a group of connected harnesses.
            group = ""
        rows.append(
            {
                "device_refdes": pr["device_refdes"],
                "device_connector": pr["device_connector"],
                "mating_harness_asserted_connector_name": pr.get(
                    "mating_harness_asserted_connector_name"
                )
                or "",
                "mating_harness_refdes": pr["mating_harness_refdes"],
                "group_of_connected_harnesses": group,
                "device_connector_mpn": pr["device_connector_mpn"],
                "external_interface_flag": pr["external_interface_flag"],
            }
        )

    system.connector_list = rows

    out_path = fileio.path("system connector list")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


# Block-diagram overlay trace labels: one value in SVG **user units**. ``label_svg`` uses
# it for text ``font-size`` and scales the background rect and inner margin proportionally.
# The same number is ``label_font_size`` in ``svg_utils.TRACE_OVERLAY_STYLE``.
BLOCK_DIAGRAM_TRACE_LABEL_SIZE = svg_utils.TRACE_OVERLAY_STYLE["label_font_size"]


def _self_hop_endpoint(endpoint_contacts, inst_name, node_id, channel_id):
    """One end of a same-connector harness loop, or ``None`` if this hop is not one.

    ``start`` belongs to the from-channel and ``end`` to the to-channel. When
    those ids are the same, or the caller does not name one of them, the two
    ends are handed out in order.
    """
    bag = endpoint_contacts.get(inst_name) or {}
    hop = bag.get("__self_hop__")
    if not isinstance(hop, dict) or hop.get("node") != node_id:
        return None
    channel_id = (channel_id or "").strip()
    from_id = (hop.get("from_channel") or "").strip()
    to_id = (hop.get("to_channel") or "").strip()
    if channel_id and from_id != to_id:
        if channel_id == from_id:
            return hop.get("start")
        if channel_id == to_id:
            return hop.get("end")
    slot = hop.get("_handout", 0)
    hop["_handout"] = slot + 1
    return hop.get("start") if slot % 2 == 0 else hop.get("end")


def block_diagram_harness_overlay_markup(
    instances, *, include_multi_ch_junction_overlays=True, style=None
):
    """
    Return raw SVG markup for harness routing overlays (paths/labels) from the block diagram
    harness graph and ``draw_segments_across_paths``. Does not read or write the block
    diagram file; ``replace_block_diagram_applied_traces`` wraps this inside
    ``channel_traces`` or ``circuit_traces`` under ``applied-traces``. Each trace group
    is emitted with ``opacity="1"`` (full opacity in the SVG file; the editor GUI
    toggles opacity to show/hide traces without changing stored values on save).

    Returns an empty string when there is nothing to draw. Instances on
    ``<unmated>`` are skipped — a patch may end on an unmated face, but that hop
    has no harness wires to draw. Channels that share a ``multi_ch_junction_id``
    follow the connecting harness subtree (each leaf to its T, each T-to-T
    span once; MST if there is no T) even when they have no paired
    harness-channel instances.

    System builds call this twice (channel pass, then circuit pass). Pass
    ``include_multi_ch_junction_overlays=False`` on the circuit pass so
    channel-level junction overlays are not duplicated under ``circuit_traces``.

    A mapped device passthrough is also stroked straight across the symbol:
    one ``channel_id`` with two connectors, both faces used as harness-channel
    ends of the same ``channel_group``, both connector nodes on the diagram.
    Imaginary passthrough channels (``imaginary-…``) count too; they are not
    on the device signals list.
    The stroke runs from that channel's end marker on one face to its marker
    on the other (the harness trace's contact point, not the connector center),
    as a spline tangent to the two harness traces. It is dashed at 60% opacity,
    and it is not added to the harness graph. The crossing is emitted before
    the harness traces so the dashed stroke paints under their label boxes.
    Its trace label is
    ``passthrough-{refdes}.{channel_id}:{channel_group}`` so Analyze highlight
    matches the harness hops. The crossing has no labels. Circuit instances
    do not produce crossings.

    When both ends of a harness channel are the same connector, that hop is
    drawn as an out-and-back on the harness. The two passthrough channels that
    share it each land on one end of the loop, so the dashed chords meet two
    contacts on that face.

    **Args:**
    - ``instances`` (list): Instance row dicts for ``draw_segments_across_paths``.
    - ``include_multi_ch_junction_overlays`` (bool): When True (default), also
      draw channel-level multi-ch-junction overlays from the channel map.
      Circuit-level junction overlays still follow from circuit instances.
    - ``style`` (dict): Optional overlay style. ``None`` uses
      ``svg_utils.trace_overlay_style``, which a build script writes directly
      or sets with ``svg_utils.regenerate_trace_overlays``.

    **Raises:**
    - ``FileNotFoundError``: If the block diagram SVG is missing.
    - ``ValueError``: If there are no harness segments or path resolution fails.
    """

    def harness_graph_adj(graph):
        adj = {}
        for seg in graph.get("segments", {}).values():
            a = seg.get("node_at_end_a")
            b = seg.get("node_at_end_b")
            if not a or not b:
                continue
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        return adj

    def harness_graph_path(adj, start, goal):
        """Shortest node list from ``start`` to ``goal``, or ``None``."""
        if start == goal:
            return [start]
        if start not in adj or goal not in adj:
            return None
        seen = {start}
        queue = [(start, [start])]
        i = 0
        while i < len(queue):
            node, path = queue[i]
            i += 1
            if node == goal:
                return path
            for nxt in adj.get(node, ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append((nxt, path + [nxt]))
        return None

    def junction_overlay_pairs(spoke_nodes, adj):
        """Non-overlapping spoke→T and T→T pairs along the connecting harness subtree.

        Stars every member to one T would redraw the span between two T's once per
        far-side spoke. Walk the union instead: each leaf to its nearest T, and
        each pair of adjacent T's once.
        """

        unique = []
        for n in spoke_nodes:
            if n and n not in unique:
                unique.append(n)
        union = {}
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                path = harness_graph_path(adj, unique[i], unique[j])
                if not path or len(path) < 2:
                    continue
                for a, b in zip(path, path[1:]):
                    union.setdefault(a, set()).add(b)
                    union.setdefault(b, set()).add(a)
        if len(unique) < 2 or not union:
            return []
        hubs = [n for n, nbrs in union.items() if len(nbrs) >= 3]
        if not hubs:
            return []
        hub_set = set(hubs)
        pairs = []
        seen = set()

        def add_pair(a, b):
            if not a or not b or a == b:
                return
            key = tuple(sorted((a, b)))
            if key in seen:
                return
            seen.add(key)
            pairs.append((a, b))

        for spoke in unique:
            if spoke in hub_set:
                continue
            prev = None
            cur = spoke
            visited = {spoke}
            while cur not in hub_set:
                nxts = [n for n in union.get(cur, ()) if n != prev]
                if not nxts:
                    break
                prev, cur = cur, nxts[0]
                if cur in visited:
                    break
                visited.add(cur)
            if cur in hub_set:
                add_pair(spoke, cur)

        for i, h1 in enumerate(hubs):
            for h2 in hubs[i + 1 :]:
                path = harness_graph_path(union, h1, h2)
                if not path or len(path) < 2:
                    continue
                if any(n in hub_set for n in path[1:-1]):
                    continue
                add_pair(h1, h2)
        return pairs

    def mst_spoke_pairs(spokes, adj):
        """MST edges among spoke dicts ``{node, key}`` using harness-graph hop distance."""
        n = len(spokes)
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                if spokes[i]["node"] == spokes[j]["node"]:
                    continue
                path = harness_graph_path(adj, spokes[i]["node"], spokes[j]["node"])
                if path is None:
                    continue
                hops = len(path) - 1
                edges.append((hops, i, j))
        edges.sort()
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        pairs = []
        for _hops, i, j in edges:
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            parent[rj] = ri
            pairs.append((spokes[i], spokes[j]))
            if len(pairs) == n - 1:
                break
        return pairs

    def multi_ch_junction_spoke_groups(graph):
        """``{(jid, group): [{"key", "node"}, ...]}`` for junction members on the harness graph."""
        from harnice.lists import channel_map

        groups = {}
        for row in channel_map.read():
            jid = (row.get("multi_ch_junction_id") or "").strip()
            if not jid:
                continue
            from_key = channel_map._key_from_row(row, "from")
            if from_key is None:
                continue
            try:
                connector = connector_of_channel(from_key)
            except (ValueError, FileNotFoundError):
                continue
            node = f"{from_key[0]}.{connector}"
            if node not in graph.get("nodes", {}):
                continue
            group = (row.get("group_of_connected_harnesses") or "").strip()
            groups.setdefault((jid, group), []).append(
                {
                    "key": from_key,
                    "node": node,
                    "channel_type": (row.get("from_channel_type") or "").strip(),
                }
            )
        return groups

    def multi_ch_junction_node_pairs(spokes, adj):
        """Spoke→T / T→T pairs, or MST among spokes when there is no T."""
        if len(spokes) < 2:
            return []
        node_pairs = junction_overlay_pairs([s["node"] for s in spokes], adj)
        if node_pairs:
            return node_pairs
        return [(a["node"], b["node"]) for a, b in mst_spoke_pairs(spokes, adj)]

    def multi_ch_junction_overlay_instances(graph):
        """Overlay traces along the connecting harness subtree (one pass per span)."""
        adj = harness_graph_adj(graph)
        instances = []
        for (jid, _group), spokes in multi_ch_junction_spoke_groups(graph).items():
            node_channel = {}
            for spoke in spokes:
                key = spoke.get("key")
                if not key or len(key) < 2:
                    continue
                ch = (key[1] or "").strip()
                repeat = (key[2] or "").strip() if len(key) >= 3 else ""
                node_channel[spoke["node"]] = f"{ch}.{repeat}" if repeat else ch
            channel_type = ""
            for spoke in spokes:
                channel_type = (spoke.get("channel_type") or "").strip()
                if channel_type:
                    break
            for idx, (a_node, b_node) in enumerate(multi_ch_junction_node_pairs(spokes, adj)):
                instances.append(
                    {
                        "instance_name": f"multi-ch-junction-{jid}-{idx}",
                        "item_type": "harness-channel",
                        "multi_ch_junction_id": jid,
                        "from_node_id": a_node,
                        "to_node_id": b_node,
                        "print_name": jid,
                        "print_name_at_end_a": node_channel.get(a_node, ""),
                        "print_name_at_end_b": node_channel.get(b_node, ""),
                        "this_channel_from_channel_type": channel_type,
                    }
                )
        return instances

    def multi_ch_junction_circuit_overlay_instances(graph, circuit_instances):
        """Per-signal junction traces: leaf→T (named ``circuit-N``) and T→T backbone."""
        adj = harness_graph_adj(graph)
        groups = multi_ch_junction_spoke_groups(graph)

        by_jid_sig_node = {}
        by_jid_sig = {}
        for inst in circuit_instances or []:
            jid = (inst.get("multi_ch_junction_id") or "").strip()
            sig = (inst.get("signal_of_channel_type") or "").strip()
            if not jid or not sig:
                continue
            node = (
                f"{(inst.get('this_harness_from_device_refdes') or '').strip()}."
                f"{(inst.get('this_harness_from_device_connector_name') or '').strip()}"
            )
            by_jid_sig_node[(jid, sig, node)] = inst
            by_jid_sig.setdefault((jid, sig), []).append(inst)

        instances = []
        for (jid, _group), spokes in groups.items():
            spoke_nodes = {s["node"] for s in spokes}
            pairs = multi_ch_junction_node_pairs(spokes, adj)
            signals = []
            seen_sig = set()
            for (j, sig), insts in by_jid_sig.items():
                if j != jid or sig in seen_sig:
                    continue
                seen_sig.add(sig)
                signals.append((sig, insts[0]))
            for sig, sample in signals:
                node_label = {}
                for spoke in spokes:
                    key = spoke.get("key")
                    if not key or len(key) < 2:
                        continue
                    ch = (key[1] or "").strip()
                    node_label[spoke["node"]] = f"{ch}.{sig}" if ch else sig
                for idx, (a_node, b_node) in enumerate(pairs):
                    a_is_spoke = a_node in spoke_nodes
                    b_is_spoke = b_node in spoke_nodes
                    owner = None
                    if a_is_spoke and not b_is_spoke:
                        owner = by_jid_sig_node.get((jid, sig, a_node))
                    elif b_is_spoke and not a_is_spoke:
                        owner = by_jid_sig_node.get((jid, sig, b_node))
                    if owner and (a_is_spoke ^ b_is_spoke):
                        inst_name = owner.get("instance_name") or f"circuit-{owner.get('circuit_id')}"
                    else:
                        inst_name = f"multi-ch-junction-{jid}-{sig}-{idx}"
                        owner = owner or sample
                    instances.append(
                        {
                            "instance_name": inst_name,
                            "item_type": "circuit",
                            "multi_ch_junction_id": jid,
                            "harness": owner.get("harness"),
                            "from_node_id": a_node,
                            "to_node_id": b_node,
                            "print_name": f"{jid}.{sig}",
                            "print_name_at_end_a": node_label.get(a_node, ""),
                            "print_name_at_end_b": node_label.get(b_node, ""),
                            "appearance": owner.get("appearance"),
                            "signal_of_channel_type": sig,
                            "this_channel_from_channel_type": owner.get(
                                "this_channel_from_channel_type"
                            ),
                        }
                    )
        return instances

    instances = [
        inst
        for inst in (instances or [])
        if _is_real_harness_refdes(inst.get("harness"))
    ]

    with open(fileio.path("block diagram"), "r", encoding="utf-8") as f:
        svg_body = f.read()
    tree = block_diagram_utils._parse_block_diagram_svg_string(svg_body)
    root = tree.getroot()
    parent_map = block_diagram_utils._svg_build_parent_map(root)
    graph = block_diagram_utils._build_harness_network_graph_from_block_diagram(
        root, parent_map
    )

    if not graph["segments"]:
        raise ValueError(
            "No harness wire segments found in the block diagram (class wire harness-wire with id)."
        )

    mcj_circuits = []
    overlay_instances = []
    for inst in instances:
        if (inst.get("multi_ch_junction_id") or "").strip() and (
            inst.get("item_type") or ""
        ).strip() == "circuit":
            mcj_circuits.append(inst)
        else:
            overlay_instances.append(inst)
    if include_multi_ch_junction_overlays:
        overlay_instances.extend(multi_ch_junction_overlay_instances(graph))
    if mcj_circuits:
        overlay_instances.extend(
            multi_ch_junction_circuit_overlay_instances(graph, mcj_circuits)
        )
    if not overlay_instances:
        return ""

    xs = [c["x"] for c in graph["nodes"].values()]
    ys = [c["y"] for c in graph["nodes"].values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) if xs else 1.0
    span = max(span, 1.0)
    draw_style = svg_utils.trace_overlay_style(style)
    if draw_style.get("min_label_segment_length") is None:
        min_lab = max(15.0, span / 80.0)
    else:
        min_lab = float(draw_style["min_label_segment_length"])

    _stroke_in = float(draw_style["stroke_width"])
    _spacing = float(draw_style["segment_spacing"])
    endpoint_contacts = {}
    markup = svg_utils.draw_segments_across_paths(
        input_instances=overlay_instances,
        input_network_2D=graph,
        stroke_width=_stroke_in,
        segment_spacing=_spacing,
        min_label_segment_length=min_lab,
        label_font_size=float(draw_style["label_font_size"]),
        trace_group_opacity=1,
        endpoint_contacts=endpoint_contacts,
    )
    from harnice.lists import signals_list

    passthroughs_by_refdes = {}
    seen_refdes = set()
    hop_ends = {}
    face_hop = {}
    sample_by_group = {}
    for inst in instances:
        if (inst.get("item_type") or "").strip() != "harness-channel":
            continue
        group = (inst.get("channel_group") or "").strip()
        inst_name = inst.get("instance_name") or ""
        if group and (
            group not in sample_by_group
            or (not sample_by_group[group].get("appearance") and inst.get("appearance"))
        ):
            sample_by_group[group] = inst
        for side in ("from", "to"):
            refdes = (inst.get(f"this_harness_{side}_device_refdes") or "").strip()
            connector = (inst.get(f"this_harness_{side}_device_connector_name") or "").strip()
            channel_id = (inst.get(f"this_harness_{side}_device_channel_id") or "").strip()
            if refdes and refdes not in seen_refdes:
                seen_refdes.add(refdes)
                signals_path = placed_signals_list_path(refdes)
                if signals_path:
                    found = signals_list.passthrough_channels(signals_path)
                    if found:
                        passthroughs_by_refdes[refdes] = found
            if not group or not refdes or not connector or not channel_id:
                continue
            hop_ends.setdefault((group, refdes, channel_id), set()).add(connector)
            face_hop.setdefault((group, refdes, channel_id, connector), inst_name)

    nodes = graph["nodes"]
    chunks = []
    for (group, refdes, channel_id), connectors in sorted(
        hop_ends.items(),
        key=lambda item: f"passthrough-{item[0][1]}.{item[0][2]}:{item[0][0]}",
    ):
        faces = (passthroughs_by_refdes.get(refdes) or {}).get(channel_id) or {}
        if len(faces) == 2:
            face_ids = signals_list.ordered_passthrough_faces(faces.keys())
        elif channel_id.startswith("imaginary-") and len(connectors) == 2:
            face_ids = signals_list.ordered_passthrough_faces(connectors)
        else:
            continue
        if len(face_ids) != 2:
            continue
        face_a, face_b = face_ids
        if face_a not in connectors or face_b not in connectors:
            continue
        node_a = f"{refdes}.{face_a}"
        node_b = f"{refdes}.{face_b}"
        if node_a not in nodes or node_b not in nodes or node_a == node_b:
            continue
        if (
            abs(float(nodes[node_a]["x"]) - float(nodes[node_b]["x"])) < 1e-9
            and abs(float(nodes[node_a]["y"]) - float(nodes[node_b]["y"])) < 1e-9
        ):
            continue
        inst_a = face_hop.get((group, refdes, channel_id, face_a), "")
        inst_b = face_hop.get((group, refdes, channel_id, face_b), "")
        hit_a = _self_hop_endpoint(endpoint_contacts, inst_a, node_a, channel_id)
        if hit_a is None:
            raw_a = (endpoint_contacts.get(inst_a) or {}).get(node_a)
            hit_a = raw_a if isinstance(raw_a, dict) and "x" in raw_a else None
        hit_b = _self_hop_endpoint(endpoint_contacts, inst_b, node_b, channel_id)
        if hit_b is None:
            raw_b = (endpoint_contacts.get(inst_b) or {}).get(node_b)
            hit_b = raw_b if isinstance(raw_b, dict) and "x" in raw_b else None
        contact_a = hit_a or {"x": float(nodes[node_a]["x"]), "y": float(nodes[node_a]["y"])}
        contact_b = hit_b or {"x": float(nodes[node_b]["x"]), "y": float(nodes[node_b]["y"])}
        if contact_a.get("departs") is True and contact_b.get("departs") is False:
            contact_a, contact_b = contact_b, contact_a
        ax, ay = float(contact_a["x"]), float(contact_a["y"])
        bx, by = float(contact_b["x"]), float(contact_b["y"])
        if abs(ax - bx) < 1e-9 and abs(ay - by) < 1e-9:
            continue
        dx, dy = bx - ax, by - ay
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            chord = 0.0
        else:
            chord = (-math.degrees(math.atan2(dy, dx))) % 360.0
        trace_group = []
        svg_utils.draw_styled_path(
            [
                {"x": ax, "y": -ay, "tangent": contact_a.get("tangent", chord)},
                {"x": bx, "y": -by, "tangent": contact_b.get("tangent", chord)},
            ],
            _stroke_in,
            svg_utils._resolved_trace_appearance(sample_by_group[group], {}),
            trace_group,
        )
        # Opacity lives on the stroke so Analyze can still show/hide the group.
        # Perpstripe overlays already set stroke-dasharray. A second one is not
        # well-formed SVG, and the next build cannot parse the diagram.
        dashed = []
        for el in trace_group:
            if "stroke-dasharray=" in el:
                if "stroke-opacity=" in el:
                    dashed.append(el)
                else:
                    dashed.append(
                        el.replace("<path ", '<path stroke-opacity="0.6" ', 1).replace(
                            "<line ", '<line stroke-opacity="0.6" ', 1
                        )
                    )
            else:
                dashed.append(
                    el.replace(
                        "<path ",
                        '<path stroke-dasharray="3 2" stroke-opacity="0.6" ',
                        1,
                    ).replace(
                        "<line ",
                        '<line stroke-dasharray="3 2" stroke-opacity="0.6" ',
                        1,
                    )
                )
        trace_group = dashed
        chunks.append(
            svg_utils._trace_group_open_tag(
                {"instance_name": f"passthrough-{refdes}.{channel_id}:{group}"},
                1,
            )
            + "\n"
            + "\n".join(trace_group)
            + "\n</g>"
        )
    crossing = "\n".join(chunk for chunk in chunks if chunk)
    if not crossing:
        return markup
    if not markup:
        return crossing
    # Before the harness traces: their label boxes must paint over this stroke.
    return crossing + "\n" + markup


def apply_block_diagram_trace_overlays(svg_text, style=None):
    """Replace channel and circuit traces in a block-diagram SVG string."""
    instances = instances_list.read()
    channel_instances = []
    circuit_instances = []
    for instance in instances:
        if instance.get("item_type") == "harness-channel":
            channel_instances.append(instance)
        elif instance.get("item_type") == "circuit":
            circuit_instances.append(instance)
    channel_overlay = block_diagram_harness_overlay_markup(
        channel_instances,
        include_multi_ch_junction_overlays=True,
        style=style,
    )
    circuit_overlay = block_diagram_harness_overlay_markup(
        circuit_instances,
        include_multi_ch_junction_overlays=False,
        style=style,
    )
    return block_diagram_utils.replace_block_diagram_applied_traces(
        svg_text, channel_overlay, circuit_overlay
    )


def connector_of_channel(key):
    """
    Use this when a system build needs the connector id for one channel endpoint.

    Connector id for a channel endpoint.

    **Args:**
    - `key` (tuple): `(device_refdes, channel_id)` or
      `(device_refdes, channel_id, repeat_channel_id)` when that channel has
      two endpoints.

    **Returns:**
    - `str`: The ``connector_id`` for that endpoint.

    **Raises:**
    - `ValueError`: If the connector is not found for the given channel.
    """
    if not isinstance(key, (tuple, list)) or len(key) < 2:
        raise ValueError(
            f"connector_of_channel key must be (device_refdes, channel_id) or "
            f"(device_refdes, channel_id, repeat_channel_id); got {key!r}"
        )
    refdes, channel_id = key[0], key[1]
    repeat = key[2] if len(key) > 2 else ""

    signals_path = placed_signals_list_path(refdes)
    if not signals_path:
        raise ValueError(
            f"No signals list / ICD for {refdes!r} under instance_data/device "
            f"or instance_data/system"
        )
    from harnice.lists import signals_list

    return signals_list.connector_id_of_channel(
        channel_id, signals_path, repeat_channel_id=repeat
    )


def find_connector_with_no_circuit(connector_list, circuits_list):
    """
    Use this when a system build should stop if a connector has no circuit.

    Validates that all connectors have associated circuits.

    Checks each connector in the connector list to ensure it has at least one
    corresponding circuit in the circuits list. Skips connectors whose
    ``mating_harness_refdes`` is ``<unmated>`` or contains ``"unconnected"``. Raises an
    error if any connector lacks a circuit.

    **Args:**
    - `connector_list` (list): List of connector dictionaries from the system connector list
        (columns include ``device_refdes``, ``device_connector``, ``mating_harness_refdes``, …).
    - `circuits_list` (list): List of circuit dictionaries from the circuits list.

    **Raises:**
    - `ValueError`: If a connector is found that has no associated circuits. The error
        message suggests checking the channel map and channel compatibility.
    """
    for connector in connector_list:
        device_refdes = connector.get("device_refdes", "").strip()
        connector_name = connector.get("device_connector", "").strip()

        # skip if either key is missing
        if not device_refdes or not connector_name:
            continue

        h_ref = connector.get("mating_harness_refdes", "").strip()
        # skip unmated connectors and "unconnected" harnesses
        if h_ref == UNMATED_HARNESS_REFDES or "unconnected" in h_ref:
            continue

        found_match = False
        for circuit in circuits_list:
            from_device_refdes = circuit.get("harness_from_refdes", "").strip()
            from_connector_name = circuit.get("harness_from_connector_name", "").strip()
            to_device_refdes = circuit.get("harness_to_refdes", "").strip()
            to_connector_name = circuit.get("harness_to_connector_name", "").strip()

            if (
                from_device_refdes == device_refdes
                and from_connector_name == connector_name
            ) or (
                to_device_refdes == device_refdes
                and to_connector_name == connector_name
            ):
                found_match = True
                break

        if not found_match:
            cli.warn(
                f"Connector '{connector_name}' of device '{device_refdes}' does not contain any circuits. Check if it was mapped in the channel map. If n, check channel compatibility."
            )


def _import_bom_devices(update_instances_list=True):
    """
    Pull every BOM device, subsystem, or harness into ``instance_data`` and optionally the instances list.

    Devices with ``build.py`` are built via ``device.build()``.
    A subsystem import also copies that system's channel map to
    ``instance_data/system/{refdes}/maps/channels.tsv``. That file is the
    source of truth for ``channel_map.flatten()``.
    Called from ``system.build()`` after the BOM is exported from the block diagram.
    """

    def bom_item_type(row):
        if (row.get("harness") or "").strip().upper() == "TRUE":
            return "harness"
        if (row.get("system") or "").strip().upper() == "TRUE":
            return "system"
        return "device"

    def evaluate_device_symbol_fstrings(refdes, namespace):
        """Store this device's symbol text while its build namespace is live.

        Does not modify the symbol file. The consuming system's diagram write
        happens later.
        """
        refdes = (refdes or "").strip().strip("?")
        results = {}
        _device_symbol_fstring_results[refdes] = results
        if not refdes:
            return results
        path = fileio.path("block diagram symbol")
        if not path or not os.path.isfile(path):
            return results
        try:
            tree = block_diagram_utils._parse_block_diagram_svg_file(path)
        except (OSError, ET.ParseError) as exc:
            cli.warn(f"{refdes}: could not read symbol text ({type(exc).__name__}: {exc})")
            return results
        ns = _symbol_fstring_namespace(namespace, refdes)
        root = tree.getroot()
        parent_map = {c: p for p in root.iter() for c in list(p)}
        parent_map[root] = None
        local = block_diagram_utils._svg_local_tag
        for node in root.iter():
            if local(node.tag) != "text":
                continue
            if is_under_system_diagram_primitive(node, parent_map):
                continue
            template = symbol_text_template(node)
            if "\\n" not in template and not ("{" in template and "}" in template):
                continue
            results[template] = eval_symbol_fstring(template, ns)
        return results

    bom_rows = fileio.read_tsv("bom")
    instance_data_root = fileio.dirpath("instance_data")

    for row in bom_rows:
        item_type = bom_item_type(row)
        is_harness = item_type == "harness"

        library_utils.pull(
            {
                "instance_name": row.get("device_refdes"),
                "mfg": row.get("MFG"),
                "mpn": row.get("MPN"),
                "item_type": item_type,
                "lib_repo": row.get("lib_repo"),
                "lib_subpath": row.get("lib_subpath"),
                "lib_rev_used_here": row.get("rev"),
                "device_configuration": (row.get("configuration") or "").strip(),
            },
            update_instances_list=update_instances_list,
            destination_directory=os.path.join(
                instance_data_root, item_type, row.get("device_refdes")
            ),
            include_filenames=("instances.tsv",) if is_harness else None,
            replace_destination=is_harness,
        )

    # Build each BOM device, then evaluate its symbol text in that build's namespace.
    clear_device_symbol_fstring_results()
    saved_cwd = os.getcwd()
    saved_pn = getattr(state, "pn", None)
    saved_rev = getattr(state, "rev", None)
    saved_project_type = getattr(state, "project_type", None)
    saved_file_structure = getattr(state, "file_structure", None)
    saved_harness = getattr(state, "harness", None)

    for row in bom_rows:
        if bom_item_type(row) != "device":
            continue

        refdes = row.get("device_refdes")
        if not refdes:
            continue

        dest_dir = os.path.join(instance_data_root, "device", refdes)
        if not os.path.isdir(dest_dir):
            continue

        bi_path = os.path.join(dest_dir, "build.py")
        configuration = {}
        config_text = (row.get("configuration") or "").strip()
        if config_text:
            configuration = ast.literal_eval(config_text)
            if not isinstance(configuration, dict):
                raise ValueError(
                    f"BOM configuration must evaluate to a dict, got "
                    f"{type(configuration).__name__}: {config_text!r}"
                )

        try:
            os.chdir(dest_dir)
            state.set_pn(refdes)
            state.set_rev(None)
            state.set_project_type("device")
            state.set_file_structure(device.file_structure())
            merged = {**device._default_configuration_from_setup(), **configuration}
            script_ns = None
            if os.path.isfile(bi_path):
                try:
                    script_ns = device.build(verbose=False, configuration=configuration)
                except Exception as e:
                    cli.warn(
                        f"device {refdes} build failed, continuing "
                        f"({type(e).__name__}: {e})"
                    )
            if not isinstance(script_ns, dict):
                script_ns = build_sandbox.public_globals()
                script_ns["configuration"] = merged
            else:
                script_ns.setdefault("configuration", merged)
            try:
                evaluate_device_symbol_fstrings(refdes, script_ns)
            except Exception as e:
                cli.warn(
                    f"device {refdes} symbol text failed, continuing "
                    f"({type(e).__name__}: {e})"
                )
        finally:
            os.chdir(saved_cwd)
            if saved_pn is not None:
                state.set_pn(saved_pn)
            if saved_rev is not None:
                state.set_rev(saved_rev)
            if saved_project_type is not None:
                state.set_project_type(saved_project_type)
            if saved_file_structure is not None:
                state.set_file_structure(saved_file_structure)
            if saved_harness is not None:
                state.set_harness(saved_harness)


def create_instances_from_circuits_list():
    """
    Use this when a system build needs connector, cavity, channel, and circuit instances created from the circuits list.

    Creates connector, cavity, channel, and circuit instances from the circuits list.

    Intended to be called from system build instructions (after ``circuits_list.new()``).
    BOM devices/harnesses are imported earlier in ``system.build()`` via
    ``_import_bom_devices``.

    For each circuit, it creates:

    - Connector instances (at both ends, with MPN lookup from system connector list)
    - Connector cavity instances (at both ends)
    - Circuit instance. ``print_name`` is
      ``{signal}_of_{from_device}.{from_ch}<->{to_device}.{to_ch}``;
      ``print_name_at_end_a`` / ``print_name_at_end_b`` are the from/to cavities.
    - Channel instances. ``print_name`` is
      ``{from_device}.{from_ch} <-> {to_device}.{to_ch}``;
      ``print_name_at_end_a`` / ``print_name_at_end_b`` are the mapped device
      channel IDs.
    - Harness-channel instances use the same ``print_name``, but end labels are
      the hop-local channel IDs (``harness_from_channel_id`` /
      ``harness_to_channel_id``) so a passthrough hop shows that passthrough
      channel, not the far-end device channel.
    - Harness-channel instance names are ``{harness}-{harness_chain_index}:channel-…``

    Connector nodes (and parenting connectors to them) are created later when
    the harness is imported via ``import_harness_from_harnice_system``.

    After processing all circuits, the function updates device connector instances with
    device-side and harness-side connector information from the system connector list.
    """
    connectors_list = list(fileio.read_tsv("system connector list"))
    circuits = circuits_list.read()

    for circuit in circuits:
        from_side_device = circuit.get("from_side_device_refdes") or ""
        from_side_ch = circuit.get("from_side_device_chname") or ""
        to_side_device = circuit.get("to_side_device_refdes") or ""
        to_side_ch = circuit.get("to_side_device_chname") or ""
        circuit_print_name = (
            f"{circuit.get('from_signal') or ''}_of_"
            f"{from_side_device}.{from_side_ch}<->{to_side_device}.{to_side_ch}"
        )
        channel_print_name = (
            f"{from_side_device}.{from_side_ch} <-> {to_side_device}.{to_side_ch}"
        )

        from_connector_key = (
            f"{circuit.get('harness_from_refdes')}.{circuit.get('harness_from_connector_name')}"
        )
        from_cavity = f"{from_connector_key}.{circuit.get('harness_from_cavity')}"

        # Look up device connector MPN and asserted harness connector name
        from_connector_mpn = ""
        from_harness_side_connector_id = ""
        for connector in connectors_list:
            if connector.get("device_refdes") == circuit.get(
                "harness_from_refdes"
            ) and connector.get("device_connector") == circuit.get(
                "harness_from_connector_name"
            ):
                from_connector_mpn = connector.get("device_connector_mpn")
                from_harness_side_connector_id = connector.get(
                    "mating_harness_asserted_connector_name"
                ) or ""
                break

        # from device connector
        instances_list.new_instance(
            f"{from_connector_key}.conn",
            {
                "harness": circuit.get("harness"),
                "item_type": "device_connector",
                "location_type": "node",
                "connector_group": from_connector_key,
                "parent_csys_instance_name": f"{from_connector_key}.node",
                "parent_csys_outputcsys_name": "origin",
                "device_side_refdes": circuit.get("harness_from_refdes"),
                "device_side_connector_id": circuit.get("harness_from_connector_name"),
                "device_side_connector_mpn": from_connector_mpn,
                "harness_side_connector_id": from_harness_side_connector_id,
            },
            ignore_duplicates=True,
        )

        # from connector cavity
        instances_list.new_instance(
            from_cavity,
            {
                "harness": circuit.get("harness"),
                "item_type": "device_connector_cavity",
                "location_type": "node",
                "connector_group": from_connector_key,
                "circuit_id": circuit.get("circuit_id"),
                "circuit_port_number": 0,
            },
            ignore_duplicates=True,
        )

        is_mcj = bool((circuit.get("multi_ch_junction_id") or "").strip())
        to_connector_key = (
            f"{circuit.get('harness_to_refdes')}.{circuit.get('harness_to_connector_name')}"
        )
        to_cavity = (
            f"{to_side_device}.{to_side_ch}"
            if is_mcj
            else f"{to_connector_key}.{circuit.get('harness_to_cavity')}"
        )

        if not is_mcj:
            # Look up device connector MPN and asserted harness connector name
            to_connector_mpn = ""
            to_harness_side_connector_id = ""
            for connector in connectors_list:
                if connector.get("device_refdes") == circuit.get(
                    "harness_to_refdes"
                ) and connector.get("device_connector") == circuit.get(
                    "harness_to_connector_name"
                ):
                    to_connector_mpn = connector.get("device_connector_mpn")
                    to_harness_side_connector_id = connector.get(
                        "mating_harness_asserted_connector_name"
                    ) or ""
                    break

            # to device connector
            instances_list.new_instance(
                f"{to_connector_key}.conn",
                {
                    "harness": circuit.get("harness"),
                    "item_type": "device_connector",
                    "location_type": "node",
                    "connector_group": to_connector_key,
                    "device_side_refdes": circuit.get("harness_to_refdes"),
                    "device_side_connector_id": circuit.get("harness_to_connector_name"),
                    "device_side_connector_mpn": to_connector_mpn,
                    "harness_side_connector_id": to_harness_side_connector_id,
                },
                ignore_duplicates=True,
            )

            # to connector cavity
            instances_list.new_instance(
                to_cavity,
                {
                    "harness": circuit.get("harness"),
                    "item_type": "device_connector_cavity",
                    "location_type": "node",
                    "connector_group": to_connector_key,
                    "circuit_id": circuit.get("circuit_id"),
                    "circuit_port_number": 1,
                },
                ignore_duplicates=True,
            )

        circuit_instance = {
            "harness": circuit.get("harness"),
            "item_type": "circuit",
            "print_name": circuit_print_name,
            "print_name_at_end_a": circuit.get("harness_from_cavity") or "",
            "print_name_at_end_b": circuit.get("harness_to_cavity") or "",
            "node_at_end_a": from_cavity,
            "node_at_end_b": to_cavity,
            "channel_group": f"channel-{circuit.get('from_side_device_refdes')}.{circuit.get('from_side_device_chname')}-{circuit.get('to_side_device_refdes')}.{circuit.get('to_side_device_chname')}",
            "circuit_id": circuit.get("circuit_id"),
            "device_side_from_cavity": circuit.get("harness_from_cavity"),
            "device_side_to_cavity": circuit.get("harness_to_cavity"),
            "this_harness_from_device_refdes": circuit.get("harness_from_refdes"),
            "this_harness_from_device_channel_id": circuit.get("harness_from_channel_id"),
            "this_harness_from_device_connector_name": circuit.get(
                "harness_from_connector_name"
            ),
            "this_harness_to_device_refdes": circuit.get("harness_to_refdes"),
            "this_harness_to_device_channel_id": circuit.get("harness_to_channel_id"),
            "this_harness_to_device_connector_name": circuit.get(
                "harness_to_connector_name"
            ),
            "this_channel_from_device_refdes": circuit.get(
                "from_side_device_refdes"
            ),
            "this_channel_from_device_channel_id": circuit.get(
                "from_side_device_chname"
            ),
            "this_channel_to_device_refdes": circuit.get("to_side_device_refdes"),
            "this_channel_to_device_channel_id": circuit.get(
                "to_side_device_chname"
            ),
            "this_channel_from_channel_type": circuit.get("from_channel_type"),
            "this_channel_to_channel_type": circuit.get("to_channel_type"),
            "signal_of_channel_type": circuit.get("from_signal"),
        }
        if is_mcj:
            circuit_instance["multi_ch_junction_id"] = circuit.get(
                "multi_ch_junction_id"
            )
            circuit_instance["from_node_id"] = from_connector_key

        # add circuit
        instances_list.new_instance(
            f"circuit-{circuit.get('circuit_id')}",
            circuit_instance,
            ignore_duplicates=True,
        )

        # --- add channel
        instances_list.new_instance(
            f"channel-{circuit.get('from_side_device_refdes')}.{circuit.get('from_side_device_chname')}-"
            f"{circuit.get('to_side_device_refdes')}.{circuit.get('to_side_device_chname')}",
            {
                "item_type": "channel",
                "print_name": channel_print_name,
                "print_name_at_end_a": from_side_ch,
                "print_name_at_end_b": to_side_ch,
                "node_at_end_a": f"{from_side_device}.{from_side_ch}",
                "node_at_end_b": f"{to_side_device}.{to_side_ch}",
                "channel_group": (
                    f"channel-{circuit.get('from_side_device_refdes')}.{circuit.get('from_side_device_chname')}-"
                    f"{circuit.get('to_side_device_refdes')}.{circuit.get('to_side_device_chname')}"
                ),
                "location_type": "segment",
                "this_channel_from_device_refdes": circuit.get(
                    "from_side_device_refdes"
                ),
                "this_channel_from_device_channel_id": circuit.get(
                    "from_side_device_chname"
                ),
                "this_channel_to_device_refdes": circuit.get("to_side_device_refdes"),
                "this_channel_to_device_channel_id": circuit.get(
                    "to_side_device_chname"
                ),
                "this_channel_from_channel_type": circuit.get("from_channel_type"),
                "this_channel_to_channel_type": circuit.get("to_channel_type"),
            },
            ignore_duplicates=True,
        )

        # One harness-channel per circuit row; index disambiguates repeated harness names in chain_of_harnesses.
        # MCJ circuits terminate on the junction, not a device connector — skip harness-channel
        # so the channel overlay does not try to route to a missing MCJ node.
        harness = (circuit.get("harness") or "").strip()
        harness_chain_index_raw = circuit.get("harness_chain_index")
        if (
            not is_mcj
            and harness
            and harness_chain_index_raw is not None
            and str(harness_chain_index_raw).strip() != ""
        ):
            harness_chain_index = int(harness_chain_index_raw)
            channel_suffix = (
                f"{circuit.get('from_side_device_refdes')}.{circuit.get('from_side_device_chname')}-"
                f"{circuit.get('to_side_device_refdes')}.{circuit.get('to_side_device_chname')}"
            )
            instances_list.new_instance(
                f"{harness}-{harness_chain_index}:channel-{channel_suffix}",
                {
                    "harness": harness,
                    "harness_chain_index": harness_chain_index,
                    "item_type": "harness-channel",
                    "print_name": channel_print_name,
                    "print_name_at_end_a": circuit.get("harness_from_channel_id") or "",
                    "print_name_at_end_b": circuit.get("harness_to_channel_id") or "",
                    "node_at_end_a": (
                        f"{circuit.get('harness_from_refdes') or ''}."
                        f"{circuit.get('harness_from_channel_id') or ''}"
                    ),
                    "node_at_end_b": (
                        f"{circuit.get('harness_to_refdes') or ''}."
                        f"{circuit.get('harness_to_channel_id') or ''}"
                    ),
                    "channel_group": f"channel-{channel_suffix}",
                    "location_type": "segment",
                    "this_harness_from_device_refdes": circuit.get("harness_from_refdes"),
                    "this_harness_from_device_channel_id": circuit.get(
                        "harness_from_channel_id"
                    ),
                    "this_harness_from_device_connector_name": circuit.get(
                        "harness_from_connector_name"
                    ),
                    "this_harness_to_device_refdes": circuit.get("harness_to_refdes"),
                    "this_harness_to_device_channel_id": circuit.get("harness_to_channel_id"),
                    "this_harness_to_device_connector_name": circuit.get(
                        "harness_to_connector_name"
                    ),
                    "this_channel_from_device_refdes": circuit.get(
                        "from_side_device_refdes"
                    ),
                    "this_channel_from_device_channel_id": circuit.get(
                        "from_side_device_chname"
                    ),
                    "this_channel_to_device_refdes": circuit.get(
                        "to_side_device_refdes"
                    ),
                    "this_channel_to_device_channel_id": circuit.get(
                        "to_side_device_chname"
                    ),
                    "this_channel_from_channel_type": circuit.get("from_channel_type"),
                    "this_channel_to_channel_type": circuit.get("to_channel_type"),
                },
                ignore_duplicates=True,
            )

    # Post-process: Update all device connector instances with device-side and harness-side info
    for connector in fileio.read_tsv("system connector list"):
        try:
            instances_list.modify(
                f"{connector.get('device_refdes')}.{connector.get('device_connector')}.conn",
                {
                    "device_side_refdes": connector.get("device_refdes"),
                    "device_side_connector_id": connector.get("device_connector"),
                    "device_side_connector_mpn": connector.get("device_connector_mpn"),
                    "harness_side_connector_id": connector.get(
                        "mating_harness_asserted_connector_name"
                    )
                    or "",
                },
            )
        except ValueError:
            # Skip if device connector instance doesn't exist (may not have been created if no circuits)
            pass


def import_harness_from_harnice_system(
    system_pn,
    system_rev,
    system_lib_repo,
    system_lib_subpath,
    target_harness,
):
    """
    Use this when a harness that comes from a system needs that system's instances for one harness refdes.

    Import harness instances from a system revision's instances list for one harness.

    Resolves the system revision folder from ``fileio.path("repository locations")`` as
    ``{local_path}/{system_lib_subpath}/{system_pn}/rev{system_rev}``,
    then reads ``fileio.path("instances list")`` from that folder,
    sets ``state.harness`` to ``target_harness``, and copies every instance whose
    ``harness`` column matches into the current harness instances list. Circuit
    instances are imported as conductors (same fields,
    ``item_type`` set to ``conductor``). ``print_name``, ``print_name_at_end_a``,
    ``print_name_at_end_b``, and ``appearance`` are copied exactly from the circuit,
    as are cable recommendations (``mpn``, ``lib_repo``, ``lib_subpath``,
    ``cable_group``, ``cable_identifier``). Device connector instances are imported
    as harness connectors (same fields, ``item_type`` set to ``harness_connector``,
    keyed by ``harness_side_connector_id``), parented to a matching ``node`` instance
    (``{harness_side_connector_id}.node``) created for each. Device connector
    cavities are renamed from
    ``{device}.{device_connector}.{cavity}`` to
    ``{harness_side_connector_id}.{cavity}``. Print names are set at creation:
    harness connectors use the connector group, cavities use ``cavity {id}``,
    and nodes use the instance name. Then seeds a node for each connector group
    via ``instances_list.seed_connector_nodes()``.

    **Args:**
    - `system_pn` (str): Part number of the system whose harness you are importing.
    - `system_rev` (str): System revision label as used in folder/file names (e.g. ``"rev1"``).
    - `system_lib_repo` (str): Library repository URL as listed in ``repository_locations.csv``.
    - `system_lib_subpath` (str): Path from that library root to the system PN folder.
      Empty string if the PN folder sits directly under the library root.
    - `target_harness` (str): Harness reference designator to import.

    **Raises:**
    - `FileNotFoundError`: If the system instances list file does not exist.
    - `ValueError`: If required arguments are missing, if ``system_lib_repo`` is
      not in ``repository_locations.csv``, if no connectors/circuits exist for
      ``target_harness``, or if a mating connector on that harness is unnamed.
    """
    system_pn = (system_pn or "").strip()
    system_rev = (system_rev or "").strip()
    system_lib_repo = (system_lib_repo or "").strip()
    system_lib_subpath = (system_lib_subpath or "").strip()
    target_harness = (target_harness or "").strip()
    if not system_pn or not system_rev:
        raise ValueError("system_pn and system_rev are required")
    if not system_lib_repo:
        raise ValueError("system_lib_repo is required")
    if not target_harness:
        raise ValueError("target_harness is required")

    rev_suffix = system_rev
    if len(rev_suffix) >= 3 and rev_suffix[:3].lower() == "rev":
        rev_suffix = rev_suffix[3:].lstrip()
    path_to_system_rev = os.path.join(
        library_utils.get_local_path(system_lib_repo),
        system_lib_subpath,
        system_pn,
        fileio.revision_folder_name(rev_suffix),
    )
    path_to_system_instances_list = os.path.join(
        path_to_system_rev, "instances.tsv"
    )
    if not os.path.isfile(path_to_system_instances_list):
        raise FileNotFoundError(
            f"System instances list not found: {path_to_system_instances_list}"
        )

    state.set_harness(target_harness)

    with open(path_to_system_instances_list, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        instance_fields = list(reader.fieldnames or [])
        system_instances_list_data = list(reader)

    # Rows already tagged with this harness, and the subset import can copy
    # (connectors, cavities, circuits). Other item types are skipped later.
    matching = [
        row
        for row in system_instances_list_data
        if (row.get("harness") or "").strip() == target_harness
    ]
    useful = [
        row
        for row in matching
        if row.get("item_type")
        in ("device_connector", "device_connector_cavity", "circuit")
    ]

    # If those rows are missing, explain why before copying anything.
    if not useful:
        parts = []
        if not system_instances_list_data:
            parts.append(
                f"System instances list is empty ({path_to_system_instances_list}). "
                f"Build {system_pn}-{system_rev} first."
            )
        elif "harness" in instance_fields:
            present = []
            for row in system_instances_list_data:
                value = (row.get("harness") or "").strip()
                if value and value not in present:
                    present.append(value)
            if matching and not useful:
                # Harness name matched, but only skipped types (e.g. harness-channel).
                parts.append(
                    f"{system_pn}-{system_rev} has instances for harness "
                    f"{target_harness!r}, but none are connectors, cavities, or "
                    f"circuits."
                )
            elif present:
                # Wrong harness name, or this harness was never written onto instances.
                listed = ", ".join(repr(name) for name in present)
                parts.append(
                    f"No instances have harness={target_harness!r}. "
                    f"Harnesses in {system_pn}-{system_rev}: {listed}."
                    "(Were there channels mapped in the system through this harness?)"
                )
            else:
                # Column exists but every value is blank — system was not built
                # far enough to assign circuits to a harness.
                parts.append(
                    f"Every instance in {system_pn}-{system_rev} has a blank "
                    f"harness column. Map channels and rebuild the system so "
                    f"circuits exist for {target_harness!r}."
                )

        # Connector list is the source of mating names. Check whether this
        # harness is mated there, and whether those mates were named.
        connector_path = os.path.join(
            path_to_system_rev,
            "lists",
            "connectors.tsv",
        )
        connectors = []
        if os.path.isfile(connector_path):
            with open(connector_path, newline="", encoding="utf-8") as f:
                connectors = list(csv.DictReader(f, delimiter="\t"))
        on_harness = [
            row
            for row in connectors
            if (row.get("mating_harness_refdes") or "").strip() == target_harness
        ]
        if connectors and not on_harness:
            parts.append(
                f"The system connector list has no connectors mated to "
                f"{target_harness!r}."
            )
        else:
            unnamed = [
                f"{row.get('device_refdes')}.{row.get('device_connector')}"
                for row in on_harness
                if not (
                    row.get("mating_harness_asserted_connector_name") or ""
                ).strip()
            ]
            if unnamed:
                parts.append(
                    f"These connectors on {target_harness!r} have no asserted "
                    f"mating name: {', '.join(unnamed)}. Name them on the "
                    f"system block diagram, then rebuild the system."
                )

        if parts:
            raise ValueError(" ".join(parts))

    unnamed_connectors = []
    for instance in system_instances_list_data:
        if instance.get("harness") != target_harness:
            continue
        if instance.get("item_type") != "device_connector":
            continue
        if instance.get("harness_side_connector_id") in ["", None]:
            unnamed_connectors.append(
                f"{instance.get('device_side_refdes')}."
                f"{instance.get('device_side_connector_id')}"
            )
    if unnamed_connectors:
        raise ValueError(
            f"These connectors on {target_harness!r} in {system_pn}-{system_rev} "
            f"have no asserted mating name: {', '.join(unnamed_connectors)}. "
            f"Name them on the system block diagram, then rebuild the system."
        )

    for instance in system_instances_list_data:

        if instance.get("harness") != target_harness:
            continue

        # turn circuits into conductors
        if instance.get("item_type") == "circuit":
            circuit_id = instance.get("circuit_id")

            # find the harness-side connector name of the from and to ends of the circuit
            from_side_connector_name = ""
            to_side_connector_name = ""
            for instance2 in system_instances_list_data:
                if instance2.get("harness") != target_harness:
                    continue
                if instance2.get("item_type") != "device_connector":
                    continue
                if (
                    instance2.get("device_side_refdes")
                    == instance.get("this_harness_from_device_refdes")
                    and instance2.get("device_side_connector_id")
                    == instance.get("this_harness_from_device_connector_name")
                ):
                    from_side_connector_name = instance2.get(
                        "harness_side_connector_id"
                    )
                if (
                    instance2.get("device_side_refdes")
                    == instance.get("this_harness_to_device_refdes")
                    and instance2.get("device_side_connector_id")
                    == instance.get("this_harness_to_device_connector_name")
                ):
                    to_side_connector_name = instance2.get(
                        "harness_side_connector_id"
                    )

            instances_list.new_instance(
                f"conductor-{circuit_id}",
                {
                    "harness": instance.get("harness"),
                    "item_type": "conductor",
                    "location_type": "segment",
                    "print_name": instance.get("print_name") or "",
                    "print_name_at_end_a": instance.get("print_name_at_end_a") or "",
                    "print_name_at_end_b": instance.get("print_name_at_end_b") or "",
                    "appearance": instance.get("appearance") or "",
                    "mpn": instance.get("mpn") or "",
                    "lib_repo": instance.get("lib_repo") or "",
                    "lib_subpath": instance.get("lib_subpath") or "",
                    "cable_group": instance.get("cable_group"),
                    "cable_identifier": instance.get("cable_identifier"),
                    "channel_group": instance.get("channel_group"),
                    "circuit_id": circuit_id,
                    "node_at_end_a": f"{from_side_connector_name}.{instance.get('device_side_from_cavity')}",
                    "node_at_end_b": f"{to_side_connector_name}.{instance.get('device_side_to_cavity')}",
                    "this_harness_from_device_refdes": instance.get(
                        "this_harness_from_device_refdes"
                    ),
                    "this_harness_from_device_channel_id": instance.get(
                        "this_harness_from_device_channel_id"
                    ),
                    "this_harness_from_device_connector_name": instance.get(
                        "this_harness_from_device_connector_name"
                    ),
                    "this_harness_to_device_refdes": instance.get(
                        "this_harness_to_device_refdes"
                    ),
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
                },
            )
        elif instance.get("item_type") == "device_connector":
            harness_side_connector_id = instance.get("harness_side_connector_id")

            instances_list.new_instance(
                harness_side_connector_id,
                {
                    "harness": instance.get("harness"),
                    "item_type": "harness_connector",
                    "location_type": instance.get("location_type"),
                    "connector_group": harness_side_connector_id,
                    "parent_csys_instance_name": f"{harness_side_connector_id}.node",
                    "parent_csys_outputcsys_name": "origin",
                    "print_name": harness_side_connector_id,
                    "device_side_refdes": instance.get("device_side_refdes"),
                    "device_side_connector_id": instance.get(
                        "device_side_connector_id"
                    ),
                    "device_side_connector_mpn": instance.get(
                        "device_side_connector_mpn"
                    ),
                    "harness_side_connector_id": harness_side_connector_id,
                },
            )
            instances_list.new_instance(
                f"{harness_side_connector_id}.node",
                {
                    "harness": instance.get("harness"),
                    "item_type": "node",
                    "location_type": "node",
                    "connector_group": harness_side_connector_id,
                    "print_name": f"{harness_side_connector_id}.node",
                },
                ignore_duplicates=True,
            )
        elif instance.get("item_type") == "device_connector_cavity":
            device_connector_group = instance.get("connector_group") or ""
            harness_side_connector_id = ""
            for instance2 in system_instances_list_data:
                if instance2.get("harness") != target_harness:
                    continue
                if instance2.get("item_type") != "device_connector":
                    continue
                if instance2.get("connector_group") == device_connector_group:
                    harness_side_connector_id = instance2.get(
                        "harness_side_connector_id"
                    )
                    break
            if harness_side_connector_id in ["", None]:
                raise ValueError(
                    f"Harness mating connector for cavity "
                    f"'{instance.get('instance_name')}' "
                    f"(connector group '{device_connector_group}') is not named in "
                    f"target {target_harness} of the controlling system ({system_pn}). "
                    f"Please assign it a name so that the harness's orientation is "
                    f"understood when it is connected in the context of this system."
                )

            instance_name = instance.get("instance_name") or ""
            if device_connector_group and instance_name.startswith(
                f"{device_connector_group}."
            ):
                cavity = instance_name[len(device_connector_group) + 1 :]
            else:
                cavity = instance_name.rsplit(".", 1)[-1]

            instances_list.new_instance(
                f"{harness_side_connector_id}.{cavity}",
                {
                    "harness": instance.get("harness"),
                    "item_type": "device_connector_cavity",
                    "location_type": instance.get("location_type"),
                    "connector_group": harness_side_connector_id,
                    "circuit_id": instance.get("circuit_id"),
                    "circuit_port_number": instance.get("circuit_port_number"),
                    "print_name": f"cavity {cavity}",
                },
            )
        elif instance.get("item_type") == "harness-channel":
            continue
        else:
            instances_list.new_instance(instance.get("instance_name"), instance)

    instances_list.seed_connector_nodes()


def svg_element_visible_text(el):
    """Visible character data of a ``text`` node. Tspan lines are joined with newlines."""
    if el is None:
        return ""
    local = block_diagram_utils._svg_local_tag
    tspans = [c for c in list(el) if local(c.tag) == "tspan"]
    if tspans:
        lines = []
        for tspan in tspans:
            if "data-line" in tspan.attrib:
                lines.append(tspan.get("data-line") or "")
            else:
                line = "".join(tspan.itertext())
                if line == "\u00a0":
                    line = ""
                lines.append(line)
        return "\n".join(lines)
    return "".join(el.itertext()).strip()


def is_under_system_diagram_primitive(el, parent_map):
    """True when ``el`` is nested inside a ``.system-diagram-primitive`` group."""
    cur = el
    while cur is not None:
        classes = (cur.get("class") or "").split()
        if "system-diagram-primitive" in classes:
            return True
        cur = parent_map.get(cur)
    return False


# template -> evaluated string, captured while each device build namespace is live.
_device_symbol_fstring_results = {}


def clear_device_symbol_fstring_results():
    """Drop symbol f-string results from an earlier system build in this process."""
    _device_symbol_fstring_results.clear()


def symbol_text_template(node):
    """F-string source for one symbol text node.

    ``data-text`` when present, otherwise the visible characters.
    """
    raw = node.get("data-text")
    if raw is not None:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        if isinstance(parsed, str):
            return parsed
    return svg_element_visible_text(node)


def eval_symbol_fstring(template, namespace):
    """
    Evaluate ``template`` as a Python f-string in ``namespace``.

    ``\\n`` in the text starts a new line, including inside an expression.
    ``\\\\n`` stays as the two characters ``\\n``. Text with no braces and no
    ``\\n`` is returned unchanged. A failed expression is warned and left as
    the template so the diagram shows what could not be evaluated.
    """
    template = "" if template is None else str(template)
    if "\\" in template:
        out = []
        i = 0
        n = len(template)
        while i < n:
            if template[i] == "\\" and i + 1 < n:
                nxt = template[i + 1]
                if nxt == "n":
                    out.append("\n")
                    i += 2
                    continue
                if nxt == "\\":
                    out.append("\\")
                    i += 2
                    continue
            out.append(template[i])
            i += 1
        template = "".join(out)
    if "{" not in template or "}" not in template:
        return template
    try:
        value = eval("f" + repr(template), namespace)
    except Exception as exc:
        cli.warn(
            f"symbol text f-string failed ({type(exc).__name__}: {exc}): {template!r}"
        )
        return template
    if value is None:
        return ""
    return str(value)


def _symbol_fstring_namespace(namespace, refdes):
    ns = dict(namespace or {})
    if not isinstance(ns.get("configuration"), dict):
        ns["configuration"] = {}
    ns["refdes"] = refdes
    return ns


def _is_device_component_group(el):
    local = block_diagram_utils._svg_local_tag
    if el is None or local(el.tag) != "g":
        return False
    classes = set((el.get("class") or "").split())
    if "component" not in classes or "device" not in classes:
        return False
    gid = (el.get("id") or "").strip().strip("?")
    if not gid or gid.endswith("-contents-start") or gid.endswith("-contents-end"):
        return False
    return True


def apply_placed_symbol_fstrings(root_g):
    """
    Write evaluated f-strings onto text under a placed device or subsystem.

    Uses strings captured when that device was built, when present. Otherwise
    evaluates here with ``configuration`` from the placed ``<configuration>``
    child and ``refdes`` from the group id. Skips text inside an embedded
    system-diagram primitive.
    """

    def set_text(el, value):
        value = "" if value is None else str(value)
        local = block_diagram_utils._svg_local_tag
        if "\n" in value:
            if svg_element_visible_text(el) == value:
                return
            for child in list(el):
                if local(child.tag) == "tspan":
                    el.remove(child)
            el.text = None
            raw = (el.get("font-size") or "12").strip()
            i = 0
            while i < len(raw) and (raw[i].isdigit() or raw[i] == "."):
                i += 1
            try:
                size = float(raw[:i] or "12")
            except ValueError:
                size = 12.0
                i = 0
            unit = raw[i:].strip()
            dy_step = f"{size * 1.2:.4f}".rstrip("0").rstrip(".") + unit
            tag = el.tag if isinstance(el.tag, str) else ""
            if tag.startswith("{") and "}" in tag:
                tag = tag.split("}", 1)[0] + "}tspan"
            else:
                tag = "tspan"
            x = el.get("x") or "0"
            for index, line in enumerate(value.split("\n")):
                tspan = ET.Element(tag)
                tspan.set("x", x)
                tspan.set("dy", "0" if index == 0 else dy_step)
                tspan.set("data-line", line)
                tspan.text = line if line else "\u00a0"
                el.append(tspan)
            return
        if svg_element_visible_text(el) == value.strip():
            return
        tspans = [c for c in list(el) if local(c.tag) == "tspan"]
        if tspans:
            first = tspans[0]
            first.text = value
            first.tail = None
            if "data-line" in first.attrib:
                del first.attrib["data-line"]
            for extra in tspans[1:]:
                el.remove(extra)
            for sub in list(first):
                first.remove(sub)
            el.text = None
            return
        el.text = value
        for child in list(el):
            if local(child.tag) == "tspan":
                el.remove(child)

    def text_in_scope(node, parent_map):
        if is_under_system_diagram_primitive(node, parent_map):
            return False
        cur = parent_map.get(node)
        enclosing = None
        while cur is not None:
            if _is_device_component_group(cur):
                enclosing = cur
                break
            cur = parent_map.get(cur)
        if _is_device_component_group(root_g):
            return enclosing is root_g
        return enclosing is None

    local = block_diagram_utils._svg_local_tag
    refdes = (root_g.get("id") or "").strip().strip("?")
    stored = _device_symbol_fstring_results.get(refdes) or {}
    config = {}
    for child in list(root_g):
        if local(child.tag) != "configuration":
            continue
        raw = "".join(child.itertext()).strip()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        config = parsed if isinstance(parsed, dict) else {}
        break
    fallback_ns = None

    parent_map = {c: p for p in root_g.iter() for c in list(p)}
    parent_map[root_g] = None
    for node in root_g.iter():
        if local(node.tag) != "text":
            continue
        if not text_in_scope(node, parent_map):
            continue
        template = symbol_text_template(node)
        if "\\n" not in template and not ("{" in template and "}" in template):
            continue
        if template in stored:
            value = stored[template]
        else:
            if fallback_ns is None:
                fallback_ns = _symbol_fstring_namespace(
                    {
                        **build_sandbox.public_globals(),
                        "configuration": config,
                    },
                    refdes,
                )
            value = eval_symbol_fstring(template, fallback_ns)
        value = "" if value is None else str(value)
        set_text(node, value)
        if "data-text" in node.attrib:
            node.set("data-text", json.dumps(value))


def apply_component_symbol_fstrings(root):
    """Evaluate symbol f-strings on each device component under ``root``."""
    local = block_diagram_utils._svg_local_tag
    for g in root.iter():
        if local(g.tag) != "g":
            continue
        if not _is_device_component_group(g):
            continue
        apply_placed_symbol_fstrings(g)

def refresh_block_diagram_placed_symbols(svg_text):
    """
    Replace each placed device/subsystem symbol's contents from
    ``instance_data/{type}/{refdes}/`` so library/instance edits are picked up on build.

    Preserves each placed root's transform, id, pull metadata, and ``<configuration>``.
    Subsystem symbols are demoted to graphics (nested components are not instances).
    Missing symbol files are skipped with a warning.

    Leaves the file text unchanged when a placed symbol already matches the
    instance source (ignoring editor-generated ids and formatting). When a
    symbol does change, only that contents-start inner markup is rewritten.
    """
    if not svg_text or not str(svg_text).strip():
        return svg_text

    def instance_symbol_svg_path(item_type, refdes, artifact_id=""):
        """
        Absolute path to a placed instance's symbol SVG under ``instance_data``.

        Devices use ``symbol.svg``. Subsystems (``item_type="system"``) resolve a
        ``subsystem_symbol`` macro SVG by ``artifact_id`` when given, otherwise the
        first available symbol file. Returns ``None`` when no file is found.
        """
        refdes = (refdes or "").strip()
        if not refdes or not item_type:
            return None
        inst_dir = os.path.join(fileio.dirpath("instance_data"), item_type, refdes)
        if not os.path.isdir(inst_dir):
            return None

        if item_type == "device":
            path = os.path.join(inst_dir, "symbol.svg")
            return path if os.path.isfile(path) else None

        if item_type == "system":
            from harnice.utils import system_symbol_utils

            symbols = system_symbol_utils.list_system_symbols_in_directory(inst_dir)
            aid = (artifact_id or "").strip()
            if aid:
                for row in symbols:
                    if row.get("artifact_id") == aid and row.get("path"):
                        return row["path"]
            for row in symbols:
                if row.get("path"):
                    return row["path"]
            flat = os.path.join(inst_dir, "symbol.svg")
            return flat if os.path.isfile(flat) else None

        return None

    def demote_subsystem_symbol_contents_to_primitives(placed_root):
        """
        Strip Harnice object semantics from nested graphics inside a subsystem symbol.

        Nested ``component`` groups, harness wires, mating taps, and ICD flags become
        plain drawing elements so only the outer placed subsystem instance counts as a
        real BOM / connector object.
        """
        local = block_diagram_utils._svg_local_tag

        def strip_classes(el, drop):
            parts = [c for c in (el.get("class") or "").split() if c and c not in drop]
            if parts:
                el.set("class", " ".join(parts))
            elif "class" in el.attrib:
                del el.attrib["class"]

        for g in list(placed_root.iter()):
            if g is placed_root or local(g.tag) != "g":
                continue
            classes = (g.get("class") or "").split()
            if "component" not in classes:
                continue
            strip_classes(g, {"component", "device", "disconnect", "subsystem", "system"})
            for attr in (
                "lib_repo",
                "lib_subpath",
                "mpn",
                "rev",
                "artifact_id",
                "mfg",
                "MFG",
                "disconnect",
            ):
                if attr in g.attrib:
                    del g.attrib[attr]

        for line in placed_root.iter():
            if local(line.tag) != "line":
                continue
            classes = set((line.get("class") or "").split())
            if "wire" not in classes and "harness-wire" not in classes:
                continue
            strip_classes(line, {"wire", "harness-wire"})
            for attr in ("data-from", "data-to"):
                if attr in line.attrib:
                    del line.attrib[attr]

        for el in placed_root.iter():
            classes = set((el.get("class") or "").split())
            if "harness-refdes-marker" in classes:
                strip_classes(el, {"harness-refdes-marker"})
                for attr in (
                    "data-refdes",
                    "data-pn",
                    "data-lib-repo",
                    "data-lib-subpath",
                    "data-rev",
                ):
                    if attr in el.attrib:
                        del el.attrib[attr]

        parent_map = {c: p for p in placed_root.iter() for c in list(p)}
        parent_map[placed_root] = None
        for c in placed_root.iter():
            if local(c.tag) != "circle":
                continue
            classes = set((c.get("class") or "").split())
            if "mating" in classes and "connector" in classes:
                strip_classes(c, {"mating", "connector"})
                continue
            if "connector" in classes and "mating" not in classes:
                if is_under_system_diagram_primitive(c, parent_map):
                    strip_classes(c, {"connector"})

        for el in placed_root.iter():
            classes = set((el.get("class") or "").split())
            if "external-interface-flag" not in classes:
                continue
            strip_classes(el, {"external-interface-flag"})
            for attr in ("data-mating-pos", "data-conn-id"):
                if attr in el.attrib:
                    del el.attrib[attr]

    tree = block_diagram_utils._parse_block_diagram_svg_string(svg_text)
    root = tree.getroot()
    parent_map = block_diagram_utils._svg_build_parent_map(root)
    local = block_diagram_utils._svg_local_tag
    result = svg_text
    updated = 0

    for el in list(root.iter()):
        if local(el.tag) != "g":
            continue
        parent = parent_map.get(el)
        if parent is None or (parent.get("id") or "") not in block_diagram_utils._SVG_DEVICES_PARENT_GROUP_IDS:
            continue
        kind = _component_kind(el.get("class"))
        if not kind:
            continue
        if el.get("data-harnice-gui-temp-place") == "1":
            continue

        refdes = block_diagram_utils._refdes_from_device_group(el)
        if not refdes:
            continue

        item_type = {
            "device": "device",
            "subsystem": "system",
        }.get(kind)
        artifact_id = (el.get("artifact_id") or "").strip()
        symbol_path = instance_symbol_svg_path(item_type, refdes, artifact_id)
        if not symbol_path:
            cli.warn(
                f"skipping symbol refresh for {refdes}: no symbol SVG under "
                f"instance_data/{item_type}/{refdes}/"
            )
            continue

        rid = (el.get("id") or "").strip()
        want_contents_id = f"{rid}-contents-start" if rid else ""
        dest_contents = None
        for child in list(el):
            cid = (child.get("id") or "").strip()
            if want_contents_id and cid == want_contents_id:
                dest_contents = child
                break
        if dest_contents is None:
            for child in list(el):
                if (child.get("id") or "").endswith("-contents-start"):
                    dest_contents = child
                    break
        if dest_contents is None:
            cli.warn(f"skipping symbol refresh for {refdes}: no contents-start group")
            continue
        dest_contents_id = (dest_contents.get("id") or "").strip()
        if not dest_contents_id:
            cli.warn(f"skipping symbol refresh for {refdes}: contents-start has no id")
            continue

        try:
            with open(symbol_path, "r", encoding="utf-8") as f:
                symbol_text = f.read()
            src_tree = block_diagram_utils._parse_block_diagram_svg_string(symbol_text)
        except (OSError, ET.ParseError) as e:
            cli.warn(f"skipping symbol refresh for {refdes}: {type(e).__name__}: {e}")
            continue

        src_contents = None
        for src_el in src_tree.getroot().iter():
            if (src_el.get("id") or "").endswith("-contents-start"):
                src_contents = src_el
                break
        if src_contents is None:
            cli.warn(f"skipping symbol refresh for {refdes}: symbol has no contents-start")
            continue

        scratch_root = block_diagram_utils.clone_svg_element(el)
        scratch_contents = None
        for child in list(scratch_root):
            cid = (child.get("id") or "").strip()
            if cid == dest_contents_id or cid.endswith("-contents-start"):
                scratch_contents = child
                break
        if scratch_contents is None:
            cli.warn(f"skipping symbol refresh for {refdes}: could not clone contents-start")
            continue
        for child in list(scratch_contents):
            scratch_contents.remove(child)
        for child in list(src_contents):
            scratch_contents.append(block_diagram_utils.clone_svg_element(child))

        if kind == "subsystem":
            demote_subsystem_symbol_contents_to_primitives(scratch_root)
        elif kind == "device":
            scratch_parent_map = block_diagram_utils._svg_build_parent_map(scratch_root)
            scratch_circles = block_diagram_utils._svg_device_connector_circles(
                scratch_root, scratch_parent_map
            )
            block_diagram_utils.apply_missing_device_connector_ids(scratch_circles)
            signals_path = placed_signals_list_path(refdes)
            required_ids = []
            if signals_path:
                from harnice.lists import signals_list

                required_ids = signals_list.unique_connector_ids(
                    path_to_signals_list=signals_path
                )
            dest_parent_map = block_diagram_utils._svg_build_parent_map(el)
            dest_circles = block_diagram_utils._svg_device_connector_circles(
                el, dest_parent_map
            )
            for err in block_diagram_utils.device_connector_id_errors(
                dest_circles, required_ids
            ):
                cli.warn(f"{refdes}: {err}")

        apply_placed_symbol_fstrings(scratch_root)

        if block_diagram_utils.svg_children_signature(
            dest_contents
        ) == block_diagram_utils.svg_children_signature(scratch_contents):
            continue

        block_diagram_utils.copy_matching_svg_ids(dest_contents, scratch_contents)
        new_inner = block_diagram_utils.serialize_svg_element_children(scratch_contents)
        spliced = block_diagram_utils.replace_svg_element_inner_by_id(
            result, dest_contents_id, new_inner
        )
        if spliced is None:
            cli.warn(
                f"skipping symbol refresh for {refdes}: could not locate "
                f"{dest_contents_id} in block diagram text"
            )
            continue
        result = spliced
        updated += 1

    if updated:
        print(f"Refreshed {updated} placed symbol(s) from instance_data.")
    return result

