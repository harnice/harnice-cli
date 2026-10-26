# Bundle Network Utilities

These functions turn an available network into the chosen network. The available network is the starting shape, already on disk: a route drawn in this Harnice project, imported from CAD with ``available_network.source_context_from_path``, or copied from another Harnice project with ``available_network.source_available_network_from_project``. The chosen network is that route after the harness build changes it, and it is the network that defines the harness.

The build script is that transformation. Each call changes a small piece and returns a new dict. Assign the dict it returns and use that as the network from then on:

    network = bundle_network_utils.move_node(network, node_id, direction=offset)

Load the available network, give every free segment end a node, add any connector node the available network does not yet contain, and keep the one route that touches every required node. Layout moves belong after that one route exists and before ``chosen_network.save``. ``flattened_network.derive`` then builds the flat drawing from the chosen network.

``chosen_network.end_all_segments_in_nodes``, ``ensure_nodes_exist``, ``calculate_possible_sub_networks``, and ``find_network_with`` do the first part of that. ``new_node`` adds a node and does not add a segment. ``move_node``, ``rename_node``, ``reroute_segment``, and ``clock_backshell`` edit the chosen route. A connector group with a backshell is clocked toward its hop with ``clock_backshell``, which already shifts the node by the connector mate. A group with no backshell keeps that mate on the available-network point with ``move_node`` and ``output_offset(..., "3d-mate")``.

The chosen network is a dict with ``"nodes"`` and ``"segments"``.

A coordinate system is a different dict, ``{x, y, z, alpha, beta, gamma}``. ``x``, ``y``, and ``z`` are the position. ``alpha``, ``beta``, and ``gamma`` are degrees about X, Y, and Z. The rotation is ``Rx(alpha) · Ry(beta) · Rz(gamma)``, so Z is applied first, then Y, then X. ``output_offset`` and ``difference_between_csys`` return one of these dicts. Pass it to ``move_node`` as ``direction``.

---
##Commands
*These functions are already available in build instructions as `bundle_network_utils`. Use them as written.*
??? info "`bundle_network_utils.compose_csys(*csys_list)`"

    Use this when a harness build needs one pose made by stacking child coordinate systems.
    
    Compose child CSYS dicts left to right.
    
    Each next CSYS is expressed in the previous CSYS's frame. Returns
    ``{x, y, z, alpha, beta, gamma}`` in the first CSYS's parent frame.
    
    **Args:**
    - `csys_list`: One or more child CSYS dicts, in order from parent to child. Each dict may include ``x``, ``y``, ``z``, ``alpha``, ``beta``, and ``gamma``. Pass them as separate positional arguments. Optional; with none, the result is the origin with no rotation.

??? info "`bundle_network_utils.invert_csys(csys)`"

    Use this when a harness build needs the opposite of a child coordinate system.
    
    Return the opposite of a child CSYS.
    
    The result takes the child frame back to its parent origin: if ``csys``
    is a connector mate relative to the part origin, ``invert_csys(csys)``
    is the shift that puts that mate on the origin.
    
    **Args:**
    - `csys`: Child CSYS dict ``{x, y, z, alpha, beta, gamma}``, expressed in its parent frame. The result is the opposite shift, the one that brings that child frame back to the parent origin.

??? info "`bundle_network_utils.difference_between_csys(instance, from_csys, to_csys)`"

    Use this when a harness build needs the move from one coordinate system to another before passing it to move_node.
    
    Direction that takes ``to_csys`` onto ``from_csys``.
    
    Pass the result to ``move_node`` as the move direction. Typical use:
    keep a connector mating face on the original available-network point
    with ``from_csys="origin"`` and ``to_csys="3d-mate"``.
    
    **Args**
    
    - **instance** — Instance dict, ``instance_name``, or ``connector_group``.
      Named children may live on different items in the same group; the
      parent CSYS stack is composed (backshell ``3d-connector``, each
      instance ``3d_translate``, then connector ``3d-mate``).
    - **from_csys** — Child name or ``"origin"``. This is where ``to_csys``
      should land.
    - **to_csys** — Child name or ``"origin"``. The CSYS that moves.
    
    **Returns**
    
    A CSYS dict ``{x, y, z, alpha, beta, gamma}`` in the node frame.

