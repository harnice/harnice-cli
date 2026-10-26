import copy
import json
import math
import re

from harnice import fileio


def _connector_ids(node):
    """Connector ids a mating-connector node stands for, in stored order."""
    mates = node.get("mates")
    if isinstance(mates, list) and mates:
        ids = []
        for mate in mates:
            if isinstance(mate, dict) and mate.get("device") and mate.get("mate"):
                ids.append(f"{mate['device']}.{mate['mate']}")
        if ids:
            return ids
    mate = node.get("mate")
    if isinstance(mate, dict) and mate.get("device") and mate.get("mate"):
        return [f"{mate['device']}.{mate['mate']}"]
    node_id = str(node.get("node_id") or "")
    if node_id.startswith("{") and node_id.endswith("}") and "+" in node_id:
        return [part for part in node_id[1:-1].split("+") if part]
    return []


def _is_mate_node(node):
    return bool(_connector_ids(node))


def _coalesce_coincident_mate_nodes(nodes, near):
    """One node per point shared by mating connectors. Other nodes stay put."""

    def _node_id_key(text):
        return [
            int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", str(text))
        ]

    def _combined_node_id(ids):
        ordered = sorted(set(ids), key=_node_id_key)
        if len(ordered) <= 1:
            return ordered[0] if ordered else ""
        return "{" + "+".join(ordered) + "}"

    kept = []
    clusters = []
    for node in nodes:
        if not _is_mate_node(node):
            kept.append(node)
            continue
        location = tuple(node["location"])
        for cluster_location, group in clusters:
            if near(location, cluster_location):
                group.append(node)
                break
        else:
            clusters.append((location, [node]))
    for _location, group in clusters:
        ids = []
        for node in group:
            for connector_id in _connector_ids(node):
                if connector_id not in ids:
                    ids.append(connector_id)
        ordered = sorted(ids, key=_node_id_key)
        lead_id = ordered[0]
        lead = group[0]
        for node in group:
            if lead_id in _connector_ids(node):
                lead = node
                break
        device, mate = lead_id.rsplit(".", 1)
        combined = {
            "node_id": _combined_node_id(ordered),
            "location": list(lead["location"]),
            "alpha": lead.get("alpha"),
            "beta": lead.get("beta"),
            "gamma": lead.get("gamma"),
            "mate": {"device": device, "mate": mate},
        }
        if len(ordered) > 1:
            combined["mates"] = [
                {"device": item.rsplit(".", 1)[0], "mate": item.rsplit(".", 1)[1]}
                for item in ordered
            ]
        kept.append(combined)
    return kept


