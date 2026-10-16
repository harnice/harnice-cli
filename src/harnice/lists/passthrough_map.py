import csv
import heapq
from collections import defaultdict

from harnice import cli, fileio
from harnice.lists import cached_tsv, signals_list
from harnice.project_types import chtype, system
from harnice.utils import system_utils


# ``COLUMNS``: header order for ``passthrough map`` (passthrough channel identity + optional mapping).
# ``_PASSTHROUGH_CHANNEL_IDENTITY_COLUMNS``: subset filled by ``new()`` from signals lists.
COLUMNS = [
    "A-side_device_refdes",
    "A-side_device_channel_id",
    "A-side_device_channel_type",
    "B-side_device_refdes",
    "B-side_device_channel_id",
    "B-side_device_channel_type",
    "passthrough_device_refdes",
    "passthrough_channel_id",
    "A-passthrough_channel_type",
    "B-passthrough_channel_type",
    "from_channel_type",  # channel-map from type
    "from-passthrough_channel_type",  # passthrough face on the same side as from
    "to-passthrough_channel_type",  # passthrough face on the same side as to
    "to_channel_type",  # channel-map to type
    "requirement",  # user route() step number for this passthrough-channel mapping
    "satisfaction",  # resolve() route() step number (always >= requirement when both set)
    "is_imaginary",  # TRUE if this mapping was minted because no real passthrough channel was available
    "has_imaginary",  # TRUE if this passthrough device has any imaginary channel mappings
    "manual_map_passthrough_python_equiv",  # passthrough_map.route() that would form this requirement
]

PASSTHROUGH_ROUTING_CONTEXT_COLUMNS = [
    "group_of_connected_harnesses",
    "from_channel_type",
    "to_channel_type",
    "passthrough_device_refdes",
    "A-side_harness_refdes",
    "B-side_harness_refdes",
    "directionality",  # 1: from near A / to near B; -1: from near B / to near A; 0: either (reversible)
    "availables",  # passthrough channels that obey this row's directionality for the from→to pair
]

# Per-(device_refdes, channel_id) requirement counter for passthrough_map.route().
_channel_requirement_counters = {}

# Per-(device_refdes, channel_id) satisfaction counter for resolve(); starts at 1 per channel.
_channel_satisfaction_counters = {}

# Imaginary channel unique identifier (when an imaginary channel that is not required is minted, it gets a sequential uuid)
imaginary_counter = 0

# Lookup dictionaries storing which harness each connector of each passthrough or channel is part of
passthrough_harness_lookup = {}
channel_harness_lookup = {}
# Actual connector_id pair per passthrough device, mapped onto internal A/B labels.
passthrough_face_names = {}
# Cached ``{channel_id: {connector_id: channel_type}}`` per passthrough device.
_passthrough_channels_cache = {}

_PASSTHROUGH_CHANNEL_IDENTITY_COLUMNS = frozenset(
    {
        "passthrough_device_refdes",
        "passthrough_channel_id",
        "A-passthrough_channel_type",
        "B-passthrough_channel_type",
    }
)


def _load_passthrough_channels(refdes):
    """Return ``{channel_id: {connector_id: channel_type}}`` for a placed device."""
    if refdes in _passthrough_channels_cache:
        return _passthrough_channels_cache[refdes]
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        _passthrough_channels_cache[refdes] = {}
        return {}
    raw = signals_list.passthrough_channels(path)
    _passthrough_channels_cache[refdes] = raw
    if raw and refdes not in passthrough_face_names:
        first = next(iter(raw.values()))
        passthrough_face_names[refdes] = signals_list.ordered_passthrough_faces(first)
    return raw


def _algo_sides(refdes, channel_id=None, sides=None):
    """Map a channel's connector types onto internal A/B labels."""
    if sides is None:
        raw = _load_passthrough_channels(refdes)
        if channel_id:
            sides = raw.get(channel_id, {})
        else:
            sides = next(iter(raw.values()), {})
    a, b = passthrough_face_names.get(refdes) or signals_list.ordered_passthrough_faces(
        sides
    )
    if refdes not in passthrough_face_names and a and b:
        passthrough_face_names[refdes] = (a, b)
    return {"A": sides.get(a, ""), "B": sides.get(b, "")}


def _cell(row, key):
    return (row.get(key) or "").strip()


def _directionality_from_repeat(refdes, repeat_channel_id, channel_id=None):
    """Translate an author-written repeat (the from-face) into 1 / -1."""
    if repeat_channel_id in (None, "", 0, "either"):
        return None
    want = str(repeat_channel_id).strip()
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        return None
    raw = _load_passthrough_channels(refdes)
    target_channel = channel_id if channel_id in (raw or {}) else None
    connector_id = None
    for row in signals_list.read(path):
        row_channel = _cell(row, "channel_id")
        if target_channel and row_channel != target_channel:
            continue
        if row_channel not in raw:
            continue
        if _cell(row, "repeat_channel_id") == want:
            connector_id = _cell(row, "connector_id")
            if not target_channel:
                target_channel = row_channel
            break
    if connector_id is None:
        return None
    a, b = passthrough_face_names.get(refdes) or signals_list.ordered_passthrough_faces(
        raw.get(target_channel, {})
    )
    if connector_id == a:
        return 1
    if connector_id == b:
        return -1
    return None


def _repeat_of_orientation(refdes, orientation, channel_id=None):
    """Author-written repeat on the from-face for this orientation."""
    raw = _load_passthrough_channels(refdes)
    if not raw:
        return None
    target = channel_id if channel_id in raw else next(iter(raw))
    a, b = passthrough_face_names.get(refdes) or signals_list.ordered_passthrough_faces(
        raw.get(target, {})
    )
    face = a if orientation in (1, 0) else b
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        return None
    for row in signals_list.read(path):
        if _cell(row, "channel_id") != target:
            continue
        if _cell(row, "connector_id") == face:
            return _cell(row, "repeat_channel_id") or None
    return None


def read():
    """Return the passthrough map (cached)."""
    return cached_tsv.read(fileio.path("passthrough map"))


def next_requirement():
    """
    Allocate the next global requirement number (one per assigned passthrough channel).

    Updates ``system.passthrough_highest_requirement`` so callers can later read the
    largest requirement number issued so far via ``passthrough_map.highest_requirement()``
    or ``system.passthrough_highest_requirement``.
    """
    system.passthrough_highest_requirement = (
        int(system.passthrough_highest_requirement or 0) + 1
    )
    return system.passthrough_highest_requirement


def highest_requirement():
    """Return the largest requirement number issued so far (0 if none)."""
    return int(system.passthrough_highest_requirement or 0)