??? info "`bundle_network_utils.calculate_location_3d(lookup_instance, instances)`"

    Use this when a harness build needs an instance's world pose from the chain of parent coordinate systems.
    
    Calculates the 3D world pose of an instance from the CSYS chain.
    
    Same walk and order as ``flattened_network.calculate_location``: origin of
    the master file is ``(0, 0, 0)``, then each parent CSYS along the chain.
    At every link:
    
    1. Parent output CSYS offset is applied in the current (parent) frame.
    2. Parent output CSYS rotation is composed on.
    3. Instance ``3d_translate`` ``{x, y, z, alpha, beta, gamma}`` is applied
       in that same frame, then its rotation is composed on. When
       ``3d_translate`` is blank, ``2d_translate`` ``{x, y, rotate}`` is used
       (``rotate`` about Z, like 2D).
    
    Angles are ZYX Euler degrees matching the console node triad
    (``α`` about X, ``β`` about Y, ``γ`` about Z;
    ``R = Rx(alpha) · Ry(beta) · Rz(gamma)``). Each link's rotation is
    composed onto the next so a child inherits every ancestor heading.
    A 2D ``csys_children`` ``rotation`` is about drawing Z, so it becomes
    ``gamma``. ``absolute_rotation`` is the 2D formboard heading and is
    not applied here.
    
    Args:
        lookup_instance (dict): The instance dictionary to calculate coordinates for.
        instances (list): List of all instance dictionaries needed to resolve the parent chain.
    
    Returns:
        tuple: ``(x, y, z, alpha, beta, gamma)`` in the same units as ``3d_translate``
            (inches) and degrees.
    
    Raises:
        ValueError: If parent coordinate system information is missing or invalid, or
            if parent instances cannot be found in the instances list.

??? info "`bundle_network_utils.move_node(input_network, node_id, direction=None, new_location=None, new_rotation=None, output_csys=None)`"

    Use this when a harness build needs one node of the chosen network moved, along with the segment ends that sit on it.
    
    Moves one node in a network.
    
    **Args**
    
    - **input_network** — Network dict with ``"segments"`` and ``"nodes"``.
    - **node_id** — Which node in the network to move.
    - **direction** — Which way to move it: a CSYS dict in the node's
      current frame, usually from ``difference_between_csys``. Segment
      endpoints that sit on the old location follow the node. Optional.
      Omit this when you pass ``new_location``.
    - **new_location** — Absolute world position ``[x, y, z]``. Use this
      instead of ``direction`` when you already know the destination.
      Segment endpoints on the old location follow the node. Optional.
    - **new_rotation** — Absolute ``[alpha, beta, gamma]`` in degrees,
      applied together with ``new_location``. Ignored when ``direction``
      or ``output_csys`` is set. Optional.
    - **output_csys** — Alias for ``direction``: a CSYS dict in the node's
      current frame. Optional.
    
    **Returns**
    
    A deep copy of ``input_network`` with the node and its incident
    segment geometry updated.
    
    **Errors**
    
    - **ValueError** if the node is missing, or if no direction or
      ``new_location`` is given.

??? info "`bundle_network_utils.adjacent_nodes(input_network, from_node)`"

    Use this when a harness build needs the nodes one segment away from a given node.
    
    Traverses the network from a given node and returns a list of dicts representing nodes that are one segment of connection away.
    
    The dict should contain node_id, delta_x, delta_y, and delta_z.
    
    Deltas are calculated by finding the relative position of each node with respect to the from_node coordinate system.
    
    **Args**
    
    - **input_network** — Network dict to traverse. Segments connect nodes that share an endpoint location.
    - **from_node** — Node dict to start from. It needs ``location``. Include ``alpha``, ``beta``, and ``gamma`` when deltas should be in that node's frame; if any angle is missing, deltas are in global coordinates.

