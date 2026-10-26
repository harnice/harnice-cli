import ast
import json
import math
import os
import re

from harnice import cli, fileio
from harnice.lists import flattened_network, instances_list
from harnice.utils import library_utils


def _conductor_row_for_identifier(rows, cable_identifier, cable_instance_name):
    if cable_identifier in [None, ""]:
        raise ValueError(
            f"when assigning a conductor to cable '{cable_instance_name}', "
            "'cable_identifier' is required but blank"
        )

    key = str(cable_identifier).strip()
    matches = [
        row for row in rows if (row.get("identifier") or "").strip() == key
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"cable_identifier '{key}' of '{cable_instance_name}' is not unique. "
            "Rebuild the cable so every conductor key in its attributes JSON "
            "is unique."
        )

    available = ", ".join(
        (row.get("identifier") or "").strip()
        for row in rows
        if (row.get("identifier") or "").strip()
    )
    raise ValueError(
        f"Conductor '{key}' is not in cable '{cable_instance_name}'. "
        f"Available: {available or '(none)'}"
    )


def new_cable(instance_name, mpn, lib_repo, lib_subpath):
    """
    Use this when a harness build needs a library cable imported as a new cable instance.

    Imports a library cable into the project as a new cable instance.

    Creates an instances-list row named `instance_name` (the cable refdes) and
    pulls the matching library part into `instance_data/cable/{instance_name}/`,
    the same way connectors and backshells are imported.

    **Args:**
    - `instance_name` (str): Refdes / instance name for this cable in the project.
    - `mpn` (str): Manufacturer part number of the cable in the library.
    - `lib_repo` (str): Library repository URL, or `"local"` for the project library.
    - `lib_subpath` (str): Subpath within the library to the cable (may be `""`).

    **Raises:**
    - `ValueError`: If required arguments are blank, or an instance with
        `instance_name` already exists.
    - `FileNotFoundError`: If the library cable cannot be found.
    """
    if instance_name in [None, ""]:
        raise ValueError("instance_name is required but blank")
    if mpn in [None, ""]:
        raise ValueError(
            f"when creating cable '{instance_name}', 'mpn' is required but blank"
        )
    if lib_repo in [None, ""]:
        raise ValueError(
            f"when creating cable '{instance_name}', 'lib_repo' is required but blank"
        )
    if lib_subpath is None:
        lib_subpath = ""

    instances_list.new_instance(
        instance_name,
        {
            "item_type": "cable",
            "location_type": "segment",
            "cable_group": instance_name,
            "mpn": mpn,
            "lib_repo": lib_repo,
            "lib_subpath": lib_subpath,
            "print_name": instance_name,
            "print_name_at_end_a": instance_name,
            "print_name_at_end_b": instance_name,
        },
    )
    library_utils.pull(
        {
            "instance_name": instance_name,
            "item_type": "cable",
            "mpn": mpn,
            "lib_repo": lib_repo,
            "lib_subpath": lib_subpath,
        }
    )


def prepare_for_conductor_assign(instance_name):
    """
    Use this when a harness build needs the system cable recommendation cleared on a conductor before that conductor is assigned to a chosen cable.

    Clears system cable-recommendation fields on a conductor so it can be assigned.

    System build writes `mpn`, `lib_repo`, `lib_subpath`, `cable_group`, and
    `cable_identifier` onto circuits as suggestions. Those fields are copied onto
    conductors when the harness is imported. `assign_conductor_to_cable` requires
    `cable_group` and `cable_identifier` to be blank, and the library identity
    belongs on the cable instance after `new_cable`, not on the conductor.

    **Args:**
    - `instance_name` (str): Instance name of the conductor to clear.
    """

    instances_list.modify(
        instance_name,
        {
            "cable_group": "",
            "cable_identifier": "",
            "mpn": "",
            "lib_repo": "",
            "lib_subpath": "",
        },
    )


