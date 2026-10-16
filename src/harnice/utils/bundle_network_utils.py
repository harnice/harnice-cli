import ast
import copy
import math


def _point3(value):
    coords = list(value or (0.0, 0.0, 0.0))
    while len(coords) < 3:
        coords.append(0.0)
    return (float(coords[0]), float(coords[1]), float(coords[2]))


def _as_dict(value):
    if value in ("", None):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _float_or_0(value):
    if value in ("", None):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _zyx_rotation_matrix(alpha, beta, gamma):
    """Return R = Rx(alpha) · Ry(beta) · Rz(gamma) in degrees.

    Matches the console node triad: α about X, β about Y, γ about Z.
    Three.js builds this matrix with ``THREE.Euler(α, β, γ, 'XYZ')``.
    """
    ra, rb, rg = math.radians(alpha), math.radians(beta), math.radians(gamma)
    ca, sa = math.cos(ra), math.sin(ra)
    cb, sb = math.cos(rb), math.sin(rb)
    cg, sg = math.cos(rg), math.sin(rg)
    return [
        [cb * cg, -cb * sg, sb],
        [sa * sb * cg + ca * sg, -sa * sb * sg + ca * cg, -sa * cb],
        [-ca * sb * cg + sa * sg, ca * sb * sg + sa * cg, ca * cb],
    ]


def _identity3():
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _matmul3(a, b):
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)
    ]


def _rotate3(rotation, vector):
    return (
        rotation[0][0] * vector[0]
        + rotation[0][1] * vector[1]
        + rotation[0][2] * vector[2],
        rotation[1][0] * vector[0]
        + rotation[1][1] * vector[1]
        + rotation[1][2] * vector[2],
        rotation[2][0] * vector[0]
        + rotation[2][1] * vector[1]
        + rotation[2][2] * vector[2],
    )


def _euler_zyx_from_matrix(matrix):
    """Extract α, β, γ from R = Rx(α) · Ry(β) · Rz(γ)."""
    r00, r01, r02 = matrix[0][0], matrix[0][1], matrix[0][2]
    beta = math.atan2(r02, math.hypot(r00, r01))
    if abs(math.cos(beta)) < 1e-9:
        alpha = math.atan2(matrix[1][0], matrix[1][1])
        gamma = 0.0
    else:
        alpha = math.atan2(-matrix[1][2], matrix[2][2])
        gamma = math.atan2(-r01, r00)
    return (
        math.degrees(alpha),
        math.degrees(beta),
        math.degrees(gamma),
    )


def _csys_child_offset_3d(child):
    """Cartesian or polar offset, same rules as 2D location, plus z."""
    dx = 0.0
    dy = 0.0
    dz = _float_or_0(child.get("z"))
    if child.get("x") not in ["", None] and child.get("y") not in ["", None]:
        dx = float(child.get("x"))
        dy = float(child.get("y"))
    elif child.get("distance") not in ["", None] and child.get("angle") not in [
        "",
        None,
    ]:
        dist = float(child.get("distance"))
        ang = math.radians(float(child.get("angle")))
        dx = dist * math.cos(ang)
        dy = dist * math.sin(ang)
    return dx, dy, dz


def _csys_child_rotation_3d(child):
    """Child heading as ZYX Euler degrees (α about X, β about Y, γ about Z).

    Prefers ``alpha`` / ``beta`` / ``gamma``, then library ``rx`` / ``ry`` / ``rz``.
    A 2D ``rotation`` is about drawing Z, so it becomes ``gamma``.
    """

    def has(*keys):
        return any(child.get(key) not in ["", None] for key in keys)

    if has("alpha", "beta", "gamma"):
        return (
            _float_or_0(child.get("alpha")),
            _float_or_0(child.get("beta")),
            _float_or_0(child.get("gamma")),
        )
    if has("rx", "ry", "rz"):
        return (
            _float_or_0(child.get("rx")),
            _float_or_0(child.get("ry")),
            _float_or_0(child.get("rz")),
        )
    if child.get("rotation") not in ["", None]:
        return (0.0, 0.0, float(child.get("rotation")))
    return (0.0, 0.0, 0.0)