def end_all_segments_in_nodes(input_network, proximity_threshold=1e-6):
    """
    Use this when a harness build needs every segment end closed on a node in the chosen network.

    Give every segment end a node, and reject two different nodes at one location or two segments on the same endpoints.

    ## Behavior

    - Verifies that each line or spline ends at the location of a node.
    - If two nodes share the same location and the same name, deletes one of them.
    - Mating-connector nodes that share a location become one node. Its id is
      ``{nodea+nodeb}``, with the connector ids in order. A fasten record is
      not consulted: only the locations matter. A node is a mating-connector
      node when it carries ``mate`` or ``mates``.
    - If a segment endpoint has no matching node, creates one named `f"N{segment_id}A"` or `f"N{segment_id}B"` depending on which end is unmatched.

    ## Errors

    - **Duplicate node:** raises `ValueError` if two nodes share the same location and they are not both mating-connector nodes.
    - **Duplicate segment:** raises `ValueError` if two segments share the same pair of endpoints.

    ## Args

    - **input_network** — Network dict with `"segments"` and `"nodes"` keys.
    - **proximity_threshold** — Max distance between two points to be considered the same location. Defaults to `1e-6`.

    ## Returns

    A deep copy of `input_network` with deduplication applied and any missing nodes added.
    """
    output_network = copy.deepcopy(input_network)
    nodes = output_network.setdefault("nodes", [])
    segments = output_network.setdefault("segments", [])

    def _dist(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def _near(a, b):
        return _dist(a, b) <= proximity_threshold

    # Step 1: deduplicate nodes that share both location and node_id
    deduplicated = []
    for node in nodes:
        loc = tuple(node["location"])
        nid = node["node_id"]
        if not any(
            _near(loc, tuple(n["location"])) and nid == n["node_id"]
            for n in deduplicated
        ):
            deduplicated.append(node)
    output_network["nodes"] = _coalesce_coincident_mate_nodes(deduplicated, _near)
    nodes = output_network["nodes"]

    # Step 2: raise if two distinct nodes share a location
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if _near(tuple(a["location"]), tuple(b["location"])):
                raise ValueError(
                    f"Duplicate node location: '{a['node_id']}' and '{b['node_id']}' "
                    f"both occupy {a['location']}."
                )

    # Step 3: raise if two segments share the same endpoint pair
    seen_pairs = []
    for seg in segments:
        ea = tuple(seg["location_at_end_a"])
        eb = tuple(seg["location_at_end_b"])
        for prev_id, prev_ea, prev_eb in seen_pairs:
            if (_near(ea, prev_ea) and _near(eb, prev_eb)) or (
                _near(ea, prev_eb) and _near(eb, prev_ea)
            ):
                raise ValueError(
                    f"Duplicate segment: '{seg['segment_id']}' and '{prev_id}' "
                    f"share the same endpoints."
                )
        seen_pairs.append((seg["segment_id"], ea, eb))

    # Step 4: ensure every segment endpoint has a node; create one if missing
    for seg in segments:
        for label, end_loc in (
            ("A", tuple(seg["location_at_end_a"])),
            ("B", tuple(seg["location_at_end_b"])),
        ):
            if not any(_near(end_loc, tuple(n["location"])) for n in nodes):
                new_node = {
                    "node_id": f"N{seg['segment_id']}{label}",
                    "location": list(end_loc),
                    "alpha": None,
                    "beta": None,
                    "gamma": None,
                }
                nodes.append(new_node)

    return output_network


def ensure_nodes_exist(input_network, set_of_required_nodes):
    """
    Use this when a harness build needs the required node ids that are still missing from a network.

    Return the required node ids that are not in the network.

    The network is not modified. Missing ids come back in first-seen order.

    ## Args

    - **input_network** — Network dict with a ``"nodes"`` list. Each node needs a ``node_id``. The network is not modified.
    - **set_of_required_nodes** — Node ids that must already be in the network. The return value is the ids from this list that are missing, in first-seen order.
    """
    existing_ids = [n["node_id"] for n in input_network.get("nodes", [])]
    missing_nodes = []
    for node_id in set_of_required_nodes:
        if node_id not in existing_ids and node_id not in missing_nodes:
            missing_nodes.append(node_id)
    return missing_nodes


def calculate_possible_sub_networks(input_network, set_of_required_nodes):
    """
    Use this when a harness build needs every minimal route that joins a set of required nodes.

    Return every minimal subnetwork that joins all of the required nodes.

    Connected segments means segments that share endpoint locations.

    A node is said to be connected to a segment if the node's location equals a segment's endpoint.

    A "solution" is when a set of segments is found that connects all nodes in the set of required nodes.

    There can be zero, one, or many solutions. The output of this function should be a list of network dictionaries that are solutions.

    If zero solutions are found, raise an error.

    When exactly one node is required, every segment that leaves that node is kept, with the node at its other end. That other node does not have to be an instance. A lone connector still carries its available-network stub. Zero required nodes still return no segments.

    ## Args

    - **input_network** — Network dict with ``"segments"`` and ``"nodes"``. A segment is connected to a node when they share an endpoint location.
    - **set_of_required_nodes** — Node ids one subnetwork must connect. Raises if any id is missing from the network, or if no connecting subnetwork exists. Returns a list of network dicts, one per minimal solution.
    """
    segments = input_network.get("segments", [])
    nodes = input_network.get("nodes", [])

    missing = ensure_nodes_exist(input_network, set_of_required_nodes)
    if missing:
        raise ValueError(f"Required nodes not found in network: {missing}")

    if len(set_of_required_nodes) <= 1:
        req_nodes = [n for n in nodes if n["node_id"] in set_of_required_nodes]
        if len(req_nodes) != 1:
            return [{"segments": [], "nodes": req_nodes}]
        hub = req_nodes[0]
        hub_loc = tuple(hub["location"])
        node_at = {tuple(node["location"]): node for node in nodes}
        stub_segments = []
        stub_nodes = {hub["node_id"]: hub}
        for seg in segments:
            end_a = tuple(seg.get("location_at_end_a") or [])
            end_b = tuple(seg.get("location_at_end_b") or [])
            if end_a == hub_loc:
                other = node_at.get(end_b)
            elif end_b == hub_loc:
                other = node_at.get(end_a)
            else:
                continue
            if other is None or other["node_id"] == hub["node_id"]:
                continue
            stub_segments.append(seg)
            stub_nodes[other["node_id"]] = other
        return [{"segments": stub_segments, "nodes": list(stub_nodes.values())}]

    # Map location tuples to node_ids
    loc_to_node = {}
    for node in nodes:
        loc_to_node[tuple(node["location"])] = node["node_id"]

    # Build adjacency: node_id -> list of (segment_id, neighbor_node_id)
    adj = {node["node_id"]: [] for node in nodes}
    for seg in segments:
        na = loc_to_node.get(tuple(seg["location_at_end_a"]))
        nb = loc_to_node.get(tuple(seg["location_at_end_b"]))
        if na and nb:
            adj[na].append((seg["segment_id"], nb))
            adj[nb].append((seg["segment_id"], na))

    seg_by_id = {seg["segment_id"]: seg for seg in segments}
    node_by_id = {node["node_id"]: node for node in nodes}

    required = frozenset(set_of_required_nodes)
    start = next(iter(sorted(required)))

    # Collect all minimal Steiner trees (frozensets of segment_ids).
    # "Minimal" means no proper subset is also a valid solution.
    found: set[frozenset] = set()
    # Track visited segment sets to avoid redundant exploration.
    visited_states: set[frozenset] = set()

    def dfs(reachable: frozenset, used: frozenset) -> None:
        if used in visited_states:
            return
        visited_states.add(used)

        if required <= reachable:
            # Drop any previously found solution that is a proper superset of this one.
            to_remove = [s for s in found if used < s]
            for s in to_remove:
                found.discard(s)
            found.add(used)
            return

        for node_id in reachable:
            for seg_id, neighbor in adj.get(node_id, []):
                if neighbor not in reachable:
                    new_used = used | {seg_id}
                    # Prune: a known solution is already a subset — extending further
                    # cannot produce a new minimal solution.
                    if not any(prev <= new_used for prev in found):
                        dfs(reachable | {neighbor}, new_used)

    dfs(frozenset({start}), frozenset())

    if not found:
        raise ValueError(
            f"No subnetwork found that connects all required nodes: {set_of_required_nodes}"
        )

    subnetworks = []
    for seg_set in found:
        sol_segs = [seg_by_id[sid] for sid in sorted(seg_set)]
        touched_ids: set[str] = set()
        for seg in sol_segs:
            for loc_key in (
                tuple(seg["location_at_end_a"]),
                tuple(seg["location_at_end_b"]),
            ):
                nid = loc_to_node.get(loc_key)
                if nid:
                    touched_ids.add(nid)
        sol_nodes = [
            node_by_id[nid] for nid in sorted(touched_ids) if nid in node_by_id
        ]
        subnetworks.append({"segments": sol_segs, "nodes": sol_nodes})

    return subnetworks  # list of networks


def find_network_with(input_networks, segment_ids=[], node_ids=[]):
    """
    Use this when a harness build got more than one route and needs the one that contains a segment id or a node id the user named. Both id lists empty matches nothing.

    Keep the networks that contain any listed segment id or any listed node id.

    A network of segments A, B, C and a network of segments C, D, E:

    - ``segment_ids=["A"]`` keeps the first network.
    - ``segment_ids=["B", "E"]`` keeps both.
    - ``segment_ids=["C"]`` keeps both.
    - ``segment_ids=["F"]`` keeps nothing.

    Both ``segment_ids`` and ``node_ids`` empty matches nothing. Call this
    only when more than one solution came back and a stable id was named.

    ## Args

    - **input_networks** — List of network dicts to filter.
    - **segment_ids** — Segment ids to look for. A network is kept when it contains any of these. Optional; pass an empty list to ignore segments.
    - **node_ids** — Node ids to look for. A network is kept when it contains any of these or any of ``segment_ids``. Optional; pass an empty list to ignore nodes. If both lists are empty, nothing matches.
    """
    found_networks = []
    for network in input_networks:
        net_seg_ids = {seg["segment_id"] for seg in network.get("segments", [])}
        net_node_ids = {node["node_id"] for node in network.get("nodes", [])}
        if any(sid in net_seg_ids for sid in segment_ids) or any(
            nid in net_node_ids for nid in node_ids
        ):
            found_networks.append(network)
    return found_networks  # list of networks


def save(network):
    """
    Use this when a harness build has finished changing the chosen network and needs that dict written to disk.

    Replace the chosen-network file with this network dict.

    ## Args

    - **network** — Network dict to write. Replaces the chosen-network file.
    """
    with open(fileio.path("chosen network"), "w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)
