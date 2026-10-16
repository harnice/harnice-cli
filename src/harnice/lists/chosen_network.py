import copy
import json
import math

from harnice import fileio


def end_all_segments_in_nodes(input_network, proximity_threshold=1e-6):
    """
    Processes an input network dict.

    ## Behavior

    - Verifies that each line or spline ends at the location of a node.
    - If two nodes share the same location and the same name, deletes one of them.
    - If a segment endpoint has no matching node, creates one named `f"N{segment_id}A"` or `f"N{segment_id}B"` depending on which end is unmatched.

    ## Errors

    - **Duplicate node:** raises `ValueError` if two nodes share the same location but have different names.
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
    output_network["nodes"] = deduplicated
    nodes = deduplicated

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
    Ensures that every node in the list is present in the network.

    Returns the list of required node ids that do not exist.
    """
    existing_ids = [n["node_id"] for n in input_network.get("nodes", [])]
    missing_nodes = []
    for node_id in set_of_required_nodes:
        if node_id not in existing_ids and node_id not in missing_nodes:
            missing_nodes.append(node_id)
    return missing_nodes


def calculate_possible_sub_networks(input_network, set_of_required_nodes):
    """
    Processes an input dict and searches it for all possible solutions connecting a set of nodes to other nodes via a set of segments.

    Connected segments means segments that share endpoint locations.

    A node is said to be connected to a segment if the node's location equals a segment's endpoint.

    A "solution" is when a set of segments is found that connects all nodes in the set of required nodes.

    There can be zero, one, or many solutions. The output of this function should be a list of network dictionaries that are solutions.

    If zero solutions are found, raise an error.
    """
    segments = input_network.get("segments", [])
    nodes = input_network.get("nodes", [])

    missing = ensure_nodes_exist(input_network, set_of_required_nodes)
    if missing:
        raise ValueError(f"Required nodes not found in network: {missing}")

    if len(set_of_required_nodes) <= 1:
        req_nodes = [n for n in nodes if n["node_id"] in set_of_required_nodes]
        return [{"segments": [], "nodes": req_nodes}]

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
    Processes a list of input dicts and returns just the networks that contain segments or nodes with id's in their respective lists.

    For example...
     - if input networks are [[A, B, C], [C, D, E]] and segments_allowed is [A], only the first network will be returned.
     - if segments_allowed is [B, E], both networks will be returned.
     - if segments_allowed is [C], both networks will be returned.
     - if segments_allowed is [F], neither network will be returned and the list will be empty
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
    Stores a network dict into `fileio.path("chosen network")`.
    """
    with open(fileio.path("chosen network"), "w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)
