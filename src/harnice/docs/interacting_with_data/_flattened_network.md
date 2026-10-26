# Flattened Network
``networks/flat.csv`` is the 2D drawing. ``derive`` is the call a harness script makes. ``map_instance_to_segments`` is what the cable mapper calls for one conductor; a harness script calls ``cable_utils.map_cables_and_conductors_to_segments`` instead.

---
##Columns 
*``derive`` writes this header. A harness script leaves the heading columns in the CSV.*

| Column | Description |
|--------|-------------|
| `segment_id` | id of the 3D segment this row flattens |
| `node_at_end_a` | node id at end A after derive; A is the left end, or the upper end when the segment is vertical |
| `node_at_end_b` | node id at end B |
| `length` | arc length of the 3D curve, recomputed on every derive |
| `length_tolerance` | kept from the previous row with this segment_id; not edited on the 2D page |
| `angle` | heading in degrees from end A to the first bend; 0 is +X and console Y points down |
| `angle_constraint` | match name for that first heading; blank means the heading is independent |
| `subdivisions` | JSON list of {percent, angle, constraint}; percent is in (0, 100) where the next heading starts |


---
##Commands
*These functions are already available in build instructions as `flattened_network`. Use them as written.*
??? info "`flattened_network.derive(network: dict) -> list[dict]`"

    Use this when a harness build needs networks/flat.csv, and the node and segment instances, updated from the chosen network. Skip it when the project does not need the flat drawing.
    
    Build the flattened-network CSV from a chosen network, and update the node and segment instances to match.
    
    The network decides which rows exist and sets ``segment_id``,
    ``node_at_end_a``, ``node_at_end_b``, and ``length``. ``length`` is the
    3D curve length. The 3D page stores each ``spline_control_points`` triple
    as an offset from end A. ``spline_length`` places those stored triples in
    the Bezier polygon with the two ends and does not add end A.
    
    ``length_tolerance``, ``angle``, ``angle_constraint``, and
    ``subdivisions`` already saved for a ``segment_id`` are kept. ``angle``
    is the heading from end A to the first bend. Each subdivision is a
    percent of length where the next heading starts. When the 3D ends come
    back swapped versus the saved row, those spans are reversed so the
    drawing stays. A first heading in ``[90, 270)`` swaps the CSV ends and
    adds 180° to each heading, so A is left of B, or above B when the
    segment is vertical.
    
    On the instances list, each node receives ``2d_translate`` ``{x, y}``,
    parent ``origin`` / ``origin``, ``absolute_rotation``, and
    ``3d_translate`` from the network node. A node id with no instance is
    created as ``item_type`` ``"node"``. Each segment is created or updated
    as ``item_type`` ``"segment"``, parented to end A on ``"origin"``, with
    ``length`` rounded to 2 digits.
    
    **Args:**
    - `network`: Network dict with ``"segments"`` and ``"nodes"``, such as a chosen network.
    
    **Returns:**
    - `list`: The flattened rows that were written.

??? info "`flattened_network.map_instance_to_segments(instance)`"

    Use this when cable routing needs one instance split into a segment instance for each segment between its ends. A harness script calls cable_utils.map_cables_and_conductors_to_segments instead.
    
    Maps a segment-based instance across multiple segments using pathfinding.
    
    Takes an instance that spans between two nodes and creates segment-specific
    instances for each segment in the path between those nodes. Uses breadth-first
    search to find the path through the segment graph, then creates one
    ``{item_type}-segment`` instance per segment carrying the direction it is
    traversed in and its order along the path.
    
    **Note:** Cavity endpoints are resolved to the ``node`` in the same connector
    group. If ``node_at_end_a`` / ``node_at_end_b`` are already ``item_type=="node"``
    instances, they are used directly. When both ends resolve to the same node,
    the instance is a loopback: it is mapped out and back on the free stub
    leaving that connector, and each hop's ``length`` is twice the segment
    length.
    
    **Args:**
    
    - `instance` (dict): Instance dictionary with `location_type="segment"` that has
        `node_at_end_a` and `node_at_end_b` defined.
    
    **Raises:**
    
    - `ValueError`: If the instance is not segment-based, if endpoints are missing,
        if endpoints are not nodes, or if no path is found between the nodes.