def next_satisfaction(channel_key):
    """Allocate the next satisfaction step for one mapped channel (1-based per channel)."""
    n = int(_channel_satisfaction_counters.get(channel_key, 0)) + 1
    _channel_satisfaction_counters[channel_key] = n
    return n


def _passthrough_channel_obeys_directionality(
    from_channel_type, to_channel_type, directionality, a_type, b_type
):
    """
    Whether a passthrough through-channel can carry from→to in this directionality.

    directionality 1:  from mates with A, to mates with B
    directionality -1: from mates with B, to mates with A
    directionality 0:  either orientation works (reversible pairs)
    """
    def port_mates(port_type, channel_type):
        return bool(port_type and port_type in chtype.compatibles(channel_type))

    if directionality == 1:
        ok = port_mates(a_type, from_channel_type) and port_mates(
            b_type, to_channel_type
        )
        return ok, "dir=1: from↔A and to↔B" if ok else "dir=1: no from↔A and to↔B"
    if directionality == -1:
        ok = port_mates(b_type, from_channel_type) and port_mates(
            a_type, to_channel_type
        )
        return ok, "dir=-1: from↔B and to↔A" if ok else "dir=-1: no from↔B and to↔A"
    if directionality == 0:
        forward = port_mates(a_type, from_channel_type) and port_mates(
            b_type, to_channel_type
        )
        reverse = port_mates(b_type, from_channel_type) and port_mates(
            a_type, to_channel_type
        )
        ok = forward or reverse
        if forward and reverse:
            return True, "dir=0: both orientations"
        if forward:
            return True, "dir=0: forward (from↔A, to↔B)"
        if reverse:
            return True, "dir=0: reverse (from↔B, to↔A)"
        return False, "dir=0: neither orientation"
    return False, f"unknown directionality={directionality!r}"


def _write_passthrough_map(rows):
    def stamp_imaginary_flags(rows):
        """Fill ``is_imaginary`` / ``has_imaginary`` on every row from current mappings."""
        devices_with_imaginary = set()
        for row in rows:
            channel_id = str(row.get("passthrough_channel_id") or "")
            if str(row.get("is_imaginary") or "").strip().upper() == "TRUE" or channel_id.startswith("imaginary-"):
                row["is_imaginary"] = "TRUE"
                devices_with_imaginary.add(row.get("passthrough_device_refdes"))
            else:
                row["is_imaginary"] = ""
        for row in rows:
            disc = row.get("passthrough_device_refdes")
            row["has_imaginary"] = (
                "TRUE" if disc in devices_with_imaginary else ""
            )

    stamp_imaginary_flags(rows)
    normalized = [
        {column: row.get(column, "") for column in COLUMNS} for row in rows
    ]
    cached_tsv.write(fileio.path("passthrough map"), COLUMNS, normalized)


def _write_routing_context(rows):
    system.passthrough_routing_context = rows
    with open(
        fileio.path("passthrough routing context"), "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=PASSTHROUGH_ROUTING_CONTEXT_COLUMNS, delimiter="\t"
        )
        writer.writeheader()
        for line in rows:
            writer.writerow(
                {
                    column: line.get(column, "")
                    for column in PASSTHROUGH_ROUTING_CONTEXT_COLUMNS
                }
            )


def _context_row_matches_pair(row, group_of_connected_harnesses, from_channel_type, to_channel_type):
    if row.get("group_of_connected_harnesses") != group_of_connected_harnesses:
        return False
    for a, b in (
        (row.get("from_channel_type"), from_channel_type),
        (row.get("to_channel_type"), to_channel_type),
    ):
        parsed_a = chtype.parse(a) if a not in [None, ""] else None
        parsed_b = chtype.parse(b) if b not in [None, ""] else None
        if parsed_a is None or parsed_a != parsed_b:
            return False
    return True