def _csys_chain(lookup_instance, instances):
    """Walk from ``lookup_instance`` to origin. Returns origin-first chain."""
    for instance in instances:
        raw_children = instance.get("csys_children")
        try:
            if isinstance(raw_children, str) and raw_children:
                csys_children = ast.literal_eval(raw_children)
            else:
                csys_children = raw_children or {}
        except Exception:
            csys_children = {}
        instance["csys_children"] = csys_children

    chain = []
    current = lookup_instance

    while True:
        parent_csys_instance_name = None
        parent_csys_outputcsys_name = None

        for instance in instances:
            if instance.get("instance_name") == current.get("instance_name"):
                parent_csys_instance_name = instance.get("parent_csys_instance_name")
                parent_csys_outputcsys_name = instance.get(
                    "parent_csys_outputcsys_name"
                )
                chain.append(instance)
                break

        if current.get("instance_name") == "origin":
            break

        if parent_csys_instance_name is None:
            raise ValueError(
                f"Instance '{current.get('instance_name')}' missing parent_csys_instance_name"
            )
        if not parent_csys_instance_name:
            raise ValueError(
                f"Instance '{current.get('instance_name')}' parent_csys_instance_name blank"
            )
        if not parent_csys_outputcsys_name:
            raise ValueError(
                f"Instance '{current.get('instance_name')}' parent_csys_outputcsys_name blank"
            )

        parent_csys_instance = None
        for instance in instances:
            if instance.get("instance_name") == parent_csys_instance_name:
                parent_csys_instance = instance
                break
        else:
            raise ValueError(
                f"Instance '{parent_csys_instance_name}' not found in instances list"
            )

        current = parent_csys_instance

    return list(reversed(chain))


def _csys_child_of(chainlink, instances):
    for instance in instances:
        if instance.get("instance_name") == chainlink.get("parent_csys_instance_name"):
            if instance.get("csys_children") != {}:
                return instance["csys_children"].get(
                    chainlink.get("parent_csys_outputcsys_name")
                )
            return {}
    return None


def _transpose3(matrix):
    return [
        [matrix[0][0], matrix[1][0], matrix[2][0]],
        [matrix[0][1], matrix[1][1], matrix[2][1]],
        [matrix[0][2], matrix[1][2], matrix[2][2]],
    ]


def _csys_as_pose(csys):
    child = csys or {}
    return (
        _csys_child_offset_3d(child),
        _zyx_rotation_matrix(*_csys_child_rotation_3d(child)),
    )


def compose_csys(*csys_list):
    """
    Compose child CSYS dicts left to right.

    Each next CSYS is expressed in the previous CSYS's frame. Returns
    ``{x, y, z, alpha, beta, gamma}`` in the first CSYS's parent frame.
    """
    translation = (0.0, 0.0, 0.0)
    rotation = _identity3()
    for csys in csys_list:
        offset, child_r = _csys_as_pose(csys)
        ox, oy, oz = _rotate3(rotation, offset)
        translation = (
            translation[0] + ox,
            translation[1] + oy,
            translation[2] + oz,
        )
        rotation = _matmul3(rotation, child_r)
    alpha, beta, gamma = _euler_zyx_from_matrix(rotation)
    return {
        "x": translation[0],
        "y": translation[1],
        "z": translation[2],
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }


def invert_csys(csys):
    """
    Return the opposite of a child CSYS.

    The result takes the child frame back to its parent origin: if ``csys``
    is a connector mate relative to the part origin, ``invert_csys(csys)``
    is the shift that puts that mate on the origin.
    """
    offset, rotation = _csys_as_pose(csys)
    inverse_r = _transpose3(rotation)
    tx, ty, tz = _rotate3(inverse_r, (-offset[0], -offset[1], -offset[2]))
    alpha, beta, gamma = _euler_zyx_from_matrix(inverse_r)
    return {
        "x": tx,
        "y": ty,
        "z": tz,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }


