import csv
import os

from harnice import cli, fileio
from harnice.lists import cached_tsv, signals_list
from harnice.project_types import chtype
from harnice.utils import system_utils

COLUMNS = [
    "group_of_connected_harnesses",  # harnesses linked through passthroughs (or a single standalone harness)
    "from_device_refdes",  # device instance refdes of this channel endpoint (seeded by new())
    "from_device_channel_id",  # channel id on that device (from its signals list)
    "from_repeat_channel_id",  # required when that channel has two endpoints; blank otherwise
    "from_channel_type",  # channel type of the from endpoint (from the signals list)
    "to_device_refdes",  # device instance refdes of the mapped partner; blank until mapped
    "to_device_channel_id",  # channel id of the mapped partner; blank until mapped
    "to_repeat_channel_id",  # required when that channel has two endpoints; blank otherwise
    "to_channel_type",  # channel type of the mapped partner; blank until mapped
    "multi_ch_junction_id",  # set by map(..., multi_ch_junction_key=...); shared id for a multi-channel junction net
    "chain_of_connectors",  # filled by passthrough_map.resolve(); semicolon-separated refdes.connector path (e.g. MIC3.J1;X1.A;X1.B;PREAMP1.J1)
    "chain_of_harnesses",  # filled by passthrough_map.resolve(); semicolon-separated harness refdes hops (e.g. H1;H2)
    "manual_map_channel_python_equiv",  # channel_map.map(...) call that produced this pairing; copy back into build instructions
]

# Forced patches whose signal names differ, waiting for circuits_list.force().
PENDING_COLUMNS = [
    "from_device_refdes",
    "from_device_channel_id",
    "from_repeat_channel_id",
    "to_device_refdes",
    "to_device_channel_id",
    "to_repeat_channel_id",
    "from_channel_type",
    "to_channel_type",
    "from_signals",  # comma-separated, channel-type order
    "to_signals",  # comma-separated, channel-type order
]

channel_documentation_description = 'A channel is a set of electrical signals in a device that together transmit or receive information, power, etc. They have "channel_types" which define their attributes and compatibility with other channels, and contain a list of required signals (pos, neg)'

mapped_channel_documentation_description = "A mapped channel is a connection from one channel on a device to another. They define the functional requirement of any harness, and form the basis of which circuits are generated and where they go. The channel map is the list of mapped channels (and any still-unmapped channels). The passthrough map then routes those mapped channels through passthrough devices."


def read():
    """Return the channel map (cached)."""
    return cached_tsv.read(fileio.path("channel map"))


def _repeats_of_channel(refdes, channel_id):
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        raise FileNotFoundError(
            f"No signals list / ICD for {refdes!r} under "
            f"instance_data/device or instance_data/system"
        )
    return signals_list.repeat_ids_of_channel(signals_list.read(path)).get(
        (channel_id or "").strip(), set()
    )


def _other_key_channel_label(other_key):
    if not other_key or not isinstance(other_key, (tuple, list)) or len(other_key) < 2:
        return None
    other_refdes = (other_key[0] or "").strip()
    other_channel_id = (other_key[1] or "").strip()
    if not other_refdes or not other_channel_id:
        return None
    return other_channel_id, other_refdes


def _missing_repeat_message(refdes, channel_id, repeats, other_key=None):
    example = next((r for r in sorted(repeats) if r), "A")
    msg = f"Channel {channel_id!r} on {refdes!r} has two endpoints. "
    other = _other_key_channel_label(other_key)
    if other:
        other_channel_id, other_refdes = other
        msg += (
            f"When mapping {other_channel_id!r} on {other_refdes!r} to it, "
            "you did not specify which endpoint you want. "
        )
    else:
        msg += "You did not specify which endpoint you want. "
    msg += (
        f"Add a third value in the tuple: ex. ({refdes!r}, {channel_id!r}, {example!r})"
    )
    return msg