def assign_conductor_to_cable(instance_name, cable_instance_name, cable_identifier):
    """
    Use this when a harness build needs a conductor instance assigned to one conductor of a cable that is already in the project.

    Assigns a conductor instance to one conductor inside an existing cable.

    Verifies that `cable_instance_name` exists as a cable, that `cable_identifier`
    is a conductor in that cable's conductor list, that the conductor instance
    has blank `cable_group` and `cable_identifier`, and that no instance already
    holds that cable-and-identifier pair. Then writes `cable_group`,
    `cable_identifier`, and `appearance` onto the conductor, and writes the
    cable's own appearance (from its attributes JSON) onto the cable instance.

    `cable_identifier` is the `identifier` column from the cable conductor list.
    Cable build requires that column to be unique, so it is sufficient on its own.

    **Args:**
    - `instance_name` (str): Instance name of the conductor to assign.
    - `cable_instance_name` (str): Instance name of the cable created with
        `new_cable`.
    - `cable_identifier` (str): Conductor in the cable (`identifier` column).

    **Raises:**
    - `ValueError`: If the conductor or cable is missing, the cable has no
        conductor list, `cable_identifier` is missing or not unique, the
        conductor is already assigned, or that cable conductor is already
        assigned to another instance.
    """
    if instance_name in [None, ""]:
        raise ValueError("instance_name is required but blank")
    if cable_instance_name in [None, ""]:
        raise ValueError(
            f"when assigning '{instance_name}' to a cable, "
            "'cable_instance_name' is required but blank"
        )

    instances = instances_list.read()

    conductor = None
    cable = None
    for instance in instances:
        if instance.get("instance_name") == instance_name:
            if instance.get("cable_group") not in ["", None] or instance.get(
                "cable_identifier"
            ) not in ["", None]:
                raise ValueError(
                    f"when assigning '{cable_identifier}' of "
                    f"'{cable_instance_name}' to '{instance_name}', instance "
                    f"'{instance_name}' has already been assigned to "
                    f"'{instance.get('cable_identifier')}' of cable "
                    f"'{instance.get('cable_group')}'"
                )
            conductor = instance
        if instance.get("instance_name") == cable_instance_name:
            cable = instance

    if conductor is None:
        raise ValueError(f"Conductor instance '{instance_name}' not found")
    if cable is None:
        raise ValueError(f"Cable instance '{cable_instance_name}' not found")
    if cable.get("item_type") != "cable":
        raise ValueError(
            f"Instance '{cable_instance_name}' exists but is not a cable "
            f"(item_type='{cable.get('item_type')}')"
        )

    conductor_list_path = os.path.join(
        fileio.dirpath(None),
        "instance_data",
        "cable",
        cable_instance_name,
        "conductors.tsv",
    )
    if not os.path.isfile(conductor_list_path):
        raise ValueError(
            f"Cable '{cable_instance_name}' has no conductor list at "
            f"{conductor_list_path}; pull it from the library first with "
            "cable_utils.new_cable"
        )

    conductor_row = _conductor_row_for_identifier(
        fileio.read_tsv(conductor_list_path),
        cable_identifier,
        cable_instance_name,
    )
    resolved_identifier = conductor_row.get("identifier")

    for instance in instances:
        if (
            instance.get("cable_group") == cable_instance_name
            and instance.get("cable_identifier") == resolved_identifier
        ):
            raise ValueError(
                f"when assigning '{resolved_identifier}' of '{cable_instance_name}' "
                f"to '{instance_name}', conductor '{resolved_identifier}' of "
                f"'{cable_instance_name}' has already been assigned to "
                f"{instance.get('instance_name')}"
            )

    instances_list.modify(
        instance_name,
        {
            "cable_group": cable_instance_name,
            "cable_identifier": resolved_identifier,
            "appearance": conductor_row.get("appearance"),
        },
    )

    attributes_path = os.path.join(
        os.path.dirname(conductor_list_path),
        "attributes.json",
    )
    cable_appearance = ""
    if os.path.isfile(attributes_path):
        with open(attributes_path, encoding="utf-8") as f:
            node = json.load(f)
        skip = {
            "conductor",
            "properties",
            "appearance",
            "specification",
            "tools",
            "build_notes",
        }
        while isinstance(node, dict):
            if node.get("appearance"):
                cable_appearance = node["appearance"]
                break
            color = (node.get("properties") or {}).get("color")
            if color:
                cable_appearance = {"base_color": color}
                break
            nested = [
                value
                for key, value in node.items()
                if key not in skip and isinstance(value, dict)
            ]
            node = nested[0] if nested else None
    if cable_appearance:
        instances_list.modify(
            cable_instance_name,
            {"appearance": cable_appearance},
        )