def calculate_location_3d(lookup_instance, instances):
    """
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
    """
    from harnice.lists.flattened_network import _2d_translate_of

    def translate_of(instance):
        td = _as_dict(instance.get("3d_translate"))
        if td:
            return (
                _float_or_0(td.get("x")),
                _float_or_0(td.get("y")),
                _float_or_0(td.get("z")),
                _float_or_0(td.get("alpha")),
                _float_or_0(td.get("beta")),
                _float_or_0(td.get("gamma")),
            )
        tx, ty, rotate = _2d_translate_of(instance)
        return (
            0.0 if tx is None else tx,
            0.0 if ty is None else ty,
            0.0,
            0.0,
            0.0,
            0.0 if rotate is None else rotate,
        )

    chain = _csys_chain(lookup_instance, instances)

    x_pos = 0.0
    y_pos = 0.0
    z_pos = 0.0
    rotation = _identity3()

    for chainlink in chain:
        relevant_csys_child = _csys_child_of(chainlink, instances)

        rotation_old = rotation
        dx = 0.0
        dy = 0.0
        dz = 0.0

        if relevant_csys_child is not None:
            dx, dy, dz = _csys_child_offset_3d(relevant_csys_child)
            child_alpha, child_beta, child_gamma = _csys_child_rotation_3d(
                relevant_csys_child
            )
            rotation = _matmul3(
                rotation, _zyx_rotation_matrix(child_alpha, child_beta, child_gamma)
            )

        ox, oy, oz = _rotate3(rotation_old, (dx, dy, dz))
        x_pos += ox
        y_pos += oy
        z_pos += oz

        tx, ty, tz, alpha, beta, gamma = translate_of(chainlink)
        ox, oy, oz = _rotate3(rotation, (tx, ty, tz))
        x_pos += ox
        y_pos += oy
        z_pos += oz
        rotation = _matmul3(rotation, _zyx_rotation_matrix(alpha, beta, gamma))

    return (x_pos, y_pos, z_pos) + _euler_zyx_from_matrix(rotation)


def _identity_csys():
    return {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "alpha": 0.0,
        "beta": 0.0,
        "gamma": 0.0,
    }


def _csys_children_of(instance):
    from harnice.lists import instances_list

    if not isinstance(instance, dict):
        return {}
    raw = instance.get("csys_children")
    if not raw:
        raw = instances_list.attribute_of(
            instance.get("instance_name"), "csys_children"
        )
    return _as_dict(raw)


def _lookup_csys_child(instance, csys_name):
    if csys_name in ["", None, "origin"]:
        return _identity_csys()
    children = _csys_children_of(instance)
    if csys_name in children:
        return children[csys_name]
    if csys_name == "connector" and "3d-connector" in children:
        return children["3d-connector"]
    aliased = f"3d-{csys_name}"
    if aliased in children:
        return children[aliased]
    return None


def _instance_named(instances, name):
    for instance in instances:
        if instance.get("instance_name") == name:
            return instance
    return None


def _scope_instances(instance):
    from harnice.lists import instances_list

    instances = instances_list.read()
    if isinstance(instance, dict):
        return instances, instance.get("connector_group")
    for row in instances:
        if row.get("instance_name") == instance:
            return instances, row.get("connector_group")
    return instances, instance


def _owner_of_csys(instances, connector_group, csys_name):
    if csys_name in ["", None, "origin"]:
        for instance in instances:
            if instance.get("connector_group") == connector_group and instance.get(
                "item_type"
            ) == "node":
                return instance
        return None
    for instance in instances:
        if connector_group not in ["", None]:
            if instance.get("connector_group") != connector_group:
                continue
        children = _csys_children_of(instance)
        if csys_name in children:
            return instance
        if csys_name == "connector" and "3d-connector" in children:
            return instance
        if f"3d-{csys_name}" in children:
            return instance
    return None


def _instance_translate_csys(instance):
    """Instance ``3d_translate`` only. Blank stays identity (do not use 2D)."""
    td = _as_dict((instance or {}).get("3d_translate"))
    if not td:
        return _identity_csys()
    return {
        "x": _float_or_0(td.get("x")),
        "y": _float_or_0(td.get("y")),
        "z": _float_or_0(td.get("z")),
        "alpha": _float_or_0(td.get("alpha")),
        "beta": _float_or_0(td.get("beta")),
        "gamma": _float_or_0(td.get("gamma")),
    }