def canonical_map_key(key, other_key=None):
    """Normalize a ``map()`` key to a 2-tuple or 3-tuple.

    ``(device_refdes, channel_id)`` when the channel has one endpoint.
    ``(device_refdes, channel_id, repeat_channel_id)`` when it has two.
    A 3-tuple on a single-instance channel, or a 2-tuple on a two-instance
    channel, is an error.
    """
    if key is None:
        return None
    if not isinstance(key, (tuple, list)) or len(key) not in (2, 3):
        raise ValueError(
            f"map key must be a 2-tuple (device_refdes, channel_id) or "
            f"3-tuple (device_refdes, channel_id, repeat_channel_id); got {key!r}"
        )
    refdes = (key[0] or "").strip()
    channel_id = (key[1] or "").strip()
    given_repeat = (key[2] or "").strip() if len(key) == 3 else None
    if not refdes or not channel_id:
        raise ValueError(f"map key {key!r} is missing device_refdes or channel_id")

    repeats = _repeats_of_channel(refdes, channel_id)
    if not repeats:
        raise ValueError(f"Channel {channel_id!r} not found on {refdes!r}")

    n = len(repeats)
    if n == 1:
        only = next(iter(repeats))
        if only:
            if given_repeat is None:
                raise ValueError(
                    _missing_repeat_message(refdes, channel_id, repeats, other_key)
                )
            if given_repeat != only:
                raise ValueError(
                    f"repeat_channel_id {given_repeat!r} is not an endpoint of "
                    f"channel {channel_id!r} on {refdes!r}"
                )
            return (refdes, channel_id, given_repeat)
        if given_repeat is not None:
            raise ValueError(
                f"Channel {channel_id!r} on {refdes!r} only has one endpoint, "
                f"but you called for a specific repeat channel id {given_repeat!r}, "
                "which is not necessary"
            )
        return (refdes, channel_id)

    if given_repeat is None:
        raise ValueError(
            _missing_repeat_message(refdes, channel_id, repeats, other_key)
        )
    if given_repeat not in repeats:
        raise ValueError(
            f"repeat_channel_id {given_repeat!r} is not an endpoint of "
            f"channel {channel_id!r} on {refdes!r} "
            f"(repeats: {sorted(repeats)})"
        )
    return (refdes, channel_id, given_repeat)


def _key_from_row(row, side="from"):
    refdes = (row.get(f"{side}_device_refdes") or "").strip()
    channel_id = (row.get(f"{side}_device_channel_id") or "").strip()
    repeat = (row.get(f"{side}_repeat_channel_id") or "").strip()
    if not refdes or not channel_id:
        return None
    if repeat:
        return (refdes, channel_id, repeat)
    return (refdes, channel_id)


def _repeat_of_key(key):
    if key is None or len(key) < 3:
        return ""
    return (key[2] or "").strip()


def _row_is_multi_endpoint(row):
    return bool((row.get("from_repeat_channel_id") or "").strip())


def _connector_list_rows():
    try:
        return fileio.read_tsv("system connector list")
    except FileNotFoundError:
        return []


def _group_of_device_connector(refdes, connector_id, connectors=None):
    connectors = connectors if connectors is not None else _connector_list_rows()
    for row in connectors:
        if (row.get("device_refdes") or "").strip() != refdes:
            continue
        if (row.get("device_connector") or "").strip() != connector_id:
            continue
        return (row.get("group_of_connected_harnesses") or "").strip()
    return ""


def groups_of_device(refdes):
    """Non-empty ``group_of_connected_harnesses`` labels on this placed device."""
    refdes = (refdes or "").strip()
    return {
        (row.get("group_of_connected_harnesses") or "").strip()
        for row in _connector_list_rows()
        if (row.get("device_refdes") or "").strip() == refdes
        and (row.get("group_of_connected_harnesses") or "").strip()
    }


def group_of_key(key):
    """``group_of_connected_harnesses`` for a map key.

    A terminating (single-instance) channel uses the group on that connector.
    Unmated terminating connectors have no group.

    A passthrough face belongs to the group of either face of that channel: an
    unmated far face still shares the mated near face's group. Both faces
    unmated means no group.
    """
    if key is None:
        return ""
    refdes = (key[0] or "").strip()
    channel_id = (key[1] or "").strip()
    repeat = _repeat_of_key(key)
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        return ""
    connectors = _connector_list_rows()
    sides = signals_list.passthrough_channels(path).get(channel_id)
    if sides:
        groups = set()
        for connector_id in sides:
            g = _group_of_device_connector(refdes, connector_id, connectors)
            if g:
                groups.add(g)
        if not groups:
            return ""
        return sorted(groups)[0]
    try:
        connector_id = signals_list.connector_id_of_channel(
            channel_id, path, repeat_channel_id=repeat
        )
    except (ValueError, FileNotFoundError):
        return ""
    return _group_of_device_connector(refdes, connector_id, connectors)


def _mating_harness_of_key(key):
    """Mating harness refdes for a map key, or ``\"\"`` if unknown/unmated."""
    if key is None:
        return ""
    refdes, channel_id = key[0], key[1]
    repeat = _repeat_of_key(key)
    path = system_utils.placed_signals_list_path(refdes)
    if not path:
        return ""
    try:
        connector_id = signals_list.connector_id_of_channel(
            channel_id, path, repeat_channel_id=repeat
        )
    except (ValueError, FileNotFoundError):
        return ""
    for row in _connector_list_rows():
        if (row.get("device_refdes") or "").strip() != refdes:
            continue
        if (row.get("device_connector") or "").strip() != connector_id:
            continue
        return (row.get("mating_harness_refdes") or "").strip()
    return ""