??? info "`bundle_network_utils.path_angle(input_network, node_id, toward='incident', axis='x', zero='y', if_along_axis=None)`"

    Use this when a harness build needs the angle of one hop away from a node, in that node's frame.
    
    Angle of a hop in a node's frame, in degrees ``[0, 360)``.
    
    ``θ`` is the right-hand angle from ``zero`` to the hop, about ``axis``.
    Defaults match a clock about +X from +Y: ``atan2(z, y)``.
    
    **Args:**
    - `input_network` (dict): Network with ``"segments"`` and ``"nodes"``.
    - `node_id` (str): Node whose frame is used.
    - `toward` (str): ``"incident"`` for the unique neighbor, or a node id.
    - `axis` (str): ``"x"``, ``"y"``, or ``"z"``.
    - `zero` (str): Axis that is θ = 0.
    - `if_along_axis`: If the hop is along ``axis``, return this instead of
        raising (use ``0`` for a straight exit).
    
    **Returns:**
    - `float`: Angle in degrees.
    
    **Raises:**
    - `ValueError`: If the hop cannot be resolved, or is along ``axis`` when
        ``if_along_axis`` is omitted.

??? info "`bundle_network_utils.output_csys(instance, csys_name)`"

    Use this when a harness build needs a named output coordinate system on one instance, without walking its parents.
    
    Named output CSYS on one instance (no parent-chain walk).
    
    **Args:**
    - `instance`: Instance dict, instance name, or connector group.
    - `csys_name` (str): Child name (``"3d-mate"``, ``"connector"``, …).
    
    **Returns:**
    - `dict`: ``{x, y, z, alpha, beta, gamma}``.
    
    **Raises:**
    - `ValueError`: If the instance or CSYS is missing.

??? info "`bundle_network_utils.output_offset(instance, csys_name, about=None, angle=0)`"

    Use this when a harness build needs the node move taken from one output coordinate system, such as a connector's 3d-mate.
    
    Node move taken from one instance output CSYS.
    
    ``invert(output)``, then optionally ``rotate_csys`` about ``about``.
    Pass the result to ``move_node``. This is any part's "how far is the
    origin from this feature," not a connector-only helper.
    
    **Args:**
    - `instance`: Instance dict, instance name, or connector group.
    - `csys_name` (str): Child name on that instance.
    - `about` (str): ``"x"``, ``"y"``, or ``"z"`` to spin the offset.
    - `angle` (float): Degrees about ``about``. Ignored if ``about`` is blank.
    
    **Returns:**
    - `dict`: CSYS in the current node frame.

??? info "`bundle_network_utils.rotate_csys(csys, angle, about='x')`"

    Use this when a harness build needs a child coordinate system rotated about one parent axis.
    
    Rotate a child CSYS about a parent axis.
    
    ``R = R_about(angle) · csys`` in the parent frame.
    
    **Args:**
    - `csys` (dict): ``{x, y, z, alpha, beta, gamma}`` or a library child.
    - `angle` (float): Rotation in degrees, applied in the parent frame before the CSYS's own rotation.
    - `about` (str): ``"x"``, ``"y"``, or ``"z"``.
    
    **Returns:**
    - `dict`: The rotated CSYS.

??? info "`bundle_network_utils.spin(instance_name, angle, about='x')`"

    Use this when a harness build needs one rotation component written on an instance, such as un-clocking a connector after clocking its backshell.
    
    Write one Euler component of ``3d_translate`` on an instance.
    
    Use the opposite of a ``path_angle`` when a child should not inherit a
    parent spin (un-clock a connector after a clocked backshell move).
    
    **Args:**
    - `instance_name` (str): Instance to rotate in its parent CSYS.
    - `angle` (float): Rotation in degrees about the axis given by ``about``.
    - `about` (str): ``"x"`` → ``alpha``, ``"y"`` → ``beta``, ``"z"`` → ``gamma``.
    
    **Returns:**
    - `float`: The angle written, normalized to ``[0, 360)``.
    
    **Raises:**
    - `ValueError`: If the name is blank, the instance is missing, or the
        angle is not a finite number.

