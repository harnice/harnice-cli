import os
from harnice import fileio
from harnice.lists import cached_tsv, channel_map, passthrough_map
from harnice.project_types import chtype
from harnice.utils import system_utils

COLUMNS = [
    "harness", #documentation needed
    "harness_chain_index",  # 0-based index into channel map ``chain_of_harnesses`` for this segment
    "circuit_id", #documentation needed
    "signal", #documentation needed
    "harness_from_refdes", #documentation needed
    "harness_from_channel_id", #documentation needed
    "harness_from_connector_name", #documentation needed
    "harness_from_cavity", #documentation needed
    "harness_to_refdes", #documentation needed
    "harness_to_channel_id", #documentation needed
    "harness_to_connector_name", #documentation needed
    "harness_to_cavity", #documentation needed
    "from_side_device_refdes", #documentation needed
    "from_side_device_chname", #documentation needed
    "to_side_device_refdes", #documentation needed
    "to_side_device_chname", #documentation needed
    "from_channel_type", #documentation needed
    "to_channel_type", #documentation needed
    "multi_ch_junction_id",  # set when the circuit is from_channel.signal → mcj.signal
]


def read():
    """Return the circuits list (cached)."""
    return cached_tsv.read(fileio.path("circuits list"))


def new():
    """
    Build the circuits list from the channel map and passthrough map.

    Uses ``chain_of_connectors`` / ``chain_of_harnesses`` (from ``passthrough_map.resolve()``)
    and ordered ``satisfaction`` rows on the passthrough map for passthrough channel IDs.

    A channel-map row with ``multi_ch_junction_id`` and no ``to_*`` partner becomes
    one circuit per signal: from is ``from_channel.signal``, to is ``mcj.signal``.
    Signal names come from the first channel type seen on that junction id.

    Overwrites any existing circuits list.
    """
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
                    "signal": signal,
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

        signals = chtype.signals(row.get("from_channel_type"))

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

        for signal in signals:
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
                            signal,
                            connector_id=current_side,
                        )
                    else:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            signal,
                            repeat_channel_id=current_repeat,
                        )

                    right = resolve_endpoint(
                        refdes,
                        mapped_channel_id,
                        signal,
                        connector_id=side_from,
                    )

                    circuits_list.append(
                        {
                            "harness": harness,
                            "harness_chain_index": harness_chain_index,
                            "circuit_id": circuit_id,
                            "from_channel_type": row.get("from_channel_type"),
                            "to_channel_type": row.get("to_channel_type"),
                            "signal": signal,
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
                            signal,
                            connector_id=current_side,
                        )
                    else:
                        left = resolve_endpoint(
                            current_refdes,
                            current_channel_id,
                            signal,
                            repeat_channel_id=current_repeat,
                        )

                    right = resolve_endpoint(
                        refdes,
                        to_channel_id,
                        signal,
                        repeat_channel_id=to_repeat,
                    )

                    circuits_list.append(
                        {
                            "harness": harness,
                            "harness_chain_index": harness_chain_index,
                            "circuit_id": circuit_id,
                            "signal": signal,
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
