import os
from harnice import fileio
from harnice.lists import cached_tsv, channel_map, passthrough_map
from harnice.project_types import chtype
from harnice.utils import system_utils

COLUMNS = [
    "harness",  # harness refdes that carries this hop, taken from chain_of_harnesses
    "harness_chain_index",  # 0-based index into channel map ``chain_of_harnesses`` for this segment
    "circuit_id",  # sequential id of this row, one per signal per harness hop, starting at 0
    "from_signal",  # from-side signal name; also the name used on passthrough hops
    "to_signal",  # to-side signal name when circuits_list.force() paired different names; blank when both ends use from_signal
    "harness_from_refdes",  # refdes at the from end of this harness hop
    "harness_from_channel_id",  # channel id on that from-end refdes
    "harness_from_connector_name",  # connector on that refdes for this signal
    "harness_from_cavity",  # cavity of this signal on that connector
    "harness_to_refdes",  # refdes at the to end of this hop; a junction id when the row ends on a multi-channel junction
    "harness_to_channel_id",  # channel id on that to-end refdes; the signal name on a junction row
    "harness_to_connector_name",  # connector on the to-end refdes; blank on a junction row
    "harness_to_cavity",  # cavity of this signal on that connector; blank on a junction row
    "from_side_device_refdes",  # channel-map from device; the same on every hop of the mapped channel
    "from_side_device_chname",  # channel id on that from device
    "to_side_device_refdes",  # channel-map to device; a junction id when the row ends on a multi-channel junction
    "to_side_device_chname",  # channel id on that to device; the signal name on a junction row
    "from_channel_type",  # channel type of the channel-map from endpoint
    "to_channel_type",  # channel type of the channel-map to endpoint, or the junction's channel type
    "multi_ch_junction_id",  # set when the circuit is from_channel.signal → mcj.signal
]

FORCED_SIGNAL_COLUMNS = [
    "from_device_refdes",
    "from_device_channel_id",
    "from_repeat_channel_id",
    "to_device_refdes",
    "to_device_channel_id",
    "to_repeat_channel_id",
    "from_signal",  # name on the from channel; also the circuit's signal
    "to_signal",  # name on the to channel, used to look up that cavity
]

def read():
    """
    Use this when a system build needs every row of the circuits list in the revision that is open.

    Return the circuits list (cached).
    """
    return cached_tsv.read(fileio.path("circuits list"))


