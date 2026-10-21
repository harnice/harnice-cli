import csv
import os
from collections import defaultdict

from harnice import cli, fileio
from harnice.project_types import chtype

signal_documentation_description = "A signal is a physical conductive part inside a connector of a device that facilitiates electrical interface with the outside world. A signal must be part of a channel and live inside a connector."

COLUMNS = [
    "channel_id",  # the channel this row belongs to; the same id on every signal of that channel
    "repeat_channel_id",  # which endpoint, when the channel is a passthrough with two ends; the two repeats must differ; blank when the channel has one endpoint
    "channel_type",  # channel type string; every signal name it declares must be appended for this endpoint, and the string must parse as a channel type
    "signal",  # signal name; one of the names declared by channel_type
    "cavity",  # pin, socket, or stud this signal uses on its connector; required, and unique on that connector
    "connector_id",  # the connector that holds this signal; every signal of one endpoint uses the same connector
    "device_connector_mpn",  # manufacturer part number of the device-side connector; set this or harness_connector_mpn, not both, and use the same choice for every row of that connector
    "harness_connector_mpn",  # manufacturer part number of the harness-side connector; set this or device_connector_mpn, not both
]

_REQUIRED_ALWAYS = (
    "channel_id",
    "channel_type",
    "signal",
    "cavity",
    "connector_id",
)
_OPTIONAL_COLUMNS = tuple(col for col in COLUMNS if col not in _REQUIRED_ALWAYS)