def map_cables_and_conductors_to_segments():
    """
    Use this when a harness build needs every cable and conductor routed onto the flattened network and their lengths written.

    Routes every conductor and cable onto the flattened network and writes lengths.

    Conductors are mapped from `node_at_end_a` to `node_at_end_b`. A conductor
    whose ends resolve to the same connector node is a loopback and is mapped
    out and back along that connector's free stub. Cables have no
    ends of their own: each cable is mapped onto the segments shared by every
    conductor assigned to it (the jacketed run before conductors break out to
    different nodes). Those shared-path ends are written onto the cable as
    `node_at_end_a` / `node_at_end_b`. Then writes `length` on each conductor
    (sum of its conductor-segment lengths) and on each cable (longest member
    conductor).

    **Raises:**
    - `ValueError`: If a conductor cannot be mapped. Each end must name a
        node, or a cavity whose connector group has one node. Both ends
        resolving to the same node travel out and back on that connector's
        free stub. No path between the ends raises.
    """
    for instance in instances_list.read():
        if instance.get("item_type") == "conductor":
            flattened_network.map_instance_to_segments(instance)

    instances = instances_list.read()
    by_name = {row.get("instance_name"): row for row in instances}

    conductor_lengths = {}
    conductor_paths = {}
    for instance in instances:
        if instance.get("item_type") != "conductor":
            continue
        name = instance.get("instance_name")
        path = mapped_segment_hops(name, "conductor-segment", instances)
        conductor_paths[name] = path
        length = 0
        for seg_name, _direction in path:
            hop_length = (by_name.get(f"{name}.{seg_name}") or {}).get("length")
            if hop_length in ["", None]:
                continue
            length += float(hop_length)
        conductor_lengths[name] = length
        instances_list.modify(name, {"length": length})

    for instance in instances:
        if instance.get("item_type") != "cable":
            continue
        cable_name = instance.get("instance_name")
        member_names = [
            conductor.get("instance_name")
            for conductor in instances
            if conductor.get("item_type") == "conductor"
            and conductor.get("cable_group") == cable_name
        ]
        paths = [conductor_paths.get(name) or [] for name in member_names]
        paths = [path for path in paths if path]
        common_steps = []
        if paths:
            common = {seg_name for seg_name, _ in paths[0]}
            for path in paths[1:]:
                common &= {seg_name for seg_name, _ in path}
            common_steps = [
                (seg_name, direction)
                for seg_name, direction in paths[0]
                if seg_name in common
            ]
        updates = {
            "length": max(
                (conductor_lengths.get(name, 0) for name in member_names),
                default=0,
            )
        }
        if common_steps:
            first_seg, first_dir = common_steps[0]
            last_seg, last_dir = common_steps[-1]
            first = by_name.get(first_seg) or {}
            last = by_name.get(last_seg) or {}
            if first.get("item_type") != "segment":
                raise ValueError(
                    f"Cable '{cable_name}' common path starts on '{first_seg}', "
                    "which is not a segment."
                )
            if last.get("item_type") != "segment":
                raise ValueError(
                    f"Cable '{cable_name}' common path ends on '{last_seg}', "
                    "which is not a segment."
                )
            a, b = first.get("node_at_end_a"), first.get("node_at_end_b")
            start = b if first_dir == "ba" else a
            a, b = last.get("node_at_end_a"), last.get("node_at_end_b")
            end = a if last_dir == "ba" else b
            if start in ["", None] or end in ["", None]:
                raise ValueError(
                    f"Cable '{cable_name}' has a shared path but blank "
                    "node_at_end_a/node_at_end_b on its end segments "
                    f"('{first_seg}', '{last_seg}')."
                )
            updates["node_at_end_a"] = start
            updates["node_at_end_b"] = end
            mapped = dict(instance)
            mapped.update(updates)
            flattened_network.write_mapped_segment_instances(mapped, common_steps)
        instances_list.modify(cable_name, updates)