def new():
    """
    Use this when a system build needs the circuits list compiled from the channel map and the passthrough map.

    Build the circuits list from the channel map and passthrough map.

    Uses ``chain_of_connectors`` / ``chain_of_harnesses`` (from ``passthrough_map.resolve()``)
    and ordered ``satisfaction`` rows on the passthrough map for passthrough channel IDs.

    A channel-map row with ``multi_ch_junction_id`` and no ``to_*`` partner becomes
    one circuit per signal: from is ``from_channel.signal``, to is ``mcj.signal``.
    Signal names come from the first channel type seen on that junction id.

    A patch from ``channel_map.force()`` whose signal names differ must
    already have been burned down by ``circuits_list.force()``. Those circuits
    keep the from-side name in ``from_signal`` and look up the to-side cavity under
    ``to_signal``. Passthrough hops are still looked up under ``from_signal``.
    Any pending forced patch raises ``ValueError``.

    Clears any existing circuits list.
    """
    pending = channel_map.read_pending()
    if pending:
        labels = []
        for row in pending:
            ends = []
            for prefix in ("from", "to"):
                refdes = (row.get(f"{prefix}_device_refdes") or "").strip()
                channel = (row.get(f"{prefix}_device_channel_id") or "").strip()
                repeat = (row.get(f"{prefix}_repeat_channel_id") or "").strip()
                if repeat:
                    ends.append(f"{refdes}.{channel}.{repeat}")
                else:
                    ends.append(f"{refdes}.{channel}")
            labels.append(f"{ends[0]} -> {ends[1]}")
        raise ValueError(
            "You force-mapped channels whose signal names do not match, but did not "
            "indicate how you want the circuits mapped: "
            + "; ".join(labels)
            + ". Call circuits_list.force() for each pair before circuits_list.new()."
        )

    forced_by_key = {}
    forced_path = fileio.path("forced signal map")
    if os.path.exists(forced_path):
        for forced_row in cached_tsv.read(forced_path):
            forced_key = (
                (forced_row.get("from_device_refdes") or "").strip(),
                (forced_row.get("from_device_channel_id") or "").strip(),
                (forced_row.get("from_repeat_channel_id") or "").strip(),
            )
            forced_by_key.setdefault(forced_key, []).append(
                (
                    (forced_row.get("from_signal") or "").strip(),
                    (forced_row.get("to_signal") or "").strip(),
                )
            )
    circuits_list = []
    circuit_id = 0

    # Read once per call; nested helpers reuse these instead of re-reading TSVs.
    passthrough_map_rows = passthrough_map.read()
    channel_map_rows = channel_map.read()
    connector_rows = list(fileio.read_tsv("system connector list"))
    signals_list_cache = {}
    junction_types = {}
    for ch_row in channel_map_rows:
        jid = (ch_row.get("multi_ch_junction_id") or "").strip()
        if not jid or jid in junction_types:
            continue
        ctype = (ch_row.get("from_channel_type") or "").strip()
        if ctype:
            junction_types[jid] = ctype

    def cached_signals_rows(path):
        if path not in signals_list_cache:
            signals_list_cache[path] = list(fileio.read_tsv(path))
        return signals_list_cache[path]

    def parse_connector_token(token):
        """Split ``refdes.connector`` (e.g. ``MIC3.J1``, ``X1.A``)."""
        token = (token or "").strip()
        if "." not in token:
            raise ValueError(
                f"Invalid connector token {token!r}; expected refdes.connector "
                "(e.g. 'MIC3.J1' or 'X1.A')"
            )
        refdes, connector = token.rsplit(".", 1)
        if not refdes or not connector:
            raise ValueError(f"Invalid connector token {token!r}")
        return refdes, connector

    def passthrough_chain_from_connectors(
        chain_of_connectors, from_refdes, from_channel_id, to_refdes, to_channel_id
    ):
        """
        Build passthrough hops from ``chain_of_connectors``.

        Returns list of ``(device_refdes, entry_side, exit_side, channel_id)``.
        Empty when the path has no passthroughs (``from.conn;to.conn`` only).
        """
        tokens = [
            t.strip() for t in (chain_of_connectors or "").split(";") if t.strip()
        ]
        if len(tokens) < 2:
            raise ValueError(
                f"channel map chain_of_connectors is empty or incomplete for "
                f"{from_refdes}/{from_channel_id} -> {to_refdes}/{to_channel_id}. "
                "Call passthrough_map.resolve() after passthrough_map.new() (and any route)."
            )

        middle = tokens[1:-1]
        if len(middle) % 2 != 0:
            raise ValueError(
                f"chain_of_connectors middle tokens must be passthrough entry/exit pairs; "
                f"got {middle!r} on {from_refdes}/{from_channel_id}"
            )

        from_key = (from_refdes, from_channel_id)
        to_key = (to_refdes, to_channel_id)
        sat_hops = []
        for row in passthrough_map_rows:
            sat = row.get("satisfaction")
            if sat in [None, ""]:
                continue
            a_key = (
                (row.get("A-side_device_refdes") or "").strip(),
                (row.get("A-side_device_channel_id") or "").strip(),
            )
            b_key = (
                (row.get("B-side_device_refdes") or "").strip(),
                (row.get("B-side_device_channel_id") or "").strip(),
            )
            if {from_key, to_key} == {a_key, b_key}:
                sat_hops.append(row)
        sat_hops.sort(key=lambda r: int(r.get("satisfaction") or 0))

        n_hops = len(middle) // 2
        if n_hops and len(sat_hops) != n_hops:
            raise ValueError(
                f"channel map has {n_hops} passthrough hop(s) in chain_of_connectors for "
                f"{from_refdes}/{from_channel_id}, but passthrough map has "
                f"{len(sat_hops)} satisfaction row(s). Re-run passthrough_map.resolve()."
            )

        hop_chain = []
        for i in range(0, len(middle), 2):
            hop_ref, side_from = parse_connector_token(middle[i])
            hop_ref2, side_to = parse_connector_token(middle[i + 1])
            if hop_ref != hop_ref2:
                raise ValueError(
                    f"Passthrough entry/exit tokens disagree: {middle[i]!r} vs {middle[i + 1]!r}"
                )
            hop_idx = i // 2
            sat_row = sat_hops[hop_idx]
            if (sat_row.get("passthrough_device_refdes") or "").strip() != hop_ref:
                raise ValueError(
                    f"Satisfaction hop {hop_idx + 1} is passthrough "
                    f"{sat_row.get('passthrough_device_refdes')!r} but chain_of_connectors has "
                    f"{hop_ref!r}. Re-run passthrough_map.resolve()."
                )
            channel_id = (sat_row.get("passthrough_channel_id") or "").strip()
            hop_chain.append((hop_ref, side_from, side_to, channel_id))

        return hop_chain

    def resolve_endpoint(
        refdes, channel_id, signal, repeat_channel_id="", connector_id=""
    ):
        if str(channel_id).startswith("imaginary-"):
            return {
                "refdes": refdes,
                "channel_id": channel_id,
                "connector_id": connector_id or "",
                "cavity": "",
            }
        if not channel_id:
            return {
                "refdes": refdes,
                "channel_id": channel_id,
                "connector_id": "",
                "cavity": "",
            }

        signals_path = system_utils.placed_signals_list_path(refdes)
        if not signals_path:
            raise FileNotFoundError(
                f"No signals list / ICD for {refdes!r} under "
                f"instance_data/device or instance_data/system"
            )

        want_repeat = (repeat_channel_id or "").strip()
        want_connector = (connector_id or "").strip()
        rows = cached_signals_rows(signals_path)
        found_connector = ""
        cavity = None
        for row in rows:
            if (row.get("channel_id") or "").strip() != channel_id.strip():
                continue
            if want_repeat or not want_connector:
                if (row.get("repeat_channel_id") or "").strip() != want_repeat:
                    continue
            row_connector = (row.get("connector_id") or "").strip()
            if want_connector and row_connector and row_connector != want_connector:
                continue
            if (row.get("signal") or "").strip() != signal.strip():
                continue
            found_connector = row_connector or want_connector
            cavity = (row.get("cavity") or "").strip()
            break

        if not found_connector:
            raise ValueError(
                f"channel_id {channel_id} not found in {signals_path}"
            )
        if cavity is None:
            raise ValueError(
                f"Signal {signal} of channel_id {channel_id} not found in "
                f"{signals_path}"
            )

        return {
            "refdes": refdes,
            "channel_id": channel_id,
            "connector_id": found_connector,
            "cavity": cavity,
        }

    def mating_harness_of(refdes, connector_id, fallback=""):
        for connector in connector_rows:
            if (connector.get("device_refdes") or "").strip() != refdes:
                continue
            if (connector.get("device_connector") or "").strip() != connector_id:
                continue
            return (connector.get("mating_harness_refdes") or "").strip() or fallback
        return fallback

    def append_circuit(row_dict):
        nonlocal circuit_id
        circuits_list.append(row_dict)
        circuit_id += 1

    def append_junction_circuits(row):
        jid = (row.get("multi_ch_junction_id") or "").strip()
        from_refdes = (row.get("from_device_refdes") or "").strip()
        from_channel_id = (row.get("from_device_channel_id") or "").strip()
        from_repeat = (row.get("from_repeat_channel_id") or "").strip()
        junction_type = junction_types.get(jid) or (row.get("from_channel_type") or "")
        signals = chtype.signals(junction_type)
        fallback_harness = (row.get("group_of_connected_harnesses") or "").strip()
        for signal in signals:
            left = resolve_endpoint(
                from_refdes,
                from_channel_id,
                signal,
                repeat_channel_id=from_repeat,
            )
            harness = mating_harness_of(
                left["refdes"], left["connector_id"], fallback_harness
            )
            append_circuit(
                {
                    "harness": harness,
                    "harness_chain_index": 0,
                    "circuit_id": circuit_id,
                    "from_signal": signal,
                    "from_channel_type": row.get("from_channel_type"),
                    "to_channel_type": junction_type,
                    "harness_from_refdes": left["refdes"],
                    "harness_from_channel_id": left["channel_id"],
                    "harness_from_connector_name": left["connector_id"],
                    "harness_from_cavity": left["cavity"],
                    "harness_to_refdes": jid,
                    "harness_to_channel_id": signal,
                    "harness_to_connector_name": "",
                    "harness_to_cavity": "",
                    "from_side_device_refdes": from_refdes,
                    "from_side_device_chname": from_channel_id,
                    "to_side_device_refdes": jid,
                    "to_side_device_chname": signal,
                    "to_signal": "",
                    "multi_ch_junction_id": jid,
                }
            )

    # --- iterate channel map rows ---
    for row in channel_map_rows:
        if not row.get("from_device_channel_id"):
            continue
        jid = (row.get("multi_ch_junction_id") or "").strip()
        if not (row.get("to_device_refdes") or "").strip():
            if jid:
                append_junction_circuits(row)
            continue

        from_refdes = row["from_device_refdes"].strip()
        from_channel_id = row["from_device_channel_id"].strip()
        from_repeat = (row.get("from_repeat_channel_id") or "").strip()
        to_refdes = row["to_device_refdes"].strip()
        to_channel_id = row["to_device_channel_id"].strip()
        to_repeat = (row.get("to_repeat_channel_id") or "").strip()

        from_type = row.get("from_channel_type")
        to_type = row.get("to_channel_type")
        
        # Incompatible channel types are a forced patch.
        forced = not (
            chtype.parse(to_type) in chtype.is_or_is_compatible_with(from_type)
            or chtype.parse(from_type) in chtype.is_or_is_compatible_with(to_type)
        )

        forced_explicit_signal_map = None
        if not forced:
            # Same name on both ends, in from-channel-type order.
            signal_plan = [
                (name, name)
                for name in chtype.signals(from_type)
            ]
        else:
            forced_explicit_signal_map = forced_by_key.get(
                (from_refdes, from_channel_id, from_repeat)
            )
            if forced_explicit_signal_map:
                signal_plan = forced_explicit_signal_map
            else:
                # Matching signal names have no map, so both ends use the from-channel name.
                signal_plan = [
                    (name, name)
                    for name in chtype.signals(from_type)
                ]

        hop_chain = passthrough_chain_from_connectors(
            row.get("chain_of_connectors"),
            from_refdes,
            from_channel_id,
            to_refdes,
            to_channel_id,
        )
        hop_set = {d[0] for d in hop_chain}

        harnesses = [n.strip() for n in row.get("chain_of_harnesses", "").split(";") if n.strip()]

        # connection steps: each passthrough hop, then the final to-device
        connection_steps = hop_chain + [(to_refdes, None, None, None)]

        if len(connection_steps) != len(harnesses):
            step_labels = [s[0] for s in connection_steps]
            raise ValueError(
                f"While building circuits from channel_id '{from_channel_id}' of device "
                f"'{from_refdes}' to channel_id '{to_channel_id}' of device '{to_refdes}', "
                f"found {len(connection_steps)} connection steps: "
                f"{', '.join(step_labels) or 'none'}, "
                f"but expected {len(harnesses)} because there are {len(harnesses)} harnesses "
                f"({', '.join(harnesses) or 'no harnesses listed'}). "
                "chain_of_connectors and chain_of_harnesses must match "
                "(call passthrough_map.resolve())."
            )

        for step in connection_steps:
            entry_face = step[1] if len(step) > 1 else None
            if entry_face is None:
                continue
            mated = mating_harness_of(step[0], entry_face)
            if system_utils._is_real_harness_refdes(mated):
                continue
            raise ValueError(
                f"While building circuits from channel_id '{from_channel_id}' of device "
                f"'{from_refdes}' to channel_id '{to_channel_id}' of device '{to_refdes}', "
                f"connector {entry_face!r} of '{step[0]}' has no harness mated to it. "
                "You can't map this loopback because there is no harness there."
            )

        for from_signal, paired_to_signal in signal_plan:
            recorded_to_signal = (
                paired_to_signal if forced_explicit_signal_map else ""
            )
            current_refdes = from_refdes
            current_side = None
            current_channel_id = from_channel_id
            current_repeat = from_repeat

            for harness_chain_index, (step, harness) in enumerate(zip(connection_steps, harnesses)):
                refdes = step[0]
                side_from = step[1] if len(step) > 1 else None
                side_to = step[2] if len(step) > 2 else None
                mapped_channel_id = step[3] if len(step) > 3 else ""

                if side_from is not None:
                    # passthrough hop
                    if not mapped_channel_id:
                        raise ValueError(
                            f"Missing passthrough_channel_id for {refdes} on "
                            f"{from_refdes}/{from_channel_id}. "
                            "Call passthrough_map.resolve()."
                        )

                    if current_refdes in hop_set:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            from_signal,
                            connector_id=current_side,
                        )
                    else:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            from_signal,
                            repeat_channel_id=current_repeat,
                        )

                    right = resolve_endpoint(
                        refdes,
                        mapped_channel_id,
                        from_signal,
                        connector_id=side_from,
                    )

                    circuits_list.append(
                        {
                            "harness": harness,
                            "harness_chain_index": harness_chain_index,
                            "circuit_id": circuit_id,
                            "from_channel_type": row.get("from_channel_type"),
                            "to_channel_type": row.get("to_channel_type"),
                            "from_signal": from_signal,
                            "to_signal": recorded_to_signal,
                            "harness_from_refdes": left["refdes"],
                            "harness_from_channel_id": left["channel_id"],
                            "harness_from_connector_name": left["connector_id"],
                            "harness_from_cavity": left["cavity"],
                            "harness_to_refdes": right["refdes"],
                            "harness_to_channel_id": right["channel_id"],
                            "harness_to_connector_name": right["connector_id"],
                            "harness_to_cavity": right["cavity"],
                            "from_side_device_refdes": from_refdes,
                            "from_side_device_chname": from_channel_id,
                            "to_side_device_refdes": to_refdes,
                            "to_side_device_chname": to_channel_id,
                            "multi_ch_junction_id": "",
                        }
                    )
                    circuit_id += 1

                    current_refdes = refdes
                    current_side = side_to
                    current_channel_id = mapped_channel_id

                else:
                    # final device step
                    if current_refdes in hop_set:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            from_signal,
                            connector_id=current_side,
                        )
                    else:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            from_signal,
                            repeat_channel_id=current_repeat,
                        )

                    right = resolve_endpoint(
                        refdes,
                        to_channel_id,
                        paired_to_signal,
                        repeat_channel_id=to_repeat,
                    )

                    circuits_list.append(
                        {
                            "harness": harness,
                            "harness_chain_index": harness_chain_index,
                            "circuit_id": circuit_id,
                            "from_signal": from_signal,
                            "to_signal": recorded_to_signal,
                            "from_channel_type": row.get("from_channel_type"),
                            "to_channel_type": row.get("to_channel_type"),
                            "harness_from_refdes": left["refdes"],
                            "harness_from_channel_id": left["channel_id"],
                            "harness_from_connector_name": left["connector_id"],
                            "harness_from_cavity": left["cavity"],
                            "harness_to_refdes": right["refdes"],
                            "harness_to_channel_id": right["channel_id"],
                            "harness_to_connector_name": right["connector_id"],
                            "harness_to_cavity": right["cavity"],
                            "from_side_device_refdes": from_refdes,
                            "from_side_device_chname": from_channel_id,
                            "to_side_device_refdes": to_refdes,
                            "to_side_device_chname": to_channel_id,
                            "multi_ch_junction_id": "",
                        }
                    )
                    circuit_id += 1

    cached_tsv.write(fileio.path("circuits list"), COLUMNS, circuits_list)