def new():
    """Create a signals TSV at fileio.path("signals list") with only the header row."""
    signals_path = fileio.path("signals list")
    os.makedirs(os.path.dirname(signals_path), exist_ok=True)
    with open(signals_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(COLUMNS)


def append(**kwargs):
    """Append one signal row. Missing optional fields are written as empty strings.

    Required: channel_id, signal, cavity, connector_id, channel_type, and exactly
    one of device_connector_mpn or harness_connector_mpn.

    **Args:**
    - `channel_id`: Channel this row belongs to. Use the same id on every signal of that channel.
    - `channel_type`: Channel type string. Every signal name it declares must be appended for this endpoint, and the string must parse as a channel type.
    - `signal`: Signal name. It must be one of the names declared by ``channel_type``.
    - `cavity`: Pin, socket, or stud this signal uses on its connector. Required, and unique on that connector.
    - `connector_id`: Connector that holds this signal. Every signal of one endpoint must use the same connector.
    - `repeat_channel_id`: Which endpoint, when the channel is a passthrough with two ends. The two repeats must differ. Leave blank when the channel has one endpoint. Optional.
    - `device_connector_mpn`: Manufacturer part number of the device-side connector. Set this or ``harness_connector_mpn``, not both, and use the same choice for every row of that connector.
    - `harness_connector_mpn`: Manufacturer part number of the harness-side connector. Set this or ``device_connector_mpn``, not both.
    """
    signals_path = fileio.path("signals list")
    if not os.path.exists(signals_path):
        new()

    missing = [key for key in _REQUIRED_ALWAYS if not kwargs.get(key)]
    if missing:
        raise ValueError(f"Missing required signal fields: {', '.join(missing)}")

    device_mpn = str(kwargs.get("device_connector_mpn") or "").strip()
    harness_mpn = str(kwargs.get("harness_connector_mpn") or "").strip()
    if bool(device_mpn) == bool(harness_mpn):
        raise ValueError(
            "Exactly one of device_connector_mpn or harness_connector_mpn must be set"
        )

    row = [kwargs.get(col, "") for col in COLUMNS]
    with open(signals_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(row)


def read(path_to_signals_list=None):
    """Return signals-list rows from a path, file key, or the current project list."""
    path = path_to_signals_list or "signals list"
    return fileio.read_tsv(path)


def unique_connector_ids(rows=None, path_to_signals_list=None):
    """Unique ``connector_id`` values in first-seen order."""
    if rows is None:
        rows = read(path_to_signals_list)
    out = []
    seen = set()
    for row in rows:
        connector_id = (row.get("connector_id") or "").strip()
        if not connector_id or connector_id in seen:
            continue
        seen.add(connector_id)
        out.append(connector_id)
    return out


def unique_connector_ids_from_directory(directory):
    """Unique ``connector_id`` values from ``signals.tsv`` in ``directory``."""
    directory = directory or ""
    if not directory or not os.path.isdir(directory):
        return []
    path = os.path.join(directory, "signals.tsv")
    if not os.path.isfile(path):
        return []
    return unique_connector_ids(path_to_signals_list=path)


def cavity_of_signal(channel_id, signal, path_to_signals_list, repeat_channel_id=""):
    """Return the cavity a signal uses on one channel endpoint.

    **Args:**
    - `channel_id`: Channel id of the signal whose cavity you want.
    - `signal`: Signal name on that channel, such as ``pos`` or ``neg``.
    - `path_to_signals_list`: Path, or file key, of the signals list to read.
    - `repeat_channel_id`: Which endpoint when the channel has two. Leave blank to match a single-endpoint channel. Optional.
    """
    want_repeat = (repeat_channel_id or "").strip()
    for row in read(path_to_signals_list):
        if (row.get("signal") or "").strip() != signal.strip():
            continue
        if (row.get("channel_id") or "").strip() != channel_id.strip():
            continue
        if (row.get("repeat_channel_id") or "").strip() != want_repeat:
            continue
        return (row.get("cavity") or "").strip()
    raise ValueError(
        f"Signal {signal} of channel_id {channel_id} not found in {path_to_signals_list}"
    )


def connector_id_of_channel(channel_id, path_to_signals_list, repeat_channel_id=""):
    """Return ``connector_id`` for a channel endpoint.

    **Args:**
    - `channel_id`: Channel id whose connector you want.
    - `path_to_signals_list`: Path, or file key, of the signals list to read. Raises if that file does not exist.
    - `repeat_channel_id`: Which endpoint when the channel has two. Leave blank to match a single-endpoint channel. Optional.
    """
    if not os.path.exists(path_to_signals_list):
        raise FileNotFoundError(f"Signals list file not found: {path_to_signals_list}")
    want_repeat = (repeat_channel_id or "").strip()
    for row in read(path_to_signals_list):
        if (row.get("channel_id") or "").strip() != channel_id.strip():
            continue
        if (row.get("repeat_channel_id") or "").strip() != want_repeat:
            continue
        return (row.get("connector_id") or "").strip()
    raise ValueError(f"Channel {channel_id} not found in {path_to_signals_list}")


def repeat_ids_of_channel(rows):
    """``channel_id`` → set of ``repeat_channel_id`` values."""
    by_channel = defaultdict(set)
    for row in rows:
        channel_id = (row.get("channel_id") or "").strip()
        if not channel_id:
            continue
        by_channel[channel_id].add((row.get("repeat_channel_id") or "").strip())
    return by_channel


def channel_ids_with_repeats(path_to_signals_list):
    """Channel ids that have more than one ``repeat_channel_id`` on this list."""
    return {
        channel_id
        for channel_id, repeats in repeat_ids_of_channel(read(path_to_signals_list)).items()
        if len(repeats) > 1
    }


def passthrough_channels(path_to_signals_list):
    """Two-connector passthroughs: ``{channel_id: {connector_id: channel_type}}``.

    A channel is a passthrough when it has exactly two repeats on two distinct
    connectors. Same-connector two-repeat channels are omitted (not a harness hop).
    """
    rows = read(path_to_signals_list)
    types_by_channel = defaultdict(dict)
    for row in rows:
        channel_id = (row.get("channel_id") or "").strip()
        connector_id = (row.get("connector_id") or "").strip()
        if not channel_id or not connector_id:
            continue
        types_by_channel[channel_id][connector_id] = (
            row.get("channel_type") or ""
        ).strip()

    repeats_by_channel = repeat_ids_of_channel(rows)
    out = {}
    for channel_id, sides in types_by_channel.items():
        if len(repeats_by_channel.get(channel_id, ())) != 2:
            continue
        if len(sides) != 2:
            continue
        out[channel_id] = sides
    return out


def ordered_passthrough_faces(connector_ids):
    """Stable (first, second) face order. ``A``/``B`` stay ``A`` then ``B``."""
    ids = [str(c).strip() for c in connector_ids if str(c).strip()]
    if set(ids) == {"A", "B"}:
        return ("A", "B")
    return tuple(sorted(ids))


def validate(path=None, verbose=True):
    """Validate a unified signals list. Raises ValueError / TypeError / FileNotFoundError."""
    if verbose:
        print("--------------------------------\nValidating signals list...")
    path = path or fileio.path("signals list")
    if not os.path.exists(path):
        raise FileNotFoundError("Signals list was not generated.")

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        headers = reader.fieldnames
        rows = list(reader)

    if not headers:
        raise ValueError("Signals list has no header row.")

    if not rows:
        cli.warn(
            "Signals list contains no signal rows. "
            "Build instructions wiped the list and appended nothing."
        )

    for col in _REQUIRED_ALWAYS:
        if col not in headers:
            raise ValueError(f"Signals list is missing required column '{col}'")
    for col in _OPTIONAL_COLUMNS:
        if col not in headers:
            cli.warn(f"Signals list is missing optional column '{col}'")
    known = set(COLUMNS)
    extra = [col for col in headers if col and col not in known]
    if extra:
        noun = "column" if len(extra) == 1 else "columns"
        listed = ", ".join(repr(col) for col in extra)
        cli.warn(
            f"Signals list has additional {noun} {listed}. "
            "Additional columns are ok but discouraged due to consistency. "
            "If you need more columns, use data structures in build instructions."
        )

    for i, row in enumerate(rows, start=2):
        if verbose:
            print("Looking at csv row:", i)
        for key in _REQUIRED_ALWAYS:
            if (row.get(key) or "").strip() == "":
                if key == "cavity":
                    raise ValueError(
                        f"Signals list row {i} in {path} has a blank cavity "
                        f"(channel_id={row.get('channel_id')!r}, "
                        f"signal={row.get('signal')!r}, "
                        f"connector_id={row.get('connector_id')!r}). "
                        "Cavity is the pin, socket, or stud this signal is routed to on its connector."
                    )
                raise ValueError(f"{key} is blank")

        device_mpn = (row.get("device_connector_mpn") or "").strip()
        harness_mpn = (row.get("harness_connector_mpn") or "").strip()
        if bool(device_mpn) == bool(harness_mpn):
            raise ValueError(
                f"Row {i}: exactly one of device_connector_mpn or "
                f"harness_connector_mpn must be set "
                f"(connector_id={(row.get('connector_id') or '').strip()!r})"
            )

        try:
            channel_type = chtype.parse(row.get("channel_type"))
        except Exception:
            raise TypeError(
                "Channel type is not formatted correctly. See for more: "
                "https://harnice.io/project_types/_channel_type/"
            )

        signal = (row.get("signal") or "").strip()
        if signal not in chtype.signals(channel_type):
            raise ValueError(
                f"Signal {signal} is not a valid signal of its channel type"
            )

    endpoints = defaultdict(list)
    for row in rows:
        endpoints[
            (
                (row.get("channel_id") or "").strip(),
                (row.get("channel_type") or "").strip(),
                (row.get("repeat_channel_id") or "").strip(),
            )
        ].append(row)

    for key, group in endpoints.items():
        channel_id, channel_type_raw, repeat = key
        connectors = {(r.get("connector_id") or "").strip() for r in group}
        if len(connectors) != 1:
            raise ValueError(
                f"Channel {channel_id!r} endpoint "
                f"(channel_type={channel_type_raw!r}, repeat_channel_id={repeat!r}) "
                "has signals on more than one connector_id"
            )
        connector_id = next(iter(connectors))
        channel_type = chtype.parse(channel_type_raw)
        expected = set(chtype.signals(channel_type))
        found = {(r.get("signal") or "").strip() for r in group}
        missing = expected - found
        extra = found - expected
        if missing or extra:
            bits = []
            if missing:
                bits.append(f"missing {', '.join(sorted(missing))}")
            if extra:
                bits.append(f"unexpected {', '.join(sorted(extra))}")
            raise ValueError(
                f"Channel {channel_id!r} endpoint "
                f"(channel_type={channel_type_raw!r}, "
                f"repeat_channel_id={repeat!r}) is incomplete: {'; '.join(bits)}"
            )
        if len(group) != len(found):
            raise ValueError(
                f"Channel {channel_id!r} has duplicate signals "
                f"(repeat_channel_id={repeat!r}, connector_id={connector_id!r})"
            )

    by_channel = defaultdict(set)
    for channel_id, channel_type_raw, repeat in endpoints:
        by_channel[channel_id].add((channel_type_raw, repeat))

    for channel_id, endpoint_keys in by_channel.items():
        n = len(endpoint_keys)
        repeats = {repeat for _type, repeat in endpoint_keys}
        if n == 1:
            if any(repeats):
                raise ValueError(
                    f"Channel {channel_id!r} has only one endpoint; "
                    "repeat_channel_id must be blank"
                )
        elif n == 2:
            if "" in repeats or len(repeats) != 2:
                raise ValueError(
                    f"Channel {channel_id!r} has two endpoints; every row must have "
                    "a repeat_channel_id and the two repeats must differ"
                )
            types = [chtype.parse(t) for t, _r in endpoint_keys]
            if types[1] not in chtype.compatibles(types[0]):
                if types[0] not in chtype.compatibles(types[1]):
                    raise ValueError(
                        f"Channel {channel_id!r} passthrough channel types are not compatible"
                    )
        else:
            raise ValueError(
                f"Channel {channel_id!r} has {n} endpoints; at most two are allowed"
            )

    mpn_by_connector = {}
    for row in rows:
        connector_id = (row.get("connector_id") or "").strip()
        ownership = (
            (row.get("device_connector_mpn") or "").strip(),
            (row.get("harness_connector_mpn") or "").strip(),
        )
        prev = mpn_by_connector.get(connector_id)
        if prev is None:
            mpn_by_connector[connector_id] = ownership
        elif prev != ownership:
            raise ValueError(
                f"Connector {connector_id!r} has mixed device_connector_mpn / "
                "harness_connector_mpn values"
            )

    seen_cavities = set()
    for row in rows:
        cavity_key = (
            (row.get("connector_id") or "").strip(),
            (row.get("cavity") or "").strip(),
        )
        if cavity_key in seen_cavities:
            raise ValueError(
                f"Duplicate cavity '{cavity_key[1]}' found on connector '{cavity_key[0]}'"
            )
        seen_cavities.add(cavity_key)

    if verbose:
        from harnice import state

        print(f"Signals list of {state.partnumber('pn')} is valid.\n")
