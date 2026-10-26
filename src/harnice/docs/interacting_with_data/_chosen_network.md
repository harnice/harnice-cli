# Chosen Network
``networks/chosen.json`` is the one route Build kept. It uses the same node and segment shape as the available network. A move that must survive the next build is applied to that dict after one solution is chosen and before ``save``. Every ``bundle_network_utils`` call returns a new dict.

---
##Commands
*These functions are already available in build instructions as `chosen_network`. Use them as written.*
??? info "`chosen_network.end_all_segments_in_nodes(input_network, proximity_threshold=1e-06)`"

    Use this when a harness build needs every segment end closed on a node in the chosen network.
    
    Give every segment end a node, and reject two different nodes at one location or two segments on the same endpoints.
    
    **Behavior**
    
    - Verifies that each line or spline ends at the location of a node.
    - If two nodes share the same location and the same name, deletes one of them.
    - Mating-connector nodes that share a location become one node. Its id is
      ``{nodea+nodeb}``, with the connector ids in order. A fasten record is
      not consulted: only the locations matter. A node is a mating-connector
      node when it carries ``mate`` or ``mates``.
    - If a segment endpoint has no matching node, creates one named `f"N{segment_id}A"` or `f"N{segment_id}B"` depending on which end is unmatched.
    
    **Errors**
    
    - **Duplicate node:** raises `ValueError` if two nodes share the same location and they are not both mating-connector nodes.
    - **Duplicate segment:** raises `ValueError` if two segments share the same pair of endpoints.
    
    **Args**
    
    - **input_network** — Network dict with `"segments"` and `"nodes"` keys.
    - **proximity_threshold** — Max distance between two points to be considered the same location. Defaults to `1e-6`.
    
    **Returns**
    
    A deep copy of `input_network` with deduplication applied and any missing nodes added.

??? info "`chosen_network.ensure_nodes_exist(input_network, set_of_required_nodes)`"

    Use this when a harness build needs the required node ids that are still missing from a network.
    
    Return the required node ids that are not in the network.
    
    The network is not modified. Missing ids come back in first-seen order.
    
    **Args**
    
    - **input_network** — Network dict with a ``"nodes"`` list. Each node needs a ``node_id``. The network is not modified.
    - **set_of_required_nodes** — Node ids that must already be in the network. The return value is the ids from this list that are missing, in first-seen order.

??? info "`chosen_network.calculate_possible_sub_networks(input_network, set_of_required_nodes)`"

    Use this when a harness build needs every minimal route that joins a set of required nodes.
    
    Return every minimal subnetwork that joins all of the required nodes.
    
    Connected segments means segments that share endpoint locations.
    
    A node is said to be connected to a segment if the node's location equals a segment's endpoint.
    
    A "solution" is when a set of segments is found that connects all nodes in the set of required nodes.
    
    There can be zero, one, or many solutions. The output of this function should be a list of network dictionaries that are solutions.
    
    If zero solutions are found, raise an error.
    
    When exactly one node is required, every segment that leaves that node is kept, with the node at its other end. That other node does not have to be an instance. A lone connector still carries its available-network stub. Zero required nodes still return no segments.
    
    **Args**
    
    - **input_network** — Network dict with ``"segments"`` and ``"nodes"``. A segment is connected to a node when they share an endpoint location.
    - **set_of_required_nodes** — Node ids one subnetwork must connect. Raises if any id is missing from the network, or if no connecting subnetwork exists. Returns a list of network dicts, one per minimal solution.

??? info "`chosen_network.find_network_with(input_networks, segment_ids=[], node_ids=[])`"

    Use this when a harness build got more than one route and needs the one that contains a segment id or a node id the user named. Both id lists empty matches nothing.
    
    Keep the networks that contain any listed segment id or any listed node id.
    
    A network of segments A, B, C and a network of segments C, D, E:
    
    - ``segment_ids=["A"]`` keeps the first network.
    - ``segment_ids=["B", "E"]`` keeps both.
    - ``segment_ids=["C"]`` keeps both.
    - ``segment_ids=["F"]`` keeps nothing.
    
    Both ``segment_ids`` and ``node_ids`` empty matches nothing. Call this
    only when more than one solution came back and a stable id was named.
    
    **Args**
    
    - **input_networks** — List of network dicts to filter.
    - **segment_ids** — Segment ids to look for. A network is kept when it contains any of these. Optional; pass an empty list to ignore segments.
    - **node_ids** — Node ids to look for. A network is kept when it contains any of these or any of ``segment_ids``. Optional; pass an empty list to ignore nodes. If both lists are empty, nothing matches.

??? info "`chosen_network.save(network)`"

    Use this when a harness build has finished changing the chosen network and needs that dict written to disk.
    
    Replace the chosen-network file with this network dict.
    
    **Args**
    
    - **network** — Network dict to write. Replaces the chosen-network file.