def _pose_from_node_origin_to(instances, owner, csys_name):
    """Compose parent output CSYSes and each instance ``3d_translate``.

    Same order as ``calculate_location_3d``, expressed in
    the node frame (the node's own translate is the frame, so it is omitted).
    """
    if owner is None:
        return _identity_csys()
    if owner.get("item_type") == "node" or owner.get("instance_name") == "origin":
        if csys_name in ["", None, "origin"]:
            return _identity_csys()
        target = _lookup_csys_child(owner, csys_name)
        if target is None:
            raise ValueError(
                f"Instance '{owner.get('instance_name')}' has no CSYS '{csys_name}'"
            )
        return compose_csys(target)

    links = []
    current = owner
    seen = set()
    while current is not None:
        name = current.get("instance_name")
        if name in seen:
            break
        seen.add(name)
        if current.get("item_type") == "node" or name == "origin":
            break
        parent = _instance_named(
            instances, current.get("parent_csys_instance_name")
        )
        output_name = current.get("parent_csys_outputcsys_name") or "origin"
        parent_csys = None
        if parent is not None and output_name not in ["", None, "origin"]:
            parent_csys = _lookup_csys_child(parent, output_name)
            if parent_csys is None:
                raise ValueError(
                    f"Instance '{parent.get('instance_name')}' has no "
                    f"output CSYS '{output_name}'"
                )
        links.append((parent_csys, current))
        current = parent
    links.reverse()

    steps = []
    for parent_csys, instance in links:
        if parent_csys is not None:
            steps.append(parent_csys)
        steps.append(_instance_translate_csys(instance))
    if csys_name not in ["", None, "origin"]:
        target = _lookup_csys_child(owner, csys_name)
        if target is None:
            raise ValueError(
                f"Instance '{owner.get('instance_name')}' has no CSYS '{csys_name}'"
            )
        steps.append(target)
    return compose_csys(*steps) if steps else _identity_csys()


def difference_between_csys(instance, from_csys, to_csys):
    """
    Direction that takes ``to_csys`` onto ``from_csys``.

    Pass the result to ``move_node`` as the move direction. Typical use:
    keep a connector mating face on the original available-network point
    with ``from_csys="origin"`` and ``to_csys="3d-mate"``.

    ## Args

    - **instance** — Instance dict, ``instance_name``, or ``connector_group``.
      Named children may live on different items in the same group; the
      parent CSYS stack is composed (backshell ``3d-connector``, each
      instance ``3d_translate``, then connector ``3d-mate``).
    - **from_csys** — Child name or ``"origin"``. This is where ``to_csys``
      should land.
    - **to_csys** — Child name or ``"origin"``. The CSYS that moves.

    ## Returns

    A CSYS dict ``{x, y, z, alpha, beta, gamma}`` in the node frame.
    """
    instances, connector_group = _scope_instances(instance)
    from_owner = _owner_of_csys(instances, connector_group, from_csys)
    to_owner = _owner_of_csys(instances, connector_group, to_csys)
    if to_csys not in ["", None, "origin"] and to_owner is None:
        raise ValueError(
            f"No instance in connector group '{connector_group}' has CSYS "
            f"'{to_csys}'"
        )
    if from_csys not in ["", None, "origin"] and from_owner is None:
        raise ValueError(
            f"No instance in connector group '{connector_group}' has CSYS "
            f"'{from_csys}'"
        )
    from_pose = _pose_from_node_origin_to(instances, from_owner, from_csys)
    to_pose = _pose_from_node_origin_to(instances, to_owner, to_csys)
    return compose_csys(invert_csys(to_pose), from_pose)


def _near(a, b, proximity_threshold=1e-6):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))) <= proximity_threshold


def _node_angles(node):
    return (
        0.0 if node.get("alpha") is None else float(node.get("alpha")),
        0.0 if node.get("beta") is None else float(node.get("beta")),
        0.0 if node.get("gamma") is None else float(node.get("gamma")),
    )


def _rotation_of(node):
    return _zyx_rotation_matrix(*_node_angles(node))