_LENGTH_TO_INCHES = {
    "in": 1.0,
    "inch": 1.0,
    "inches": 1.0,
    '"': 1.0,
    "mil": 0.001,
    "thou": 0.001,
    "mm": 1.0 / 25.4,
    "cm": 10.0 / 25.4,
    "m": 1000.0 / 25.4,
}
_ATTRIBUTES_METADATA_KEYS = {
    "conductor",
    "properties",
    "appearance",
    "specification",
    "tools",
    "build_notes",
    "csys_children",
}
# Stringer 1978 bundle factors (count → β). Counts not listed are
# interpolated; counts above 300 are extrapolated from 250–300.
_BUNDLE_FACTORS = (
    (1, 1.0),
    (2, 2.0),
    (3, 2.2),
    (4, 2.4),
    (5, 2.7),
    (6, 2.9),
    (7, 3.0),
    (8, 3.3),
    (9, 3.8),
    (10, 4.0),
    (12, 4.3),
    (14, 4.6),
    (16, 5.0),
    (18, 5.3),
    (20, 5.6),
    (24, 6.0),
    (28, 6.5),
    (32, 6.9),
    (36, 7.4),
    (40, 7.7),
    (45, 8.1),
    (50, 8.5),
    (55, 8.9),
    (60, 9.3),
    (65, 9.7),
    (70, 10.1),
    (75, 10.5),
    (80, 10.9),
    (90, 11.6),
    (100, 12.2),
    (125, 13.7),
    (150, 15.0),
    (175, 16.1),
    (200, 17.2),
    (250, 19.3),
    (300, 21.0),
)


def mapped_segment_hops(instance_name, hop_item_type, instances=None):
    """
    Ordered ``(segment_name, direction)`` hops for a cable or conductor.

    Reads ``{instance_name}.{segment}`` rows whose ``item_type`` is
    ``hop_item_type`` (``cable-segment`` or ``conductor-segment``) and sorts
    by ``segment_order``. ``direction`` is ``"ab"`` or ``"ba"``.
    """
    if instance_name in [None, ""]:
        return []
    if instances is None:
        instances = instances_list.read()
    hops = []
    for hop in instances:
        if hop.get("item_type") != hop_item_type:
            continue
        if hop.get("instance_name") != f"{instance_name}.{hop.get('segment_group')}":
            continue
        raw = (hop.get("segment_order") or "").strip()
        if "-" not in raw:
            continue
        order_str, direction = raw.split("-", 1)
        try:
            order = int(order_str)
        except ValueError:
            continue
        if direction not in ("ab", "ba"):
            continue
        hops.append((order, hop.get("segment_group"), direction))
    hops.sort()
    return [(seg_name, direction) for _, seg_name, direction in hops]


def _parse_length_inches(raw):
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) and value > 0 else None
    if raw in [None, ""]:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    match = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-z\"']*)$", text)
    if not match:
        return None
    value = float(match.group(1))
    if not math.isfinite(value) or value <= 0:
        return None
    factor = _LENGTH_TO_INCHES.get(match.group(2) or "in")
    return value * factor if factor else None


def _awg_diameter_inches(raw):
    if raw in [None, ""]:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    aught = re.match(r"^([1-4])\s*/\s*0", text)
    if aught:
        gauge = -int(aught.group(1))
    else:
        match = re.match(r"^(-?[0-9]+)\s*awg$", text) or re.match(
            r"^awg\s*(-?[0-9]+)$", text
        )
        if not match:
            return None
        gauge = int(match.group(1))
    if gauge > 40 or gauge < -4:
        return None
    return 0.005 * (92 ** ((36 - gauge) / 39))


def _parse_jsonish(raw):
    if isinstance(raw, dict):
        return raw
    if raw in [None, ""]:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _bundle_factor(count):
    if count <= 1:
        return 1.0
    for i, (n_i, beta_i) in enumerate(_BUNDLE_FACTORS):
        if n_i == count:
            return beta_i
        if n_i > count:
            n_0, beta_0 = _BUNDLE_FACTORS[i - 1]
            return beta_0 + (beta_i - beta_0) * (count - n_0) / (n_i - n_0)
    n_0, beta_0 = _BUNDLE_FACTORS[-2]
    n_1, beta_1 = _BUNDLE_FACTORS[-1]
    return beta_0 + (beta_1 - beta_0) * (count - n_0) / (n_1 - n_0)


def _bundle_diameter(diameters):
    ds = [float(d) for d in diameters if d is not None and float(d) > 0]
    n = len(ds)
    if n == 0:
        return 0.0
    return (sum(ds) / n) * _bundle_factor(n)