def _format_map_key(key):
    if key is None:
        return ""
    if len(key) >= 3 and (key[2] or "").strip():
        return f"({key[0]!r}, {key[1]!r}, {key[2]!r})"
    return f"({key[0]!r}, {key[1]!r})"


def _other_repeat_of_key(key):
    repeats = _repeats_of_channel(key[0], key[1])
    this = _repeat_of_key(key)
    others = sorted(r for r in repeats if r and r != this)
    return others[0] if others else ""


def _other_devices_on_harness(harness, exclude_refdes=""):
    seen = []
    for row in _connector_list_rows():
        if (row.get("mating_harness_refdes") or "").strip() != harness:
            continue
        refdes = (row.get("device_refdes") or "").strip()
        if not refdes or refdes == exclude_refdes or refdes in seen:
            continue
        seen.append(refdes)
    return seen


def _reject_if_crossing_onto_mated_face(from_key, to_key):
    """A patch may end by crossing a device only if that destination face has no harness."""
    if to_key is None or len(to_key) != 3:
        return
    to_harness = _mating_harness_of_key(to_key)
    if not system_utils._is_real_harness_refdes(to_harness):
        return
    from_harness = _mating_harness_of_key(from_key)
    if from_harness == to_harness:
        return

    to_refdes, to_channel, to_repeat = to_key[0], to_key[1], to_key[2]
    from_refdes, from_channel = from_key[0], from_key[1]
    near_repeat = _other_repeat_of_key(to_key)
    instead = []
    if near_repeat:
        near_key = (to_refdes, to_channel, near_repeat)
        instead.append(
            f"Map to the other endpoint of {to_channel!r} on {to_refdes!r} "
            f"(same harness as {from_refdes}): "
            f"map({_format_map_key(from_key)}, {_format_map_key(near_key)})"
        )
    far_devices = _other_devices_on_harness(to_harness, to_refdes)
    far_list = ", ".join(far_devices) if far_devices else "another device"
    instead.append(
        f"Or map {from_channel!r} on {from_refdes!r} to a device on "
        f"{to_harness!r} ({far_list}) and then route() through {to_refdes}"
    )
    raise ValueError(
        f"Channel {to_channel!r} endpoint {to_repeat!r} on {to_refdes!r} "
        f"is already mated to harness {to_harness!r}. "
        f"Mapping {from_channel!r} on {from_refdes!r} to it would jump through "
        f"{to_refdes} onto that harness. You can only end a patch by crossing "
        f"a passthrough if the far endpoint has no harness; otherwise the last "
        f"hop must be that harness. Instead: {' '.join(instead)}."
    )


def _reject_if_not_same_group(from_key, to_key):
    """Manual map must stay inside one group of connected harnesses."""
    from_group = group_of_key(from_key)
    if to_key is None:
        if not from_group:
            raise ValueError(
                f"Cannot map {from_key}: endpoint is not in a group of "
                "connected harnesses"
            )
        return
    to_group = group_of_key(to_key)
    if not from_group or not to_group:
        raise ValueError(
            f"Cannot map {from_key} to {to_key}: both endpoints must belong "
            "to a group of connected harnesses "
            f"(groups: {from_group!r}, {to_group!r})"
        )
    if from_group != to_group:
        raise ValueError(
            f"Cannot map {from_key} (group {from_group!r}) to {to_key} "
            f"(group {to_group!r}): not the same group of connected harnesses"
        )