def _world_pose_from_output_csys(node, output_csys):
    """World location and Euler of a CSYS given in the node's local frame."""
    child = output_csys or {}
    dx, dy, dz = _csys_child_offset_3d(child)
    ca, cb, cg = _csys_child_rotation_3d(child)
    node_r = _rotation_of(node)
    ox, oy, oz = _rotate3(node_r, (dx, dy, dz))
    loc = [
        float(node["location"][0]) + ox,
        float(node["location"][1]) + oy,
        float(node["location"][2]) + oz,
    ]
    rot = _euler_zyx_from_matrix(
        _matmul3(node_r, _zyx_rotation_matrix(ca, cb, cg))
    )
    return loc, rot


def move_node(
    input_network,
    node_id,
    direction=None,
    new_location=None,
    new_rotation=None,
    output_csys=None,
):
    """
    Moves one node in a network.

    ## Args

    - **input_network** — Network dict with ``"segments"`` and ``"nodes"``.
    - **node_id** — Which node in the network to move.
    - **direction** — Which way to move it: a CSYS dict in the node's
      current frame, usually from ``difference_between_csys``. Segment
      endpoints that sit on the old location follow the node.

    ``new_location`` / ``new_rotation`` set an absolute world pose instead.
    ``output_csys`` is an alias for ``direction``.

    ## Returns

    A deep copy of ``input_network`` with the node and its incident
    segment geometry updated.

    ## Errors

    - **ValueError** if the node is missing, or if no direction or
      ``new_location`` is given.
    """
    if output_csys is None:
        output_csys = direction
    if output_csys is None and not new_location:
        raise ValueError("move_node requires direction or new_location")

    network = copy.deepcopy(input_network)
    nodes = network.get("nodes", [])
    segments = network.get("segments", [])
    node = next((n for n in nodes if n["node_id"] == node_id), None)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found.")

    old_loc = _point3(node.get("location"))
    if output_csys is not None:
        dest_loc, dest_rot = _world_pose_from_output_csys(node, output_csys)
    else:
        dest_loc = list(_point3(new_location))
        dest_rot = list(_node_angles(node))
        if new_rotation:
            for i, value in enumerate(new_rotation):
                if i < 3 and value not in ("", None):
                    dest_rot[i] = float(value)

    node["location"] = dest_loc
    node["alpha"], node["beta"], node["gamma"] = dest_rot

    def _follow(point):
        if _near(_point3(point), old_loc):
            return list(dest_loc)
        return list(point)

    for seg in segments:
        seg["location_at_end_a"] = _follow(seg.get("location_at_end_a"))
        seg["location_at_end_b"] = _follow(seg.get("location_at_end_b"))
        controls = seg.get("spline_control_points") or []
        if controls:
            seg["spline_control_points"] = [_follow(point) for point in controls]

    return network


def adjacent_nodes(input_network, from_node):
    """
    Traverses the network from a given node and returns a list of dicts representing nodes that are one segment of connection away.

    The dict should contain node_id, delta_x, delta_y, and delta_z.

    Deltas are calculated by finding the relative position of each node with respect to the from_node coordinate system.
    """
    network = input_network
    from_loc = from_node["location"]
    from_loc_tuple = tuple(from_loc)

    # Build rotation matrix from from_node angles (console ZYX: α about X, γ about Z).
    # If any angle is None, fall back to the identity (global coordinates).
    alpha = from_node.get("alpha")
    beta = from_node.get("beta")
    gamma = from_node.get("gamma")

    def _rotation_matrix(a, b, g):
        """Return R = Rx(a) · Ry(b) · Rz(g) in degrees (α about X, γ about Z)."""
        ra, rb, rg = math.radians(a), math.radians(b), math.radians(g)
        ca, sa = math.cos(ra), math.sin(ra)
        cb, sb = math.cos(rb), math.sin(rb)
        cg, sg = math.cos(rg), math.sin(rg)
        return [
            [cb * cg, -cb * sg, sb],
            [sa * sb * cg + ca * sg, -sa * sb * sg + ca * cg, -sa * cb],
            [-ca * sb * cg + sa * sg, ca * sb * sg + sa * cg, ca * cb],
        ]

    def _transform(dx, dy, dz):
        if None in (alpha, beta, gamma):
            return dx, dy, dz
        R = _rotation_matrix(alpha, beta, gamma)
        # Rotate the global delta into the from_node local frame (transpose of R).
        tdx = R[0][0] * dx + R[1][0] * dy + R[2][0] * dz
        tdy = R[0][1] * dx + R[1][1] * dy + R[2][1] * dz
        tdz = R[0][2] * dx + R[1][2] * dy + R[2][2] * dz
        return tdx, tdy, tdz

    segments = network.get("segments", [])
    nodes = network.get("nodes", [])
    loc_to_node = {tuple(n["location"]): n for n in nodes}

    found_nodes = []
    for seg in segments:
        ea = tuple(seg["location_at_end_a"])
        eb = tuple(seg["location_at_end_b"])
        if ea == from_loc_tuple:
            neighbor_loc = eb
        elif eb == from_loc_tuple:
            neighbor_loc = ea
        else:
            continue
        neighbor = loc_to_node.get(neighbor_loc)
        if neighbor:
            dx = neighbor["location"][0] - from_loc[0]
            dy = neighbor["location"][1] - from_loc[1]
            dz = neighbor["location"][2] - from_loc[2]
            tdx, tdy, tdz = _transform(dx, dy, dz)
            found_nodes.append(
                {
                    "node_id": neighbor["node_id"],
                    "delta_x": tdx,
                    "delta_y": tdy,
                    "delta_z": tdz,
                }
            )
    return found_nodes  # list of dicts