def new():
    """
    Create passthrough channel rows from placed-device signals lists.

    Rebuilds ``system.passthrough_routing_context`` as one row per unique
    (from_channel_type, to_channel_type) pair within each ``group_of_connected_harnesses``, per
    passthrough device, per directionality (1 / -1, or 0 if reversible), with an
    ``availables`` count of passthrough channels that obey that directionality.
    Does not route channels or fill channel-map chains (see ``resolve()``).
    """

    from harnice.lists import channel_map

    passthrough_channels_in_system = []

    connector_list = fileio.read_tsv("system connector list")

    global passthrough_harness_lookup
    global channel_harness_lookup
    global passthrough_face_names
    global _passthrough_channels_cache
    global _channel_requirement_counters
    global _channel_satisfaction_counters

    system.passthrough_highest_requirement = 0
    _channel_requirement_counters = {}
    _channel_satisfaction_counters = {}
    passthrough_harness_lookup = {}
    channel_harness_lookup = {}
    passthrough_face_names = {}
    _passthrough_channels_cache = {}

    harness_of = {}
    group_of_device = {}
    for connector in connector_list:
        refdes = (connector.get("device_refdes") or "").strip()
        connector_id = (connector.get("device_connector") or "").strip()
        harness_refdes = connector.get("mating_harness_refdes")
        if not refdes:
            continue
        channel_harness_lookup[(refdes, connector_id)] = harness_refdes
        harness_of.setdefault(refdes, {})[connector_id] = harness_refdes
        group = (connector.get("group_of_connected_harnesses") or "").strip()
        if group and refdes not in group_of_device:
            group_of_device[refdes] = group

    seen_refdes = set()
    passthroughs_in_system_by_group = {}
    for connector in connector_list:
        refdes = (connector.get("device_refdes") or "").strip()
        if not refdes or refdes in seen_refdes:
            continue
        seen_refdes.add(refdes)
        raw = _load_passthrough_channels(refdes)
        if not raw:
            continue

        first_sides = next(iter(raw.values()))
        face_a, face_b = signals_list.ordered_passthrough_faces(first_sides)
        passthrough_face_names[refdes] = (face_a, face_b)
        sides_harnesses = harness_of.get(refdes, {})
        passthrough_harness_lookup[refdes] = {
            "A": sides_harnesses.get(face_a, ""),
            "B": sides_harnesses.get(face_b, ""),
        }
        group_of_connected_harnesses = group_of_device.get(refdes, "")
        harness_sides = passthrough_harness_lookup[refdes]
        if group_of_connected_harnesses:
            passthroughs_in_system_by_group.setdefault(group_of_connected_harnesses, {})[
                refdes
            ] = {
                "passthrough_device_refdes": refdes,
                "A-side_harness_refdes": harness_sides.get("A", ""),
                "B-side_harness_refdes": harness_sides.get("B", ""),
            }

        for channel_id, sides in raw.items():
            algo = _algo_sides(refdes, channel_id, sides)
            channel_row = {
                "passthrough_device_refdes": refdes,
                "passthrough_channel_id": channel_id,
                "A-passthrough_channel_type": algo["A"],
                "B-passthrough_channel_type": algo["B"],
                "A-side_harness_refdes": harness_sides.get("A", ""),
                "B-side_harness_refdes": harness_sides.get("B", ""),
                "is_imaginary": "",
                "has_imaginary": "",
            }
            passthrough_channels_in_system.append(channel_row)

    _write_passthrough_map(passthrough_channels_in_system)

    # Pass 1: unique (from_channel_type, to_channel_type) pairs per group_of_connected_harnesses
    unique_pairs_by_group_of_connected_harnesses = {}
    for channel in channel_map.read():
        from_id = channel.get("from_device_channel_id")
        to_id = channel.get("to_device_channel_id")
        if from_id in ["", None] or to_id in ["", None]:
            continue  # channel not mapped

        group_of_connected_harnesses = (channel.get("group_of_connected_harnesses") or "").strip()
        if not group_of_connected_harnesses:
            continue

        from_channel_type = channel.get("from_channel_type")
        to_channel_type = channel.get("to_channel_type")
        from_type = chtype.parse(from_channel_type)
        to_type = chtype.parse(to_channel_type)
        if not from_type or not to_type:
            continue

        pairs_for_group = unique_pairs_by_group_of_connected_harnesses.setdefault(group_of_connected_harnesses, {})
        pair_key = (from_type, to_type)
        from_self = bool(from_type and from_type in chtype.compatibles(from_channel_type))
        to_self = bool(to_type and to_type in chtype.compatibles(to_channel_type))
        pairs_for_group[pair_key] = {
            "from_channel_type": from_channel_type,
            "to_channel_type": to_channel_type,
            "reversible": from_self or to_self,
        }


    # Pass 2: one context row per (group_of_connected_harnesses, from→to pair, passthrough, directionality)
    map_consumed = channel_map.passthroughs_consumed_as_patch_ends()
    routing_context = []
    for group_of_connected_harnesses, pairs_for_group in unique_pairs_by_group_of_connected_harnesses.items():
        passthroughs_in_group = list(
            passthroughs_in_system_by_group.get(group_of_connected_harnesses, {}).values()
        )

        for pair_info in pairs_for_group.values():
            from_channel_type = pair_info["from_channel_type"]
            to_channel_type = pair_info["to_channel_type"]
            if pair_info["reversible"]:
                directionalities = [0]
            else:
                directionalities = [1, -1]

            for passthrough_info in passthroughs_in_group:
                passthrough_device_refdes = passthrough_info.get("passthrough_device_refdes")
                raw = _load_passthrough_channels(passthrough_device_refdes)
                for directionality in directionalities:
                    availables = 0
                    for channel_id, sides in raw.items():
                        if (passthrough_device_refdes, channel_id) in map_consumed:
                            continue
                        algo = _algo_sides(passthrough_device_refdes, channel_id, sides)
                        a_type = chtype.parse(algo.get("A"))
                        b_type = chtype.parse(algo.get("B"))
                        ok, _reason = _passthrough_channel_obeys_directionality(
                            from_channel_type,
                            to_channel_type,
                            directionality,
                            a_type,
                            b_type,
                        )
                        if ok:
                            availables += 1
                    row = {
                        "group_of_connected_harnesses": group_of_connected_harnesses,
                        "from_channel_type": from_channel_type,
                        "to_channel_type": to_channel_type,
                        "passthrough_device_refdes": passthrough_device_refdes,
                        "A-side_harness_refdes": passthrough_info.get(
                            "A-side_harness_refdes", ""
                        ),
                        "B-side_harness_refdes": passthrough_info.get(
                            "B-side_harness_refdes", ""
                        ),
                        "directionality": directionality,
                        "availables": availables,
                    }
                    routing_context.append(row)

    _write_routing_context(routing_context)