def new():
    """
    Makes a new blank channel map. Overwrites existing channel map.

    Seeds one row per channel endpoint, including both faces of a passthrough.
    Auto-map skips those multi-endpoint rows; ``map()`` uses a 3-tuple to name
    a face.

    Args: none

    Returns: none
    """
    channel_map = []
    device_signals_cache = {}
    seeded = set()

    for connector in fileio.read_tsv("system connector list"):
        device_refdes = (connector.get("device_refdes") or "").strip()
        connector_id = (connector.get("device_connector") or "").strip()

        if not device_refdes or not connector_id:
            continue

        if device_refdes not in device_signals_cache:
            signals_path = system_utils.placed_signals_list_path(device_refdes)
            if not signals_path:
                raise FileNotFoundError(
                    f"No signals list / ICD for {device_refdes!r} under "
                    f"instance_data/device or instance_data/system"
                )
            rows = list(fileio.read_tsv(signals_path))
            device_signals_cache[device_refdes] = {
                "rows": rows,
                "repeats": signals_list.repeat_ids_of_channel(rows),
            }

        cached = device_signals_cache[device_refdes]
        for signal in cached["rows"]:
            sig_channel = (signal.get("channel_id") or "").strip()
            if not sig_channel:
                continue
            if (signal.get("connector_id") or "").strip() != connector_id:
                continue

            repeat = (signal.get("repeat_channel_id") or "").strip()
            endpoint = (device_refdes, sig_channel, repeat)
            if endpoint in seeded:
                continue
            seeded.add(endpoint)

            channel_map.append(
                {
                    "group_of_connected_harnesses": connector.get(
                        "group_of_connected_harnesses", ""
                    ),
                    "from_channel_type": signal.get("channel_type", ""),
                    "from_device_refdes": device_refdes,
                    "from_device_channel_id": sig_channel,
                    "from_repeat_channel_id": repeat,
                }
            )

    _write_channel_map(channel_map)

    with open(
        fileio.path("mapped channels set"), "w", newline="", encoding="utf-8"
    ) as f:
        pass

    clear_pending()
    # A new channel map invalidates signal pairings from the previous one.
    # Imported here: circuits_list imports channel_map at module level.
    from harnice.lists.circuits_list import FORCED_SIGNAL_COLUMNS

    forced_path = fileio.path("forced signal map")
    os.makedirs(os.path.dirname(forced_path), exist_ok=True)
    cached_tsv.write(forced_path, FORCED_SIGNAL_COLUMNS, [])

    return channel_map


def _write_channel_map(channels):
    cached_tsv.write(fileio.path("channel map"), COLUMNS, channels)