def _network_node(input_network, node_id):
    for node in (input_network or {}).get("nodes") or []:
        if node.get("node_id") == node_id:
            return node
    return None


_UNIT = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}
_SPIN_KEY = {"x": "alpha", "y": "beta", "z": "gamma"}


def _norm_angle_deg(angle):
    return ((float(angle) % 360.0) + 360.0) % 360.0


def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _axis_unit(name, label):
    key = str(name or "").strip().lower()
    if key not in _UNIT:
        raise ValueError(f"{label} must be 'x', 'y', or 'z', got {name!r}")
    return key, _UNIT[key]


def path_angle(
    input_network,
    node_id,
    toward="incident",
    axis="x",
    zero="y",
    if_along_axis=None,
):
    """
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
    """
    node = _network_node(input_network, node_id)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found.")
    neighbors = adjacent_nodes(input_network, node)
    if toward in ("", None, "incident"):
        if len(neighbors) != 1:
            names = ", ".join(n["node_id"] for n in neighbors) or "(none)"
            raise ValueError(
                f"Node '{node_id}' has {len(neighbors)} incident hop(s) "
                f"({names}); pass toward= as a node id to pick one."
            )
        hop = neighbors[0]
    else:
        hop = next((n for n in neighbors if n.get("node_id") == toward), None)
        if hop is None:
            raise ValueError(
                f"Node '{node_id}' is not connected to '{toward}'."
            )
    axis_name, e_axis = _axis_unit(axis, "axis")
    zero_name, e_zero = _axis_unit(zero, "zero")
    if axis_name == zero_name:
        raise ValueError("axis and zero must be different")
    hop_vec = (hop["delta_x"], hop["delta_y"], hop["delta_z"])
    along = _dot3(hop_vec, e_axis)
    radial = math.sqrt(max(_dot3(hop_vec, hop_vec) - along * along, 0.0))
    if radial < 1e-6:
        if if_along_axis is not None:
            return _norm_angle_deg(if_along_axis)
        raise ValueError(
            f"Hop from '{node_id}' to '{hop['node_id']}' is along the node "
            f"{axis_name.upper()} axis, so an angle about that axis is "
            "undefined. Pass if_along_axis=0 for a straight exit."
        )
    sine_axis = _cross3(e_axis, e_zero)
    return _norm_angle_deg(
        math.degrees(math.atan2(_dot3(hop_vec, sine_axis), _dot3(hop_vec, e_zero)))
    )


def rotate_csys(csys, angle, about="x"):
    """
    Rotate a child CSYS about a parent axis.

    ``R = R_about(angle) · csys`` in the parent frame.

    **Args:**
    - `csys` (dict): ``{x, y, z, alpha, beta, gamma}`` or a library child.
    - `angle` (float): Degrees.
    - `about` (str): ``"x"``, ``"y"``, or ``"z"``.

    **Returns:**
    - `dict`: The rotated CSYS.
    """
    about_name, _unit = _axis_unit(about, "about")
    spin = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "alpha": 0.0,
        "beta": 0.0,
        "gamma": 0.0,
    }
    spin[_SPIN_KEY[about_name]] = float(angle)
    return compose_csys(spin, csys)


