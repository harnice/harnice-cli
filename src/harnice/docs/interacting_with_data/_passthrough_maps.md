# Interacting with Passthrough Maps
Every passthrough channel in the system. Call `new()` to build the map and routing context, optionally `route()` required hops, then `resolve()` to fill channel-map chains.

---
##Columns 
*Columns are automatically generated when `passthrough_map.new()` is called. Additional columns are ok but discouraged due to consistency. If you need more columns, use data structures in build instructions.*

| Column | Description |
|--------|-------------|
| `from_channel_type` | channel-map from type |
| `from-passthrough_channel_type` | passthrough face on the same side as from |
| `to-passthrough_channel_type` | passthrough face on the same side as to |
| `to_channel_type` | channel-map to type |
| `requirement` | user route() step number for this passthrough-channel mapping |
| `satisfaction` | resolve() route() step number (always >= requirement when both set) |
| `is_imaginary` | TRUE if this mapping was minted because no real passthrough channel was available |
| `has_imaginary` | TRUE if this passthrough device has any imaginary channel mappings |
| `manual_map_passthrough_python_equiv` | passthrough_map.route() that would form this requirement |


---
##Commands
*These functions are already available in build instructions as `passthrough_map`. Use them as written.*
??? info "`passthrough_map.read()`"

    Use this when a system build needs every row of the passthrough map in the revision that is open.
    
    Return the passthrough map (cached).

??? info "`passthrough_map.new()`"

    Use this when a system build needs passthrough rows created from the signals lists of the devices on the block diagram.
    
    Create passthrough channel rows from placed-device signals lists.
    
    Rebuilds ``system.passthrough_routing_context`` as one row per unique
    (from_channel_type, to_channel_type) pair within each ``group_of_connected_harnesses``, per
    passthrough device, per directionality (1 / -1, or 0 if reversible), with an
    ``availables`` count of passthrough channels that obey that directionality.
    Does not route channels or fill channel-map chains (see ``resolve()``).

??? info "`passthrough_map.route(to_from_channel_device_refdes, to_from_channel_id, intended_device_refdes, intended_channel_id=None, repeat_channel_id=None, satisfaction=False)`"

    Use this when a system build needs one mapped channel sent through one passthrough device.
    
    Route a mapped channel through a passthrough device.
    
    Looks up the mapped channel's from→to types and group_of_connected_harnesses, finds the matching
    routing-context row(s), picks a free passthrough channel that obeys directionality,
    records the mapping on the **passthrough map**, and decrements
    ``availables`` on the matching context row (never below 0).
    
    ``repeat_channel_id`` is the face the from-side arrives on. Omit it to infer.
    
    The passthrough device must belong to the same
    ``group_of_connected_harnesses`` as the mapped channel.
    
    By default writes ``requirement`` (user route). With ``satisfaction=True``
    (used by ``resolve``), writes ``satisfaction`` instead.
    
    Returns 0 on a real assignment, -1 if an imaginary passthrough-map row was appended
    because ``availables`` was already 0.
    
    **Args:**
    - `to_from_channel_device_refdes`: Device refdes of the mapped channel you are routing.
    - `to_from_channel_id`: Channel id on that device.
    - `intended_device_refdes`: Passthrough device to route through. It must belong to the same group of connected harnesses as the mapped channel.
    - `intended_channel_id`: Specific passthrough channel to use. Optional. Omit it to let ``route`` pick a free channel that matches directionality.
    - `repeat_channel_id`: Face the from-side arrives on. Optional. Omit it to infer the face.
    - `satisfaction`: When True, write a satisfaction row (what ``resolve`` does). When False, write a requirement row. Optional.

??? info "`passthrough_map.resolve()`"

    Use this when a system build needs every mapped channel routed through its passthroughs, in channel-map order.
    
    Complete passthrough routing for each mapped channel (channel-map order).
    
    Uses the routing context (filtered to group_of_connected_harnesses + from→to pair) to find the
    fewest passthrough channels that connect from_harness → optional ordered
    ``requirement`` waypoints → to_harness. Prefers paths with remaining
    ``availables``; if none exist, allows ``availables == 0`` (imaginaries).
    
    Gap fills call ``route(..., satisfaction=True)``. Existing requirement rows
    get a ``satisfaction`` stamp. Writes ``chain_of_connectors`` and
    ``chain_of_harnesses`` on each mapped channel-map row from the resulting path.
    
    Stamps ``is_imaginary`` / ``has_imaginary`` on the passthrough map. Prints one
    warning per passthrough that needed imaginary channels to satisfy the map.
    
    No-op when ``passthrough_map.new()`` found no harness topology (empty parent
    diagram / no harness-mated connectors): there is nothing to resolve.