def _child_dicts(node):
    children = []
    if not isinstance(node, dict):
        return children
    for key, value in node.items():
        if key in _ATTRIBUTES_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            children.append(value)
        elif isinstance(value, list):
            children.extend(item for item in value if isinstance(item, dict))
    return children


def _node_od(node):
    if not isinstance(node, dict):
        return None
    props = node.get("properties")
    props = props if isinstance(props, dict) else {}
    stated = _parse_length_inches(props.get("od"))
    child_ods = []
    for child in _child_dicts(node):
        child_od = _node_od(child)
        if child_od:
            child_ods.append(child_od)
    packed = _bundle_diameter(child_ods) if child_ods else None
    wall = _parse_length_inches(props.get("thickness")) or 0.0
    if packed:
        needed = packed + 2.0 * wall
        if stated and stated >= needed:
            return stated
        return needed
    if stated:
        return stated
    if node.get("conductor") is True:
        return _awg_diameter_inches(props.get("gauge") or props.get("awg"))
    return None


def _load_cable_attributes(cable_instance_name, cable_row=None):
    attributes_path = os.path.join(
        fileio.dirpath(None),
        "instance_data",
        "cable",
        cable_instance_name,
        "attributes.json",
    )
    if os.path.isfile(attributes_path):
        with open(attributes_path, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
    raw = None
    if cable_row is not None:
        raw = cable_row.get("attributes_json")
    if raw in [None, ""]:
        raw = instances_list.attribute_of(cable_instance_name, "attributes_json")
    parsed = _parse_jsonish(raw)
    if parsed:
        return parsed
    raise ValueError(
        f"Cable '{cable_instance_name}' has no attributes JSON, so its outer "
        "diameter cannot be estimated. Pull the cable with cable_utils.new_cable "
        "so instance_data includes an attributes file with od or gauge."
    )


def cable_jacket_od(cable_instance_name, cable_row=None):
    """
    Jacket outer diameter of a cable instance, in inches.

    Same OD used when packing cables into a segment bundle: a stated jacket
    ``od``, or a pack of member ``od`` / AWG values plus jacket wall.

    **Raises:**
    - `ValueError`: If the cable has no attributes JSON or no usable OD.
    """
    od = _node_od(_load_cable_attributes(cable_instance_name, cable_row))
    if not od:
        raise ValueError(
            f"Cable '{cable_instance_name}' has no usable od or gauge in its "
            "attributes JSON, so its outer diameter cannot be estimated."
        )
    return od


def _conductor_list_path(cable_instance_name):
    return os.path.join(
        fileio.dirpath(None),
        "instance_data",
        "cable",
        cable_instance_name,
        "conductors.tsv",
    )


def _conductor_node_od(node, identifier, key=None):
    if not isinstance(node, dict):
        return None
    if key == identifier and node.get("conductor") is True:
        return _node_od(node)
    for child_key, value in node.items():
        if child_key in _ATTRIBUTES_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            found = _conductor_node_od(value, identifier, child_key)
            if found:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _conductor_node_od(item, identifier)
                    if found:
                        return found
    return None


def _od_from_instance(instance):
    stated = _parse_length_inches(instance.get("od")) or _parse_length_inches(
        instance.get("diameter")
    )
    if stated:
        return stated
    from_gauge = _awg_diameter_inches(instance.get("gauge") or instance.get("awg"))
    if from_gauge:
        return from_gauge
    attrs = _parse_jsonish(instance.get("attributes_json"))
    if attrs:
        found = _node_od(attrs)
        if found:
            return found
    return None


def conductor_od(conductor, instances=None):
    """
    Outer diameter of a conductor instance, in inches.

    Assigned conductors take OD from the parent cable's conductor list or
    attributes JSON. Unassigned conductors use their own ``od`` / ``diameter`` /
    gauge, then 0.2 in if nothing is stated (that assumption is printed).

    **Raises:**
    - `ValueError`: If the conductor is assigned to a cable conductor that has
        no ``od`` or gauge.
    """
    name = conductor.get("instance_name")
    cable_name = conductor.get("cable_group")
    identifier = conductor.get("cable_identifier")
    if instances is None:
        instances = instances_list.read()
    by_name = {row.get("instance_name"): row for row in instances}
    if cable_name not in ["", None] and identifier not in ["", None]:
        list_path = _conductor_list_path(cable_name)
        if os.path.isfile(list_path):
            row = _conductor_row_for_identifier(
                fileio.read_tsv(list_path), identifier, cable_name
            )
            stated = _parse_length_inches(row.get("od"))
            if stated:
                return stated
            from_gauge = _awg_diameter_inches(row.get("gauge") or row.get("awg"))
            if from_gauge:
                return from_gauge
        cable_row = by_name.get(cable_name)
        found = _conductor_node_od(
            _load_cable_attributes(cable_name, cable_row), identifier
        )
        if found:
            return found
        raise ValueError(
            f"Conductor '{name}' is assigned to '{identifier}' of cable "
            f"'{cable_name}', but that conductor has no od or gauge."
        )
    found = _od_from_instance(conductor)
    if found:
        return found
    cli.warn(
        f"Could not find od/gauge for conductor '{name}' "
        "(not assigned to a cable); assuming 0.2 in."
    )
    return 0.2


def calculate_bundle_diameter(segment_instance_name):
    """
    Use this when a harness build needs the outer diameter of one segment from the cables on that segment.

    Estimates the outer diameter of a segment from the cables it carries.

    Collects every cable mapped onto ``segment_instance_name`` (via
    ``cable-segment`` hops from ``map_cables_and_conductors_to_segments``) and
    reads each cable's jacket OD from its attributes JSON — a stated ``od``, or
    a pack of member ``od`` / AWG values when the jacket does not give one.
    Conductors on the segment that are not inside one of those cables (broken
    out, or never assigned) are included by their own conductor OD. If an
    unassigned conductor has no ``od``, ``diameter``, gauge, or attributes JSON,
    it is counted as 0.2 in and that assumption is printed.

    Bundle OD is ``d_av * β``: average member OD times Stringer's empirical
    bundle factor for that member count, linearly interpolated where the table
    has no exact entry. The result is written to the segment's ``diameter``
    column (inches) and returned.

    Stringer, E. J. (Rockwell International Corp.). "Calculating Wire-Bundle
    Diameter." NASA Tech Briefs 3, no. 1 (June 1978): 127. Tech Brief
    B78-10119. Report MSC-16378.
    https://ntrs.nasa.gov/citations/19780000119

    Call this after ``map_cables_and_conductors_to_segments``.

    **Args:**
    - `segment_instance_name` (str): Instance name of the segment to size.

    **Returns:**
    - `float`: Estimated bundle OD in inches.

    **Raises:**
    - `ValueError`: If the name is blank, the instance is missing or is not a
        segment, a cable on the segment has no usable OD, or an assigned
        conductor has no ``od`` / gauge.
    """
    if segment_instance_name in [None, ""]:
        raise ValueError("segment_instance_name is required but blank")

    instances = instances_list.read()
    by_name = {row.get("instance_name"): row for row in instances}
    segment = by_name.get(segment_instance_name)
    if segment is None:
        raise ValueError(f"Segment instance '{segment_instance_name}' not found")
    if segment.get("item_type") != "segment":
        raise ValueError(
            f"Instance '{segment_instance_name}' exists but is not a segment "
            f"(item_type='{segment.get('item_type')}')"
        )

    member_ods = []
    cables_on_segment = set()
    for instance in instances:
        if instance.get("item_type") != "cable":
            continue
        hop = by_name.get(f"{instance.get('instance_name')}.{segment_instance_name}")
        if hop is None:
            continue
        if hop.get("item_type") != "cable-segment":
            continue
        if hop.get("segment_group") != segment_instance_name:
            continue
        cable_name = instance.get("instance_name")
        cables_on_segment.add(cable_name)
        member_ods.append(cable_jacket_od(cable_name, instance))

    for instance in instances:
        if instance.get("item_type") != "conductor":
            continue
        hop = by_name.get(f"{instance.get('instance_name')}.{segment_instance_name}")
        if hop is None:
            continue
        if hop.get("item_type") != "conductor-segment":
            continue
        if hop.get("segment_group") != segment_instance_name:
            continue
        cable_group = instance.get("cable_group")
        if cable_group not in ["", None] and cable_group in cables_on_segment:
            continue
        member_ods.append(conductor_od(instance, instances))

    diameter = round(_bundle_diameter(member_ods), 4)
    instances_list.modify(segment_instance_name, {"diameter": diameter})
    return diameter