def output_csys(instance, csys_name):
    """
    Named output CSYS on one instance (no parent-chain walk).

    **Args:**
    - `instance`: Instance dict, instance name, or connector group.
    - `csys_name` (str): Child name (``"3d-mate"``, ``"connector"``, …).

    **Returns:**
    - `dict`: ``{x, y, z, alpha, beta, gamma}``.

    **Raises:**
    - `ValueError`: If the instance or CSYS is missing.
    """
    instances, connector_group = _scope_instances(instance)
    owner = None
    if isinstance(instance, dict):
        owner = instance
    elif isinstance(instance, str):
        owner = _instance_named(instances, instance)
    if owner is None:
        owner = _owner_of_csys(instances, connector_group, csys_name)
    if owner is None:
        raise ValueError(
            f"No instance in connector group '{connector_group}' has CSYS "
            f"'{csys_name}'"
        )
    child = _lookup_csys_child(owner, csys_name)
    if child is None:
        raise ValueError(
            f"Instance '{owner.get('instance_name')}' has no CSYS '{csys_name}'"
        )
    return compose_csys(child)


def output_offset(instance, csys_name, about=None, angle=0):
    """
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
    """
    offset = invert_csys(output_csys(instance, csys_name))
    if about not in ("", None) and angle not in ("", None, 0, 0.0):
        offset = rotate_csys(offset, angle, about=about)
    return offset


def spin(instance_name, angle, about="x"):
    """
    Write one Euler component of ``3d_translate`` on an instance.

    Use the opposite of a ``path_angle`` when a child should not inherit a
    parent spin (un-clock a connector after a clocked backshell move).

    **Args:**
    - `instance_name` (str): Instance to rotate in its parent CSYS.
    - `angle` (float): Degrees about ``about``.
    - `about` (str): ``"x"`` → ``alpha``, ``"y"`` → ``beta``, ``"z"`` → ``gamma``.

    **Returns:**
    - `float`: The angle written, normalized to ``[0, 360)``.

    **Raises:**
    - `ValueError`: If the name is blank, the instance is missing, or the
        angle is not a finite number.
    """
    from harnice.lists import instances_list

    if instance_name in ("", None):
        raise ValueError("instance_name is required but blank")
    about_name, _unit = _axis_unit(about, "about")
    try:
        theta = float(angle)
    except (TypeError, ValueError):
        raise ValueError(f"spin angle must be a number, got {angle!r}")
    if not math.isfinite(theta):
        raise ValueError("spin angle must be finite")
    theta = _norm_angle_deg(theta)

    row = _instance_named(instances_list.read(), instance_name)
    if row is None:
        raise ValueError(f"Instance '{instance_name}' not found")
    translate = dict(_as_dict(row.get("3d_translate")))
    translate[_SPIN_KEY[about_name]] = theta
    for key in ("x", "y", "z", "alpha", "beta", "gamma"):
        if translate.get(key) in ("", None):
            translate[key] = 0.0
    instances_list.modify(instance_name, {"3d_translate": translate})
    return theta