??? info "`bundle_network_utils.clock_backshell(network, connector_group, towards_node='incident', round_to_nearest_angle=None)`"

    Use this when a harness build needs a backshell clocked on its connector group toward another node.
    
    Clock a backshell on ``connector_group`` and un-clock its connector.
    
    1. ``θ = path_angle`` from the group node toward ``towards_node``.
    2. ``move_node`` by the connector ``3d-mate`` output offset.
    3. ``move_node`` by the backshell ``connector`` output offset, spun about X
       by θ (snapped if ``round_to_nearest_angle`` is set).
    4. ``spin`` the connector by ``-θ`` so the mate keeps its orientation.
    5. Apply a ``build_note`` on the connector. Connector up is +Y, so the
       shop clock starts at +Y, not +X: clockwise from the mating face is
       ``90° - θ``.
    
    **Args:**
    - `network` (dict): Chosen network, still at available poses.
    - `connector_group` (str): Group that owns the node, connector, and backshell.
    - `towards_node` (str): Neighbor to aim at, or ``"incident"`` for the
        unique hop. Defaults to ``"incident"``.
    - `round_to_nearest_angle` (float): If set, snap θ to this many degrees
        (detents). Omit or ``None`` to keep the raw angle.
    
    **Returns:**
    - `dict`: Updated network.
    
    **Raises:**
    - `ValueError`: If the group, connector, backshell, or hop cannot be found.

??? info "`bundle_network_utils.rename_node(input_network, new_id, existing_id=None, coordinates=[])`"

    Use this when a harness build needs a node's id changed in the chosen network.
    
    Finds a node and changes its id.
    
    If existing ID is used, that's self-explanatory.
    
    If coordinates are given in form {x, y, z, radius} and not 1 node is in the sphere, raise an error.
    
    **Args**
    
    - **input_network** — Network dict. A copy is returned; the input is not modified.
    - **new_id** — ``node_id`` to assign to the found node.
    - **existing_id** — Current ``node_id`` to rename. Use this or ``coordinates``. Optional.
    - **coordinates** — ``[x, y, z, radius]``. Renames the single node inside that sphere. Raises unless the sphere contains exactly one node. Optional. Pass ``existing_id`` or ``coordinates``.

??? info "`bundle_network_utils.new_node(input_network, new_id, new_location=[], new_rotation=[], csys=None)`"

    Use this when a harness build needs a node added at a location in the chosen network.
    
    Adds a node at a location.
    
    **Args**
    
    - **input_network** — Network dict. A copy with the new node appended is returned.
    - **new_id** — ``node_id`` for the new node.
    - **new_location** — ``[x, y, z]`` world position. Optional; defaults to an empty location.
    - **new_rotation** — ``[alpha, beta, gamma]`` in degrees. Angles you omit are left unset. Optional.
    - **csys** — CSYS dict stored on the node. Optional; omit it to leave the node without a ``csys``.

??? info "`bundle_network_utils.reroute_segment(input_network, existing_endpoint_node_name, new_endpoint_node_name)`"

    Use this when a harness build needs a segment that ends on one node moved onto a new node.
    
    Moves a segment that ends at an existing node to the coordinates of a new node.
    
    **Args**
    
    - **input_network** — Network dict. A copy is returned; the input is not modified.
    - **existing_endpoint_node_name** — ``node_id`` whose location is a segment endpoint to move. The node must already exist.
    - **new_endpoint_node_name** — ``node_id`` whose location becomes that endpoint. The node must already exist. Every segment end sitting on the old node's location is moved.