def force(from_key, signal_pairs, drop=()):
    """
    Use this when a system build has a pending channel_map.force patch and needs its from-signals paired to to-signals before circuits_list.new.

    Pair the signals of one pending ``channel_map.force()`` patch.

    ``from_key`` is the same endpoint key passed as the first argument to
    ``channel_map.force()``. ``signal_pairs`` maps every from-side signal name
    to a to-side signal name (``{"pos": "live", "neg": "neutral"}``). ``drop``
    lists every to-side signal left unwired (``drop=["earth"]``).

    The circuit keeps the from-side name. The to-side cavity is looked up
    under the paired name. A from-side signal cannot be dropped: if the from
    channel has a signal the to channel does not, swap which endpoint is
    ``from_key`` so the extra name is on the to side, then drop it.

    Raises ``ValueError`` if ``from_key`` is not pending (the signal names
    already matched, or ``channel_map.force()`` was not called), or if any
    from-side name is unpaired or any to-side name is neither paired nor
    dropped.
    """
    if from_key is None or not isinstance(from_key, (tuple, list)) or len(from_key) < 2:
        raise ValueError("circuits_list.force() requires a from_key")
    if isinstance(signal_pairs, str) or not isinstance(signal_pairs, dict):
        raise ValueError(
            "circuits_list.force() signal_pairs must be a dict of "
            "from-signal to to-signal"
        )
    if isinstance(drop, str):
        raise ValueError(
            "circuits_list.force() drop must be a list of to-side signal names"
        )

    from_key = channel_map.canonical_map_key(from_key)
    repeat = ""
    if len(from_key) >= 3:
        repeat = (from_key[2] or "").strip()
    wanted = (
        (from_key[0] or "").strip(),
        (from_key[1] or "").strip(),
        repeat,
    )

    def row_from_key(row):
        return (
            (row.get("from_device_refdes") or "").strip(),
            (row.get("from_device_channel_id") or "").strip(),
            (row.get("from_repeat_channel_id") or "").strip(),
        )

    pending_row = None
    for candidate in channel_map.read_pending():
        if row_from_key(candidate) == wanted:
            pending_row = candidate
            break
    if pending_row is None:
        raise ValueError(
            f"{from_key} is not a pending forced patch. "
            "channel_map.force() records a patch here only when the two channel "
            "types list different signal names. Patches with the same signal names "
            "compile by those names."
        )

    signal_pairs = {
        str(name).strip(): value for name, value in signal_pairs.items()
    }
    drop_list = [str(name).strip() for name in (drop or [])]
    if len(drop_list) != len(set(drop_list)):
        raise ValueError("circuits_list.force() drop lists a signal more than once")

    from_list = [
        part.strip()
        for part in (pending_row.get("from_signals") or "").split(",")
        if part.strip()
    ]
    to_list = [
        part.strip()
        for part in (pending_row.get("to_signals") or "").split(",")
        if part.strip()
    ]
    from_set = set(from_list)
    to_set = set(to_list)
    to_label = ", ".join(to_list) or "none"

    unknown_from = [name for name in signal_pairs if name not in from_set]
    if unknown_from:
        raise ValueError(
            "circuits_list.force() pairs "
            + ", ".join(repr(str(name).strip()) for name in unknown_from)
            + ", which are not signals of the from channel ("
            + (", ".join(from_list) or "none")
            + ")"
        )
    missing_from = [name for name in from_list if name not in signal_pairs]
    if missing_from:
        raise ValueError(
            "circuits_list.force() must pair every from-side signal. Missing "
            + ", ".join(repr(name) for name in missing_from)
        )

    seen_to = []
    normalized_pairs = {}
    for from_name in from_list:
        to_name = str(signal_pairs[from_name]).strip()
        if to_name not in to_set:
            raise ValueError(
                f"circuits_list.force() maps {from_name!r} to {to_name!r}, "
                f"which is not a signal of the to channel ({to_label}). "
                "From-side signals cannot be dropped."
            )
        if to_name in seen_to:
            raise ValueError(
                f"circuits_list.force() uses to-side signal {to_name!r} more than once"
            )
        seen_to.append(to_name)
        normalized_pairs[from_name] = to_name

    overlap = [name for name in drop_list if name in seen_to]
    if overlap:
        raise ValueError(
            "circuits_list.force() both pairs and drops "
            + ", ".join(repr(name) for name in overlap)
        )
    unknown_drop = [name for name in drop_list if name not in to_set]
    if unknown_drop:
        raise ValueError(
            "circuits_list.force() drop lists "
            + ", ".join(repr(name) for name in unknown_drop)
            + f", which are not signals of the to channel ({to_label})"
        )
    drop_set = set(drop_list)
    unpaired_to = [
        name for name in to_list if name not in seen_to and name not in drop_set
    ]
    if unpaired_to:
        raise ValueError(
            "circuits_list.force() must explicitly drop unused to-side signals. "
            "Missing drop for " + ", ".join(repr(name) for name in unpaired_to)
        )

    path = fileio.path("forced signal map")
    existing = cached_tsv.read(path) if os.path.exists(path) else []
    forced = [row for row in existing if row_from_key(row) != wanted]
    for from_name in from_list:
        forced.append(
            {
                "from_device_refdes": pending_row.get("from_device_refdes") or "",
                "from_device_channel_id": pending_row.get("from_device_channel_id") or "",
                "from_repeat_channel_id": pending_row.get("from_repeat_channel_id") or "",
                "to_device_refdes": pending_row.get("to_device_refdes") or "",
                "to_device_channel_id": pending_row.get("to_device_channel_id") or "",
                "to_repeat_channel_id": pending_row.get("to_repeat_channel_id") or "",
                "from_signal": from_name,
                "to_signal": normalized_pairs[from_name],
            }
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cached_tsv.write(path, FORCED_SIGNAL_COLUMNS, forced)
    channel_map.drop_pending(from_key)