def clock_backshell(
    network,
    connector_group,
    towards_node="incident",
    round_to_nearest_angle=None,
):
    """
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
    """
    from harnice.lists import instances_list
    from harnice.utils import note_utils

    if connector_group in ("", None):
        raise ValueError("connector_group is required but blank")

    connector = instances_list.instance_in_connector_group_with_item_type(
        connector_group, "harness_connector"
    )
    backshell = instances_list.instance_in_connector_group_with_item_type(
        connector_group, "backshell"
    )
    node = instances_list.instance_in_connector_group_with_item_type(
        connector_group, "node"
    )
    if not connector:
        raise ValueError(
            f"No harness_connector in connector group '{connector_group}'"
        )
    if not backshell:
        raise ValueError(f"No backshell in connector group '{connector_group}'")
    node_id = (
        node.get("instance_name")
        if node
        else f"{connector_group}.node"
    )
    toward = towards_node if towards_node not in ("", None) else "incident"
    theta = path_angle(
        network, node_id, toward=toward, axis="x", zero="y", if_along_axis=0
    )
    if round_to_nearest_angle not in ("", None, 0, 0.0):
        snap = float(round_to_nearest_angle)
        if snap <= 0:
            raise ValueError("round_to_nearest_angle must be positive")
        theta = _norm_angle_deg(round(theta / snap) * snap)
    network = move_node(
        network, node_id, output_offset(connector, "3d-mate")
    )
    network = move_node(
        network,
        node_id,
        output_offset(backshell, "connector", about="x", angle=theta),
    )
    spin(connector.get("instance_name"), -theta, about="x")
    # Face clock: 0 = connector +Y (up), not +X (mate axis).
    clockwise = _norm_angle_deg(90.0 - theta)
    degrees = (
        str(int(round(clockwise)))
        if abs(clockwise - round(clockwise)) < 1e-6
        else f"{clockwise:.1f}"
    )
    note_utils.new_note(
        "build_note",
        (
            f"Clock backshell to {degrees} degrees clockwise of the "
            "connector's up direction from the mating face"
        ),
        affectedinstances=[connector.get("instance_name")],
    )
    return network


def rename_node(input_network, new_id, existing_id=None, coordinates=[]):
    """
    Finds a node and changes its id.

    If existing ID is used, that's self-explanatory.

    If coordinates are given in form {x, y, z, radius} and not 1 node is in the sphere, raise an error.
    """
    network = copy.deepcopy(input_network)
    nodes = network.get("nodes", [])

    if existing_id is not None:
        matches = [n for n in nodes if n["node_id"] == existing_id]
        if not matches:
            raise ValueError(f"No node with id '{existing_id}' found.")
        target = matches[0]
    elif coordinates:
        x, y, z, radius = coordinates
        center = [x, y, z]
        in_sphere = [
            n
            for n in nodes
            if math.sqrt(sum((a - b) ** 2 for a, b in zip(n["location"], center)))
            <= radius
        ]
        if len(in_sphere) != 1:
            raise ValueError(
                f"Expected exactly 1 node within radius {radius} of {center}, "
                f"found {len(in_sphere)}."
            )
        target = in_sphere[0]
    else:
        raise ValueError("Either existing_id or coordinates must be provided.")

    target["node_id"] = new_id
    return network


def new_node(input_network, new_id, new_location=[], new_rotation=[], csys=None):
    """
    Adds a node at a location
    """
    network = copy.deepcopy(input_network)
    node = {
        "node_id": new_id,
        "location": list(new_location),
        "alpha": new_rotation[0] if len(new_rotation) > 0 else None,
        "beta": new_rotation[1] if len(new_rotation) > 1 else None,
        "gamma": new_rotation[2] if len(new_rotation) > 2 else None,
    }
    if csys is not None:
        node["csys"] = csys

    network.setdefault("nodes", []).append(node)
    return network


def reroute_segment(input_network, existing_endpoint_node_name, new_endpoint_node_name):
    """
    Moves a segment that ends at an existing node to the coordinates of a new node
    """
    network = copy.deepcopy(input_network)
    nodes = network.get("nodes", [])
    segments = network.get("segments", [])

    existing_node = next(
        (n for n in nodes if n["node_id"] == existing_endpoint_node_name), None
    )
    new_endpoint_node = next(
        (n for n in nodes if n["node_id"] == new_endpoint_node_name), None
    )

    if existing_node is None:
        raise ValueError(f"Node '{existing_endpoint_node_name}' not found.")
    if new_endpoint_node is None:
        raise ValueError(f"Node '{new_endpoint_node_name}' not found.")

    existing_loc = tuple(existing_node["location"])
    new_loc = list(new_endpoint_node["location"])

    for seg in segments:
        if tuple(seg["location_at_end_a"]) == existing_loc:
            seg["location_at_end_a"] = new_loc
        elif tuple(seg["location_at_end_b"]) == existing_loc:
            seg["location_at_end_b"] = new_loc

    return network