def route(
    to_from_channel_device_refdes,
    to_from_channel_id,
    intended_device_refdes,
    intended_channel_id=None,
    repeat_channel_id=None,
    satisfaction=False,
):
    """
    Route a mapped channel through a passthrough device.

    Looks up the mapped channel's from→to types and group_of_connected_harnesses, finds the matching
    routing-context row(s), picks a free passthrough channel that obeys directionality,
    records the mapping on the **passthrough map**, and decrements
    ``availables`` on the matching context row (never below 0).

    ``repeat_channel_id`` is the face the from-side arrives on. Omit it to infer.

    The passthrough device must belong to the same
    ``group_of_connected_harnesses`` as the mapped channel.

    By default writes ``requirement`` (user route). With ``satisfaction=True``
    (used by ``resolve``), writes ``satisfaction`` instead.

    Returns 0 on a real assignment, -1 if an imaginary passthrough-map row was appended
    because ``availables`` was already 0.
    """

    from harnice.lists import channel_map

    global _channel_requirement_counters
    global _channel_satisfaction_counters

    def _requirement_python_equiv(
        device_refdes,
        channel_id,
        passthrough_device_refdes,
        passthrough_channel_id,
        repeat_channel_id,
    ):
        """Copy-pasteable ``passthrough_map.route()`` that would form this requirement."""
        args = [repr(device_refdes), repr(channel_id), repr(passthrough_device_refdes)]
        if passthrough_channel_id not in [None, ""]:
            args.append(f"intended_channel_id={passthrough_channel_id!r}")
        if repeat_channel_id not in [None, ""]:
            args.append(f"repeat_channel_id={repeat_channel_id!r}")
        return f"passthrough_map.route({', '.join(args)})"


    def _port_matching_channel_type(a_port, b_port, channel_type):
        """Passthrough face type that is the same channel type as ``channel_type``."""
        target = None
        if channel_type not in [None, ""]:
            try:
                target = chtype.parse(channel_type)
            except (TypeError, ValueError, SyntaxError):
                target = None
        if target is not None:
            for port in (a_port, b_port):
                if port in [None, ""]:
                    continue
                try:
                    if chtype.parse(port) == target:
                        return port
                except (TypeError, ValueError, SyntaxError):
                    if port == channel_type:
                        return port
        return channel_type or ""


    def fill_passthrough_map_assignment(
        map_row,
        channel_map_row,
        orientation,
        passthrough_channel_sides=None,
        requirement=None,
        satisfaction=None,
    ):
        """Write from/to device fields onto a passthrough-map row for the chosen orientation."""
        from_ref = channel_map_row.get("from_device_refdes")
        from_id = channel_map_row.get("from_device_channel_id")
        from_type = channel_map_row.get("from_channel_type")
        to_ref = channel_map_row.get("to_device_refdes")
        to_id = channel_map_row.get("to_device_channel_id")
        to_type = channel_map_row.get("to_channel_type")

        map_row["from_channel_type"] = from_type
        map_row["to_channel_type"] = to_type

        if orientation == 1:
            # from near A, to near B
            map_row["A-side_device_refdes"] = from_ref
            map_row["A-side_device_channel_id"] = from_id
            map_row["A-side_device_channel_type"] = from_type
            map_row["B-side_device_refdes"] = to_ref
            map_row["B-side_device_channel_id"] = to_id
            map_row["B-side_device_channel_type"] = to_type
        else:
            # orientation -1: from near B, to near A
            map_row["A-side_device_refdes"] = to_ref
            map_row["A-side_device_channel_id"] = to_id
            map_row["A-side_device_channel_type"] = to_type
            map_row["B-side_device_refdes"] = from_ref
            map_row["B-side_device_channel_id"] = from_id
            map_row["B-side_device_channel_type"] = from_type

        if passthrough_channel_sides is not None:
            map_row["A-passthrough_channel_type"] = passthrough_channel_sides.get(
                "A", map_row.get("A-passthrough_channel_type", "")
            )
            map_row["B-passthrough_channel_type"] = passthrough_channel_sides.get(
                "B", map_row.get("B-passthrough_channel_type", "")
            )

        a_port = map_row.get("A-passthrough_channel_type", "")
        b_port = map_row.get("B-passthrough_channel_type", "")
        map_row["from-passthrough_channel_type"] = _port_matching_channel_type(
            a_port, b_port, from_type
        )
        map_row["to-passthrough_channel_type"] = _port_matching_channel_type(
            a_port, b_port, to_type
        )

        if requirement is not None:
            map_row["requirement"] = requirement
        if satisfaction is not None:
            map_row["satisfaction"] = satisfaction

        map_row["manual_map_passthrough_python_equiv"] = _requirement_python_equiv(
            from_ref,
            from_id,
            map_row.get("passthrough_device_refdes"),
            map_row.get("passthrough_channel_id"),
            _repeat_of_orientation(
                map_row.get("passthrough_device_refdes"),
                orientation,
                map_row.get("passthrough_channel_id"),
            ),
        )


    if not system.passthrough_routing_context:
        raise ValueError(
            "Passthrough routing context is empty; call passthrough_map.new() first to pre-compile."
        )

    if to_from_channel_device_refdes is None or to_from_channel_id is None:
        raise ValueError(
            "Specify a mapped channel that has to and from endpoints using arguments 'to_from_channel_device_refdes' and 'to_from_channel_id'. Both are required. Doesn't matter if you reference the to- or from-side."
        )

    if intended_device_refdes is None:
        raise ValueError(
            "Specify a passthrough device by its refdes using argument 'intended_device_refdes'"
        )

    preferred_directionality = _directionality_from_repeat(
        intended_device_refdes, repeat_channel_id, intended_channel_id
    )

    this_channel_key = (to_from_channel_device_refdes, to_from_channel_id)

    channel_map_row = None
    for row in channel_map.read():
        if this_channel_key in (
            (row.get("from_device_refdes"), row.get("from_device_channel_id")),
            (row.get("to_device_refdes"), row.get("to_device_channel_id")),
        ):
            if row.get("from_device_channel_id") in ["", None] or row.get(
                "to_device_channel_id"
            ) in ["", None]:
                continue
            channel_map_row = row
            break
    if channel_map_row is None:
        raise ValueError(
            f"Channel '{this_channel_key}' is not mapped to another endpoint. "
            "Complete your channel map before trying to route passthroughs."
        )

    group_of_connected_harnesses = (channel_map_row.get("group_of_connected_harnesses") or "").strip()
    passthrough_groups = channel_map.groups_of_device(intended_device_refdes)
    if not group_of_connected_harnesses or group_of_connected_harnesses not in passthrough_groups:
        raise ValueError(
            f"Cannot route {this_channel_key} through "
            f"{intended_device_refdes!r}: passthrough is not in the mapped "
            "channel's group of connected harnesses "
            f"(channel group {group_of_connected_harnesses!r}, "
            f"passthrough groups {sorted(passthrough_groups)})"
        )
    from_channel_type = channel_map_row.get("from_channel_type")
    to_channel_type = channel_map_row.get("to_channel_type")

    # Context rows for this from→to pair × passthrough (optionally filtered by directionality)
    relevant_context_rows = []
    for row in system.passthrough_routing_context:
        if row.get("passthrough_device_refdes") != intended_device_refdes:
            continue
        if not _context_row_matches_pair(
            row, group_of_connected_harnesses, from_channel_type, to_channel_type
        ):
            continue
        row_dir = row.get("directionality")
        try:
            row_dir = int(row_dir)
        except (TypeError, ValueError):
            pass
        if preferred_directionality is not None and row_dir not in (
            preferred_directionality,
            0,
        ):
            continue
        relevant_context_rows.append(row)

    if not relevant_context_rows:
        # Distinguish "pair not in context at all" vs "passthrough not in this group"
        pair_exists = any(
            _context_row_matches_pair(
                row, group_of_connected_harnesses, from_channel_type, to_channel_type
            )
            for row in system.passthrough_routing_context
        )
        if not pair_exists:
            raise ValueError(
                f"Channel '{this_channel_key}' has from→to types that are not in the "
                "passthrough routing context. Call passthrough_map.new() after completing the channel map."
            )
        raise ValueError(
            "No options were found for the mapped channel and passthrough device combination you tried to route. "
            "Does the passthrough exist and is it part of the same group of connected harnesses as the mapped channel?"
        )

    def _row_availables(row):
        try:
            return int(row.get("availables") or 0)
        except (TypeError, ValueError):
            return 0

    def _availables_for_orientation(orientation):
        total = 0
        for row in relevant_context_rows:
            row_dir = row.get("directionality")
            try:
                row_dir = int(row_dir)
            except (TypeError, ValueError):
                pass
            if row_dir == orientation or row_dir == 0:
                total += _row_availables(row)
        return total

    total_availables = sum(_row_availables(row) for row in relevant_context_rows)

    consumed = set()
    for row in read():
        if row.get("passthrough_device_refdes") != intended_device_refdes:
            continue
        channel_id = row.get("passthrough_channel_id") or ""
        if str(channel_id).startswith("imaginary-"):
            consumed.add(channel_id)
            continue
        if row.get("A-side_device_refdes") not in [None, ""] and row.get(
            "A-side_device_channel_id"
        ) not in [None, ""]:
            consumed.add(channel_id)
            continue
        if row.get("B-side_device_refdes") not in [None, ""] and row.get(
            "B-side_device_channel_id"
        ) not in [None, ""]:
            consumed.add(channel_id)
    for refdes, channel_id in channel_map.passthroughs_consumed_as_patch_ends():
        if refdes == intended_device_refdes:
            consumed.add(channel_id)
    raw_passthroughs = _load_passthrough_channels(intended_device_refdes)
    passthrough_channels = {
        channel_id: _algo_sides(intended_device_refdes, channel_id, sides)
        for channel_id, sides in raw_passthroughs.items()
    }

    # Build candidate physical channels that obey directionality, are free,
    # and have remaining availables on a matching context row.
    candidates = []  # (channel_id, orientation, sides)
    for channel_id, sides in passthrough_channels.items():
        if (
            intended_channel_id is not None
            and channel_id != intended_channel_id
        ):
            continue
        if channel_id in consumed:
            if intended_channel_id is not None:
                raise ValueError(
                    f"You tried to route mapped channel {this_channel_key} through passthrough "
                    f"channel {(intended_device_refdes, channel_id)} that has already been consumed. "
                    "That channel may already be a dual-map patch end, or routed with an earlier "
                    "passthrough_map.route(). Call this before passthrough_map.resolve()."
                )
            continue
        a_type = chtype.parse(sides.get("A"))
        b_type = chtype.parse(sides.get("B"))
        forward_ok, _ = _passthrough_channel_obeys_directionality(
            from_channel_type, to_channel_type, 1, a_type, b_type
        )
        reverse_ok, _ = _passthrough_channel_obeys_directionality(
            from_channel_type, to_channel_type, -1, a_type, b_type
        )
        orientation = None
        if preferred_directionality == 1 and forward_ok:
            orientation = 1
        elif preferred_directionality == -1 and reverse_ok:
            orientation = -1
        elif preferred_directionality in [0, None]:
            if forward_ok:
                orientation = 1
            elif reverse_ok:
                orientation = -1
        elif forward_ok:
            orientation = 1
        elif reverse_ok:
            orientation = -1
        if orientation is None:
            continue
        if _availables_for_orientation(orientation) <= 0:
            continue
        candidates.append((channel_id, orientation, sides))

    if intended_channel_id is not None:
        if intended_channel_id not in passthrough_channels:
            # Allow assigning a previously unknown id only in imaginary path; otherwise error
            if total_availables > 0:
                raise ValueError(
                    "You tried to route a mapped channel through a passthrough channel that does not exist "
                    "on the device. Check for a typo in the intended channel field? "
                    "Check that the channel is actually a passthrough on that device?"
                )
        elif not candidates:
            # Specified channel exists but does not obey directionality
            raise ValueError(
                f"Passthrough channel '{intended_channel_id}' on "
                f"'{intended_device_refdes}' does not obey the directionality rule "
                f"for from={from_channel_type!r} to={to_channel_type!r}."
            )

    map_rows = read()

    def _next_step():
        if satisfaction:
            return next_satisfaction(this_channel_key)
        step = next_requirement()
        _channel_requirement_counters[this_channel_key] = step
        return step

    # --- Imaginary path: no availables left ---
    if total_availables <= 0:
        step = _next_step()
        orientation = (
            preferred_directionality if preferred_directionality in (1, -1) else 1
        )
        prefix = "imaginary-satisfaction" if satisfaction else "imaginary-requirement"
        imaginary_id = f"{prefix}-{step}"
        # Same type on each A/B side as the device sitting there, so the
        # from/to type path reads type X, type X, type Y, type Y.
        if orientation == 1:
            a_port = from_channel_type
            b_port = to_channel_type
        else:
            a_port = to_channel_type
            b_port = from_channel_type

        imaginary_row = {column: "" for column in COLUMNS}
        imaginary_row["passthrough_device_refdes"] = intended_device_refdes
        imaginary_row["passthrough_channel_id"] = (
            intended_channel_id
            if intended_channel_id is not None
            else imaginary_id
        )
        imaginary_row["A-passthrough_channel_type"] = a_port
        imaginary_row["B-passthrough_channel_type"] = b_port
        imaginary_row["is_imaginary"] = "TRUE"
        fill_kwargs = (
            {"satisfaction": step} if satisfaction else {"requirement": step}
        )
        fill_passthrough_map_assignment(
            imaginary_row,
            channel_map_row,
            orientation,
            **fill_kwargs,
        )
        map_rows.append(imaginary_row)
        _write_passthrough_map(map_rows)
        # context availables unchanged (already 0; do not go negative)
        _write_routing_context(list(system.passthrough_routing_context))
        return -1

    # --- Real path: need a free physical channel ---
    if not candidates:
        raise ValueError(
            f"Context reports availables={total_availables} for "
            f"{intended_device_refdes} with from={from_channel_type!r} to={to_channel_type!r}, "
            "but no free passthrough channel obeys directionality. "
            "Re-run passthrough_map.new() or check for map/context desync."
        )

    step = _next_step()
    chosen_id, orientation, sides = candidates[0]
    fill_kwargs = {"satisfaction": step} if satisfaction else {"requirement": step}

    # Update passthrough map row for this channel
    updated_map = False
    for map_row in map_rows:
        if (
            map_row.get("passthrough_device_refdes") == intended_device_refdes
            and map_row.get("passthrough_channel_id") == chosen_id
        ):
            fill_passthrough_map_assignment(
                map_row,
                channel_map_row,
                orientation,
                sides,
                **fill_kwargs,
            )
            map_row["is_imaginary"] = ""
            updated_map = True
            break
    if not updated_map:
        # Channel exists on the passthrough device but wasn't in map TSV — append
        new_row = {column: "" for column in COLUMNS}
        new_row["passthrough_device_refdes"] = intended_device_refdes
        new_row["passthrough_channel_id"] = chosen_id
        new_row["is_imaginary"] = ""
        fill_passthrough_map_assignment(
            new_row,
            channel_map_row,
            orientation,
            sides,
            **fill_kwargs,
        )
        map_rows.append(new_row)
    _write_passthrough_map(map_rows)

    # Decrement availables on the matching context row (never below 0)
    updated_context = []
    decremented = False
    for row in system.passthrough_routing_context:
        updated = dict(row)
        if (
            not decremented
            and row.get("passthrough_device_refdes") == intended_device_refdes
            and _context_row_matches_pair(
                row, group_of_connected_harnesses, from_channel_type, to_channel_type
            )
        ):
            row_dir = row.get("directionality")
            try:
                row_dir = int(row_dir)
            except (TypeError, ValueError):
                pass
            # Prefer exact orientation match; dir=0 also accepts any orientation
            if row_dir == orientation or row_dir == 0:
                avail = _row_availables(row)
                if avail > 0:
                    updated["availables"] = avail - 1
                    decremented = True
        updated_context.append(updated)

    if not decremented:
        raise ValueError(
            f"Could not decrement availables for {intended_device_refdes} "
            f"orientation={orientation}. Context may be out of sync; call passthrough_map.new()."
        )

    _write_routing_context(updated_context)
    return 0