def _write_mapped_set(items):
    with open(
        fileio.path("mapped channels set"), "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f, delimiter="\t")
        for item in sorted(items):
            writer.writerow([item])


def _reject_if_incompatible_with_junction(from_key, junction_id, channels):
    """A channel may join a junction only if it is or is compatible with every member."""
    from_type = None
    for row in channels:
        if _key_from_row(row, "from") == from_key:
            from_type = row.get("from_channel_type")
            break
    if from_type is None:
        return
    for row in channels:
        if (row.get("multi_ch_junction_id") or "").strip() != junction_id:
            continue
        other_key = _key_from_row(row, "from")
        if other_key is None or other_key == from_key:
            continue
        other_type = row.get("from_channel_type")
        compatible = False
        if from_type and other_type:
            try:
                parsed_from = chtype.parse(from_type)
                parsed_other = chtype.parse(other_type)
            except (ValueError, TypeError, SyntaxError):
                parsed_from = parsed_other = None
            if parsed_from is not None and parsed_other is not None:
                compatible = parsed_from in chtype.is_or_is_compatible_with(
                    other_type
                ) or parsed_other in chtype.is_or_is_compatible_with(from_type)
        if not compatible:
            raise ValueError(
                f"Cannot map {from_key} onto multi_ch_junction_key={junction_id!r}: "
                f"channel type {from_type} is not, and is not compatible with, "
                f"{other_key} ({other_type})"
            )


def _map_into(
    channels, mapped, from_key, to_key=None, multi_ch_junction_key="", python_equiv=None
):
    """Apply one channel mapping in memory. Mutates ``channels`` and ``mapped``."""
    if str(from_key) in mapped:
        raise ValueError(f"from_key {from_key} already mapped")
    if to_key and str(to_key) in mapped:
        raise ValueError(f"to_key {to_key} already mapped")

    to_channel = None
    if to_key is not None:
        for channel in channels:
            if _key_from_row(channel, "from") == to_key:
                to_channel = channel
                break

    if not to_channel and multi_ch_junction_key == "":
        raise ValueError(f"to_key {to_key} not found in channel map")

    require_to = bool(to_key and (to_key[0] or to_key[1]))

    updated_channels, found_from, found_to = [], False, False
    mapped_row = None

    for row in channels:
        row_from = _key_from_row(row, "from")
        if row_from == from_key:
            mapped_row = row
            row["to_device_refdes"] = to_key[0] if to_key else ""
            row["to_device_channel_id"] = to_key[1] if to_key else ""
            row["to_repeat_channel_id"] = _repeat_of_key(to_key)
            row["to_channel_type"] = (
                to_channel.get("from_channel_type") if to_channel else ""
            )
            if multi_ch_junction_key:
                row["multi_ch_junction_id"] = multi_ch_junction_key
            found_from = True

            if require_to:
                row["manual_map_channel_python_equiv"] = python_equiv or (
                    f"channel_map.map({from_key}, {to_key})"
                )
            elif multi_ch_junction_key:
                row["manual_map_channel_python_equiv"] = (
                    f"channel_map.map({from_key}, multi_ch_junction_key={multi_ch_junction_key!r})"
                )
        elif require_to and row_from == to_key:
            found_to = True
            continue
        updated_channels.append(row)

    if not found_from:
        raise ValueError(f"from_key {from_key} not found in channel map")
    if require_to and not found_to:
        raise ValueError(f"to_key {to_key} not found in channel map")

    if str(from_key) in mapped:
        raise ValueError(f"key {from_key} already mapped")
    mapped.add(str(from_key))
    if to_key:
        if str(to_key) in mapped:
            raise ValueError(f"key {to_key} already mapped")
        mapped.add(str(to_key))

    channels[:] = updated_channels
    return mapped_row


def _apply_mapping(from_key, to_key=None, multi_ch_junction_key="", python_equiv=None):
    """Write one mapping the way ``map()`` does, and return that channel-map row."""
    with cached_tsv.edit(fileio.path("channel map"), COLUMNS) as channels:
        if multi_ch_junction_key:
            _reject_if_incompatible_with_junction(
                from_key, multi_ch_junction_key, channels
            )
        mapped = already_mapped_set()
        row = _map_into(
            channels,
            mapped,
            from_key,
            to_key=to_key,
            multi_ch_junction_key=multi_ch_junction_key,
            python_equiv=python_equiv,
        )
        _write_mapped_set(mapped)
        return row


def map(from_key, to_key=None, multi_ch_junction_key=""):
    """
    Map one channel endpoint to another (a patch), or consume it onto a
    multi-channel junction.

    Each key is ``(device_refdes, channel_id)`` when that channel has one
    endpoint, or ``(device_refdes, channel_id, repeat_channel_id)`` when it
    has two. A 3-tuple on a single-instance channel is an error; omitting the
    repeat on a two-instance channel is an error.

    Dual-map is two calls to the two repeats of the same passthrough. That
    consumes both faces as patch ends and does not write a passthrough-map row.

    Both endpoints must belong to the same ``group_of_connected_harnesses``.
    Unmated terminating connectors are in no group. An unmated passthrough
    face still belongs to the group of its other, mated face.

    A patch may end by crossing a device only if the destination face has no
    harness. If that face has a harness, the last hop must be that harness.

    Pass ``multi_ch_junction_key="jcn1"`` instead of ``to_key`` to consume
    ``from_key`` and write ``jcn1`` as ``multi_ch_junction_id``. Several rows
    can share that id (connecting those channels to each other) without
    pairing to a single partner. A channel may join only if its type is, or
    is compatible with, every other member already on that junction.

    **Args:**
    - `from_key`: Endpoint to map. ``(device_refdes, channel_id)`` when the channel has one endpoint, or ``(device_refdes, channel_id, repeat_channel_id)`` when it has two. A 3-tuple on a single-endpoint channel is an error, and omitting the repeat on a two-endpoint channel is an error.
    - `to_key`: Other endpoint of the patch, in the same tuple shape as ``from_key``. Both ends must belong to the same group of connected harnesses. Optional. Omit it, or pass None, when you pass ``multi_ch_junction_key`` instead.
    - `multi_ch_junction_key`: Junction id, such as ``"jcn1"``, that consumes ``from_key``. Every channel that shares that id is connected, without pairing to one partner. The channel type must be compatible with members already on the junction. Do not pass this together with ``to_key``. Optional.
    """
    multi_ch_junction_key = (multi_ch_junction_key or "").strip()
    from_key = canonical_map_key(from_key, other_key=to_key)
    if to_key is not None and (to_key[0] or to_key[1]):
        if multi_ch_junction_key:
            raise ValueError(
                "channel_map.map() allows either a to_key or "
                "multi_ch_junction_key=, not both"
            )
        to_key = canonical_map_key(to_key, other_key=from_key)
        if from_key == to_key:
            raise ValueError(f"from_key and to_key are the same endpoint: {from_key}")
        _reject_if_not_same_group(from_key, to_key)
        _reject_if_crossing_onto_mated_face(from_key, to_key)
    else:
        _reject_if_not_same_group(from_key, None)
    _apply_mapping(from_key, to_key=to_key, multi_ch_junction_key=multi_ch_junction_key)


def force(from_key, to_key):
    """Map one channel endpoint to another regardless of channel-type compatibility.

    Same key, group, and face rules as ``map()``. A 1:1 patch only: there is
    no ``multi_ch_junction_key``. ``map()`` is unchanged and does not record
    a pending patch.

    Signal names still pair by name when both channel types list the same
    set, and ``circuits_list.new()`` compiles those circuits as usual. When
    the sets differ, the patch is recorded as pending. Call
    ``circuits_list.force()`` with a from-signal → to-signal dict, and drop
    every to-side signal you are leaving unwired, before
    ``circuits_list.new()``. A pending patch still waiting at circuit compile
    raises ``ValueError``.

    The circuit's ``from_signal`` is the from-side name. A from-side signal cannot
    be left unwired. If the from channel has a name the to channel does not,
    swap the endpoints so that extra name is on the to side, then drop it.
    """
    if to_key is None or not isinstance(to_key, (tuple, list)) or len(to_key) < 2:
        raise ValueError("channel_map.force() requires a to_key")
    if not (to_key[0] or to_key[1]):
        raise ValueError("channel_map.force() requires a to_key")
    from_key = canonical_map_key(from_key, other_key=to_key)
    to_key = canonical_map_key(to_key, other_key=from_key)
    if from_key == to_key:
        raise ValueError(f"from_key and to_key are the same endpoint: {from_key}")

    # Same placement rules as map(): one group of connected harnesses, and a
    # patch may end on a passthrough face only when that face has no harness.
    _reject_if_not_same_group(from_key, to_key)
    _reject_if_crossing_onto_mated_face(from_key, to_key)

    equiv = f"channel_map.force({from_key}, {to_key})"
    row = _apply_mapping(
        from_key,
        to_key,
        python_equiv=equiv,
    )
    from_names = chtype.signals(row.get("from_channel_type") or "")
    to_names = chtype.signals(row.get("to_channel_type") or "")
    # Same names compile by name (pos meets pos), in channel-type order or not.
    # Different names stay pending until circuits_list.force() pairs each
    # from-side signal to a to-side signal. That pairing is not in this cell.
    signal_names_match = sorted(from_names) == sorted(to_names)
    if not signal_names_match:
        commented = equiv + "  # this line does not include forced circuits"
        row["manual_map_channel_python_equiv"] = commented
        with cached_tsv.edit(fileio.path("channel map"), COLUMNS) as channels:
            for stored in channels:
                if _key_from_row(stored, "from") == from_key:
                    stored["manual_map_channel_python_equiv"] = commented
                    break
        add_pending(
            from_key,
            to_key,
            row.get("from_channel_type") or "",
            row.get("to_channel_type") or "",
            from_names,
            to_names,
        )


def _write_pending(rows):
    path = fileio.path("pending forced channels")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cached_tsv.write(path, PENDING_COLUMNS, rows)


def read_pending():
    """Forced patches whose signal names still need ``circuits_list.force()``."""
    path = fileio.path("pending forced channels")
    if not os.path.exists(path):
        return []
    return cached_tsv.read(path)


def clear_pending():
    """Drop every forced patch that is still waiting on a signal map."""
    _write_pending([])


def add_pending(
    from_key, to_key, from_channel_type, to_channel_type, from_names, to_names
):
    """Record one forced patch whose signal-name sets differ."""
    rows = [row for row in read_pending() if _key_from_row(row) != from_key]
    rows.append(
        {
            "from_device_refdes": from_key[0],
            "from_device_channel_id": from_key[1],
            "from_repeat_channel_id": _repeat_of_key(from_key),
            "to_device_refdes": to_key[0],
            "to_device_channel_id": to_key[1],
            "to_repeat_channel_id": _repeat_of_key(to_key),
            "from_channel_type": from_channel_type or "",
            "to_channel_type": to_channel_type or "",
            "from_signals": ",".join(from_names),
            "to_signals": ",".join(to_names),
        }
    )
    _write_pending(rows)


def drop_pending(from_key):
    """Remove one pending forced patch. ``circuits_list.force()`` calls this."""
    _write_pending([row for row in read_pending() if _key_from_row(row) != from_key])


def already_mapped_set_append(key):
    """Mark one endpoint as already mapped.

    **Args:**
    - `key`: Endpoint key in the same shape ``map`` uses: ``(device_refdes, channel_id)`` or ``(device_refdes, channel_id, repeat_channel_id)``. Raises if that key is already in the mapped set.
    """
    items = already_mapped_set()
    if str(key) in items:
        raise ValueError(f"key {key} already mapped")
    items.add(str(key))
    _write_mapped_set(items)


def already_mapped_set():
    """Return the set of endpoint keys already consumed by ``map`` or ``route``."""
    if not os.path.exists(fileio.path("mapped channels set")):
        return set()
    with open(fileio.path("mapped channels set"), newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        return set(row[0] for row in reader if row)


def already_mapped(key):
    """Return whether an endpoint is already in the mapped-channels set.

    **Args:**
    - `key`: Endpoint key in the same shape ``map`` uses: ``(device_refdes, channel_id)`` or ``(device_refdes, channel_id, repeat_channel_id)``.
    """
    if str(key) in already_mapped_set():
        return True
    else:
        return False


def map_unmapped_compatibles_alphabetically():
    """
    For each group of connected harnesses, consider channels in alphabetical
    order. For each unmapped "from" channel, map it to the first other unmapped
    channel in the group that is mutually compatible (either side declares
    compatibility).

    Skips every channel that has more than one endpoint (passthroughs), even
    if nothing else is left. Map those faces with ``map()`` or ``route()``.
    """
    with cached_tsv.edit(fileio.path("channel map"), COLUMNS) as channels:
        mapped = already_mapped_set()
        unique_groups_of_connected_harnesses = sorted(
            set(
                r["group_of_connected_harnesses"]
                for r in channels
                if r.get("group_of_connected_harnesses")
            )
        )

        for group_of_connected_harnesses in unique_groups_of_connected_harnesses:
            group_channels = sorted(
                [
                    r
                    for r in channels
                    if r.get("group_of_connected_harnesses")
                    == group_of_connected_harnesses
                ],
                key=lambda r: (
                    r.get("from_device_refdes", ""),
                    r.get("to_device_refdes", ""),
                    r.get("from_device_channel_id", ""),
                    r.get("to_device_channel_id", ""),
                    r.get("from_repeat_channel_id", ""),
                    r.get("to_repeat_channel_id", ""),
                ),
            )

            for from_channel in group_channels:
                if _row_is_multi_endpoint(from_channel):
                    continue
                from_key = _key_from_row(from_channel, "from")
                if from_key is None or str(from_key) in mapped:
                    continue

                from_type = chtype.parse(from_channel.get("from_channel_type"))
                compatibles_from = chtype.compatibles(
                    from_channel.get("from_channel_type")
                )

                for to_channel_candidate in group_channels:
                    if _row_is_multi_endpoint(to_channel_candidate):
                        continue
                    to_key = _key_from_row(to_channel_candidate, "from")
                    if to_key is None or str(to_key) in mapped:
                        continue

                    if to_key == from_key:
                        continue

                    to_type = chtype.parse(
                        to_channel_candidate.get("from_channel_type")
                    )
                    compatibles_to = chtype.compatibles(
                        to_channel_candidate.get("from_channel_type")
                    )

                    if not (to_type in compatibles_from or from_type in compatibles_to):
                        continue

                    _map_into(channels, mapped, from_key, to_key)
                    break

        _write_mapped_set(mapped)


def passthroughs_consumed_as_patch_ends():
    """``{(device_refdes, channel_id), ...}`` whose faces are already patch ends.

    Dual-map (or a patch that ends on a passthrough face) consumes that
    passthrough channel; ``route()`` must not reuse it as a hop.
    """
    consumed = set()
    for row in read():
        to_ch = (row.get("to_device_channel_id") or "").strip()
        if not to_ch and not (row.get("multi_ch_junction_id") or "").strip():
            continue
        for side in ("from", "to"):
            if side == "to" and not to_ch:
                continue
            if not (row.get(f"{side}_repeat_channel_id") or "").strip():
                continue
            refdes = (row.get(f"{side}_device_refdes") or "").strip()
            channel_id = (row.get(f"{side}_device_channel_id") or "").strip()
            if refdes and channel_id:
                consumed.add((refdes, channel_id))
    return consumed


def compile_hierarchical():
    """Write the hierarchical channel map for this system and every child subsystem.

    Reads this system's channel map, then the channel map imported with each
    child subsystem, recursively. An imported subsystem channel map is the
    source of truth: this does not rebuild those rows.

    Rows from a subsystem prefix that subsystem's instance name onto
    ``group_of_connected_harnesses``, ``from_device_refdes``,
    ``to_device_refdes``, ``multi_ch_junction_id``, ``chain_of_connectors``,
    and ``chain_of_harnesses``. A list is prefixed per entry (``AMP.H1+AMP.H2``,
    ``AMP.H1;AMP.H2``, ``AMP.MIC3.J1;AMP.X1.A``). Nested subsystems accumulate
    prefixes (``AMP.PRE.MIC1``). ``manual_map_channel_python_equiv`` is left
    blank. Channel ids, repeat ids, and channel types are copied unchanged.
    This system's own rows are not prefixed. Headers match the channel map.

    Call after channel mapping, including
    ``map_unmapped_compatibles_alphabetically()``. The sheet snapshots the
    channel map as it stands at the call.

    Args: none

    Returns: the written rows
    """

    def namespace_row(row, prefix):
        """Copy one channel-map row and prefix subsystem identity columns."""
        out = {
            col: "" if row.get(col) is None else str(row.get(col, ""))
            for col in COLUMNS
        }
        out["manual_map_channel_python_equiv"] = ""
        prefix = (prefix or "").strip().strip(".")
        if not prefix:
            return out

        def prefixed(name):
            name = (name or "").strip()
            return f"{prefix}.{name}" if name else ""

        def prefixed_list(value, sep):
            return sep.join(prefixed(part) for part in value.split(sep))

        for col in (
            "from_device_refdes",
            "to_device_refdes",
            "multi_ch_junction_id",
        ):
            value = (out.get(col) or "").strip()
            if value:
                out[col] = prefixed(value)
        group = out.get("group_of_connected_harnesses") or ""
        if group.strip():
            out["group_of_connected_harnesses"] = prefixed_list(group, "+")
        harnesses = out.get("chain_of_harnesses") or ""
        if harnesses.strip():
            out["chain_of_harnesses"] = prefixed_list(harnesses, ";")
        connectors = out.get("chain_of_connectors") or ""
        if connectors.strip():
            tokens = []
            for part in connectors.split(";"):
                token = part.strip()
                if not token:
                    tokens.append("")
                    continue
                refdes, dot, connector = token.partition(".")
                if dot:
                    tokens.append(f"{prefixed(refdes)}.{connector}")
                else:
                    tokens.append(prefixed(token))
            out["chain_of_connectors"] = ";".join(tokens)
        return out

    def collect(rows, system_dir, prefix, rev_hint, seen, live):
        """Append this system's namespaced rows, then each child subsystem."""
        real = os.path.realpath(system_dir)
        if real in seen:
            return
        seen.add(real)

        def revision_dir():
            """``lib/revN`` under an imported subsystem, or ``None``."""
            found = fileio.list_revision_folders(
                os.path.join(system_dir, fileio.LIBRARY_USED_DIR)
            )
            if not found:
                return None
            hint = (rev_hint or "").strip()
            if hint.lower().startswith("rev"):
                hint = hint[3:]
            if hint and hint in found:
                return found[hint]
            if len(found) == 1:
                return next(iter(found.values()))

            def sort_key(suffix):
                try:
                    return (0, int(suffix))
                except ValueError:
                    return (1, suffix)

            return found[max(found, key=sort_key)]

        if live:
            source_rows = cached_tsv.read(fileio.path("channel map"))
        else:
            # Promoted maps/channels.tsv is the source of truth. Older imports
            # that only kept the library snapshot are read from lib/revN.
            path = os.path.join(system_dir, "maps", "channels.tsv")
            if not os.path.isfile(path):
                lib_rev = revision_dir()
                snapped = (
                    os.path.join(lib_rev, "maps", "channels.tsv") if lib_rev else ""
                )
                path = snapped if snapped and os.path.isfile(snapped) else ""
            if not path:
                cli.warn(
                    f"subsystem {prefix} has no imported channel map; "
                    "its channels are omitted from the hierarchical channel map"
                )
                source_rows = []
            else:
                source_rows = fileio.read_tsv(path)

        for row in source_rows:
            rows.append(namespace_row(row, prefix))

        # A live revision stores lists/bom.tsv at its root. An imported
        # subsystem keeps that BOM under lib/revN.
        content_root = system_dir
        if not os.path.isfile(os.path.join(system_dir, "lists", "bom.tsv")):
            content_root = revision_dir()
        bom_path = (
            os.path.join(content_root, "lists", "bom.tsv") if content_root else ""
        )
        if not bom_path or not os.path.isfile(bom_path):
            return
        systems_dir = os.path.join(content_root, "instance_data", "system")
        seen_children = set()
        for row in fileio.read_tsv(bom_path):
            if (row.get("system") or "").strip().upper() != "TRUE":
                continue
            refdes = (row.get("device_refdes") or "").strip()
            if not refdes or refdes in seen_children:
                continue
            seen_children.add(refdes)
            child_prefix = f"{prefix}.{refdes}" if prefix else refdes
            child_dir = os.path.join(systems_dir, refdes)
            if not os.path.isdir(child_dir):
                cli.warn(
                    f"subsystem {child_prefix} is on the BOM but has no imported "
                    "folder under instance_data/system"
                )
                continue
            collect(
                rows,
                child_dir,
                child_prefix,
                (row.get("rev") or "").strip(),
                seen,
                False,
            )

    rows = []
    collect(rows, fileio.rev_directory(), "", "", set(), True)
    out_path = fileio.path("hierarchical channel map")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cached_tsv.write(out_path, COLUMNS, rows)
    return rows