def resolve():
    """
    Complete passthrough routing for each mapped channel (channel-map order).

    Uses the routing context (filtered to group_of_connected_harnesses + from→to pair) to find the
    fewest passthrough channels that connect from_harness → optional ordered
    ``requirement`` waypoints → to_harness. Prefers paths with remaining
    ``availables``; if none exist, allows ``availables == 0`` (imaginaries).

    Gap fills call ``route(..., satisfaction=True)``. Existing requirement rows
    get a ``satisfaction`` stamp. Writes ``chain_of_connectors`` and
    ``chain_of_harnesses`` on each mapped channel-map row from the resulting path.

    Stamps ``is_imaginary`` / ``has_imaginary`` on the passthrough map. Prints one
    warning per passthrough that needed imaginary channels to satisfy the map.

    No-op when ``passthrough_map.new()`` found no harness topology (empty parent
    diagram / no harness-mated connectors): there is nothing to resolve.
    """
    from harnice.lists import channel_map

    def _requirements_for_mapped_channel(channel_map_row, map_rows=None):
        """Passthrough-map rows with a requirement belonging to this mapped channel."""
        from_key = (
            channel_map_row.get("from_device_refdes"),
            channel_map_row.get("from_device_channel_id"),
        )
        to_key = (
            channel_map_row.get("to_device_refdes"),
            channel_map_row.get("to_device_channel_id"),
        )
        belonging = []
        for row in map_rows if map_rows is not None else read():
            req = row.get("requirement")
            if req in [None, ""]:
                continue
            a_key = (
                row.get("A-side_device_refdes"),
                row.get("A-side_device_channel_id"),
            )
            b_key = (
                row.get("B-side_device_refdes"),
                row.get("B-side_device_channel_id"),
            )
            if {from_key, to_key} == {a_key, b_key}:
                belonging.append(row)
        belonging.sort(key=lambda r: int(r.get("requirement") or 0))
        return belonging


    def _requirement_orientation(req_row, channel_map_row):
        """1 if from is on A side of the requirement row, else -1."""
        from_key = (
            channel_map_row.get("from_device_refdes"),
            channel_map_row.get("from_device_channel_id"),
        )
        a_key = (
            req_row.get("A-side_device_refdes"),
            req_row.get("A-side_device_channel_id"),
        )
        if from_key == a_key:
            return 1
        return -1


    def _requirement_entry_exit_harnesses(req_row, channel_map_row):
        """Return (entry_harness, exit_harness) for traveling through this requirement."""
        disc = req_row.get("passthrough_device_refdes")
        sides = passthrough_harness_lookup.get(disc, {})
        a_h = sides.get("A", "")
        b_h = sides.get("B", "")
        if _requirement_orientation(req_row, channel_map_row) == 1:
            return a_h, b_h
        return b_h, a_h


    def find_pathway(
        start_harness=None,
        end_harness=None,
        start_requirement=None,
        end_requirement=None,
        channel_map_row=None,
    ):
        """
        Find fewest passthrough channels between harnesses and/or requirements.

        Exactly one start and one end among harness/requirement args. ``channel_map_row``
        is required to filter the routing context.
        """
        def requirement_row_by_number(requirement_number, channel_map_row):
            for row in _requirements_for_mapped_channel(channel_map_row):
                try:
                    if int(row.get("requirement")) == int(requirement_number):
                        return row
                except (TypeError, ValueError):
                    continue
            raise ValueError(
                f"No passthrough-map requirement {requirement_number} for channel "
                f"{channel_map_row.get('from_device_refdes')}/"
                f"{channel_map_row.get('from_device_channel_id')}"
            )

        def context_rows_for_channel_map_row(channel_map_row, require_availables=False):
            """Routing-context rows for this mapped channel's group_of_connected_harnesses + from→to pair."""
            group_of_connected_harnesses = (channel_map_row.get("group_of_connected_harnesses") or "").strip()
            from_channel_type = channel_map_row.get("from_channel_type")
            to_channel_type = channel_map_row.get("to_channel_type")
            rows = []
            for row in system.passthrough_routing_context:
                if not _context_row_matches_pair(
                    row, group_of_connected_harnesses, from_channel_type, to_channel_type
                ):
                    continue
                if require_availables:
                    try:
                        if int(row.get("availables") or 0) <= 0:
                            continue
                    except (TypeError, ValueError):
                        continue
                rows.append(row)
            return rows


        def shortest_passthrough_path(start_harness, end_harness, context_rows):
            """
            Dijkstra: cost = (imaginary_count, passthrough_channel_count).
            Returns list of (passthrough_device_refdes, directionality) or None.
            """
            if start_harness == end_harness:
                return []

            # adjacency: harness -> list of (to_harness, disc, dir, imag_cost)
            adj = defaultdict(list)
            for row in context_rows:
                disc = row.get("passthrough_device_refdes")
                try:
                    avail = int(row.get("availables") or 0)
                except (TypeError, ValueError):
                    avail = 0
                imag = 0 if avail > 0 else 1
                a_h = row.get("A-side_harness_refdes") or ""
                b_h = row.get("B-side_harness_refdes") or ""
                try:
                    directionality = int(row.get("directionality"))
                except (TypeError, ValueError):
                    directionality = row.get("directionality")
                for start in (a_h, b_h):
                    if not start:
                        continue
                    trav = None
                    if directionality == 1:
                        if start == a_h:
                            trav = (b_h, 1)
                    elif directionality == -1:
                        if start == b_h:
                            trav = (a_h, -1)
                    elif directionality == 0:
                        if start == a_h:
                            trav = (b_h, 1)
                        elif start == b_h:
                            trav = (a_h, -1)
                    if trav is None:
                        continue
                    to_h, used_dir = trav
                    adj[start].append((to_h, disc, used_dir, imag))

            # state: (imag, hops, harness) ; path recovered via prev
            best = {start_harness: (0, 0)}
            prev = {}  # harness -> (prev_harness, disc, dir)
            heap = [(0, 0, start_harness)]
            while heap:
                imag, hops, harness = heapq.heappop(heap)
                if (imag, hops) != best.get(harness):
                    continue
                if harness == end_harness:
                    break
                for to_h, disc, used_dir, edge_imag in adj.get(harness, []):
                    n_imag = imag + edge_imag
                    n_hops = hops + 1
                    cur = best.get(to_h)
                    if cur is None or (n_imag, n_hops) < cur:
                        best[to_h] = (n_imag, n_hops)
                        prev[to_h] = (harness, disc, used_dir)
                        heapq.heappush(heap, (n_imag, n_hops, to_h))

            if end_harness not in best:
                return None

            steps = []
            cur = end_harness
            while cur != start_harness:
                if cur not in prev:
                    return None
                p_h, disc, used_dir = prev[cur]
                steps.append((disc, used_dir))
                cur = p_h
            steps.reverse()
            return steps


        if channel_map_row is None:
            raise ValueError("find_pathway requires channel_map_row")

        checksum = 0
        start_checksum = 0
        end_checksum = 0
        if start_harness is not None:
            checksum += 1
            start_checksum += 1
        if end_harness is not None:
            checksum += 1
            end_checksum += 1
        if start_requirement is not None:
            checksum += 1
            start_checksum += 1
        if end_requirement is not None:
            checksum += 1
            end_checksum += 1
        if checksum != 2 or start_checksum != 1 or end_checksum != 1:
            raise ValueError("You must define one start and one end argument")

        if start_requirement is not None:
            req_row = requirement_row_by_number(start_requirement, channel_map_row)
            _, start_harness = _requirement_entry_exit_harnesses(req_row, channel_map_row)
        if end_requirement is not None:
            req_row = requirement_row_by_number(end_requirement, channel_map_row)
            end_harness, _ = _requirement_entry_exit_harnesses(req_row, channel_map_row)

        if start_harness == end_harness:
            return []
        tight = context_rows_for_channel_map_row(channel_map_row, require_availables=True)
        path = shortest_passthrough_path(start_harness, end_harness, tight)
        if path is not None:
            return path
        loose = context_rows_for_channel_map_row(channel_map_row, require_availables=False)
        path = shortest_passthrough_path(start_harness, end_harness, loose)
        if path is None:
            raise ValueError(
                f"No passthrough path from harness {start_harness!r} to {end_harness!r} "
                f"for channel {channel_map_row.get('from_device_refdes')}/"
                f"{channel_map_row.get('from_device_channel_id')} "
                f"(group_of_connected_harnesses={channel_map_row.get('group_of_connected_harnesses')!r})."
            )
        return path


    def _channel_type_label(type_str):
        """Human-readable channel type for warnings (description + direction)."""
        raw = (type_str or "").strip()
        if not raw:
            return "unknown"
        try:
            desc = chtype.attribute(raw, "description")
            direction = chtype.attribute(raw, "direction")
            if desc == [] or desc is None:
                desc = ""
            if direction == [] or direction is None:
                direction = ""
            desc = str(desc).strip()
            direction = str(direction).strip()
            if direction:
                return f"{desc} ({direction})" if desc else f"({direction})"
            return desc or raw
        except (TypeError, ValueError, SyntaxError):
            return raw


    def _imaginary_type_key_and_label(row):
        """
        Grouping key + display label for one imaginary passthrough channel.

        A/B face types are treated as an unordered pair so opposite orientations
        of the same through-channel type count together.
        """
        sides = []
        for col in ("A-passthrough_channel_type", "B-passthrough_channel_type"):
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            try:
                parsed = chtype.parse(raw)
            except (TypeError, ValueError, SyntaxError):
                parsed = None
            sides.append((parsed if parsed is not None else raw, raw))
        if not sides:
            return (("unknown",), "unknown")

        unique = []
        seen = set()
        for parsed, raw in sides:
            if parsed in seen:
                continue
            seen.add(parsed)
            unique.append((parsed, raw))

        parsed_keys = [parsed for parsed, _raw in unique if isinstance(parsed, tuple)]
        if parsed_keys and len(parsed_keys) == len(unique):
            key = tuple(sorted(parsed_keys))
        else:
            key = tuple(sorted(raw for _parsed, raw in unique))
        labels = sorted({_channel_type_label(raw) for _parsed, raw in unique})
        return key, " / ".join(labels)


    def _print_imaginary_warnings(rows):
        """Warn once per passthrough that needed imaginary channels to satisfy the map."""
        counts = defaultdict(lambda: defaultdict(int))
        labels = {}
        for row in rows:
            if str(row.get("is_imaginary") or "").strip().upper() != "TRUE":
                continue
            disc = row.get("passthrough_device_refdes") or ""
            key, label = _imaginary_type_key_and_label(row)
            counts[disc][key] += 1
            labels[(disc, key)] = label

        for disc in sorted(counts):
            parts = []
            type_items = sorted(
                counts[disc].items(), key=lambda item: labels[(disc, item[0])]
            )
            for key, n in type_items:
                noun = "channel" if n == 1 else "channels"
                parts.append(f"{n} imaginary {noun} of type {labels[(disc, key)]}")
            cli.warn(
                f"passthrough {disc} needs {' and '.join(parts)} "
                "for the channel map to be satisfied"
            )


    def harness_of_device_channel(device_refdes, channel_id, repeat_channel_id=""):
        connector = system_utils.connector_of_channel(
            (device_refdes, channel_id, repeat_channel_id)
        )
        return channel_harness_lookup.get((device_refdes, connector))

    def connector_token(device_refdes, channel_id, repeat_channel_id=""):
        connector = system_utils.connector_of_channel(
            (device_refdes, channel_id, repeat_channel_id)
        )
        return f"{device_refdes}.{connector}"

    def apply_path_steps(channel_map_row, steps):
        """Call route(satisfaction=True) for each (passthrough_device_refdes, directionality)."""
        from_ref = channel_map_row.get("from_device_refdes")
        from_id = channel_map_row.get("from_device_channel_id")
        for disc, directionality in steps:
            route(
                from_ref,
                from_id,
                disc,
                intended_channel_id=None,
                repeat_channel_id=_repeat_of_orientation(disc, directionality),
                satisfaction=True,
            )

    def chains_from_satisfaction(channel_map_row, map_rows):
        """
        Build chain_of_connectors and chain_of_harnesses from ordered satisfaction rows.

        Connectors: device_or_passthrough_device_refdes.connector (e.g. MIC3.J1;X1.A;X1.B;PREAMP.J2)
        Harnesses: one harness per hop (length = #passthroughs + 1)
        """
        from_ref = channel_map_row.get("from_device_refdes")
        from_id = channel_map_row.get("from_device_channel_id")
        to_ref = channel_map_row.get("to_device_refdes")
        to_id = channel_map_row.get("to_device_channel_id")

        from_repeat = (channel_map_row.get("from_repeat_channel_id") or "").strip()
        to_repeat = (channel_map_row.get("to_repeat_channel_id") or "").strip()

        from_token = connector_token(from_ref, from_id, from_repeat)
        to_token = connector_token(to_ref, to_id, to_repeat)
        from_harness = harness_of_device_channel(from_ref, from_id, from_repeat)

        from_key = (from_ref, from_id)
        to_key = (to_ref, to_id)
        hops = []
        for row in map_rows:
            sat = row.get("satisfaction")
            if sat in [None, ""]:
                continue
            a_key = (
                row.get("A-side_device_refdes"),
                row.get("A-side_device_channel_id"),
            )
            b_key = (
                row.get("B-side_device_refdes"),
                row.get("B-side_device_channel_id"),
            )
            if {from_key, to_key} == {a_key, b_key}:
                hops.append(row)
        hops.sort(key=lambda r: int(r.get("satisfaction") or 0))
        if not hops:
            return f"{from_token};{to_token}", from_harness or ""

        connectors = [from_token]
        harnesses = []
        for hop in hops:
            orientation = _requirement_orientation(hop, channel_map_row)
            disc = hop.get("passthrough_device_refdes")
            sides = passthrough_harness_lookup.get(disc, {})
            face_a, face_b = passthrough_face_names.get(disc, ("A", "B"))
            if orientation == 1:
                entry_side, exit_side = face_a, face_b
                entry_h = sides.get("A", "")
                exit_h = sides.get("B", "")
            else:
                entry_side, exit_side = face_b, face_a
                entry_h = sides.get("B", "")
                exit_h = sides.get("A", "")
            harnesses.append(entry_h)
            connectors.append(f"{disc}.{entry_side}")
            connectors.append(f"{disc}.{exit_side}")
            last_exit = exit_h
        harnesses.append(last_exit)
        connectors.append(to_token)
        return ";".join(connectors), ";".join(harnesses)


    global _channel_satisfaction_counters

    # Empty parent topology (no connectors / harness mates): nothing to resolve.
    if not passthrough_harness_lookup and not channel_harness_lookup:
        return

    updated_channel_map = []
    # Shared working copy: refresh after assign() writes; flush satisfaction stamps in batches.
    map_rows = read()

    for channel in channel_map.read():
        if channel.get("from_device_channel_id") in ["", None] or channel.get(
            "to_device_channel_id"
        ) in ["", None]:
            updated_channel_map.append(channel)
            continue

        from_ref = channel.get("from_device_refdes")
        from_id = channel.get("from_device_channel_id")
        from_repeat = (channel.get("from_repeat_channel_id") or "").strip()
        to_ref = channel.get("to_device_refdes")
        to_id = channel.get("to_device_channel_id")
        to_repeat = (channel.get("to_repeat_channel_id") or "").strip()
        channel_key = (from_ref, from_id)
        _channel_satisfaction_counters[channel_key] = 0

        from_harness = harness_of_device_channel(from_ref, from_id, from_repeat)
        to_harness = harness_of_device_channel(to_ref, to_id, to_repeat)
        requirements = _requirements_for_mapped_channel(channel, map_rows)

        # ==== CASE 1: same harness, no requirements ====
        if from_harness == to_harness and not requirements:
            channel = dict(channel)
            from_token = connector_token(from_ref, from_id, from_repeat)
            to_token = connector_token(to_ref, to_id, to_repeat)
            channel["chain_of_connectors"] = f"{from_token};{to_token}"
            channel["chain_of_harnesses"] = from_harness or ""
            updated_channel_map.append(channel)
            continue

        # ==== CASE 2: no requirements — path between harnesses ====
        if not requirements:
            steps = find_pathway(
                start_harness=from_harness,
                end_harness=to_harness,
                channel_map_row=channel,
            )
            apply_path_steps(channel, steps)
            map_rows = read()
            channel = dict(channel)
            connectors, harnesses = chains_from_satisfaction(channel, map_rows)
            channel["chain_of_connectors"] = connectors
            channel["chain_of_harnesses"] = harnesses
            updated_channel_map.append(channel)
            continue

        # ==== CASE 3: ordered requirements as waypoints ====
        current_harness = from_harness
        map_dirty = False

        for req_row in requirements:
            entry, exit_h = _requirement_entry_exit_harnesses(req_row, channel)
            if current_harness != entry:
                if map_dirty:
                    _write_passthrough_map(map_rows)
                    map_dirty = False
                gap_steps = find_pathway(
                    start_harness=current_harness,
                    end_harness=entry,
                    channel_map_row=channel,
                )
                apply_path_steps(channel, gap_steps)
                map_rows = read()

            stamped = False
            for i, row in enumerate(map_rows):
                if (
                    row.get("passthrough_device_refdes") == req_row.get("passthrough_device_refdes")
                    and row.get("passthrough_channel_id")
                    == req_row.get("passthrough_channel_id")
                    and str(row.get("requirement")) == str(req_row.get("requirement"))
                ):
                    map_rows[i]["satisfaction"] = next_satisfaction(channel_key)
                    stamped = True
                    break
            if not stamped:
                raise ValueError(
                    f"Could not find passthrough-map row to stamp satisfaction for "
                    f"requirement {req_row.get('requirement')} on "
                    f"{req_row.get('passthrough_device_refdes')}/"
                    f"{req_row.get('passthrough_channel_id')}"
                )
            map_dirty = True
            current_harness = exit_h

        if map_dirty:
            _write_passthrough_map(map_rows)
            map_dirty = False

        if current_harness != to_harness:
            gap_steps = find_pathway(
                start_harness=current_harness,
                end_harness=to_harness,
                channel_map_row=channel,
            )
            apply_path_steps(channel, gap_steps)
            map_rows = read()

        channel = dict(channel)
        connectors, harnesses = chains_from_satisfaction(channel, map_rows)
        channel["chain_of_connectors"] = connectors
        channel["chain_of_harnesses"] = harnesses
        updated_channel_map.append(channel)

    channel_map._write_channel_map(updated_channel_map)
    _write_routing_context(list(system.passthrough_routing_context))
    _print_imaginary_warnings(read())

