# Interacting with Channel Maps
A list of channels on devices within groups of connected harnesses. Each completed pairing is a mapped channel; remaining rows are unmapped.

---
##Columns 
*Columns are automatically generated when `channel_map.new()` is called. Additional columns are not supported and may result in an error when parsing.*

| Column | Description |
|--------|-------------|
| `group_of_connected_harnesses` | harnesses linked through passthroughs (or a single standalone harness) |
| `from_device_refdes` | device instance refdes of this channel endpoint (seeded by new()) |
| `from_device_channel_id` | channel id on that device (from its signals list) |
| `from_repeat_channel_id` | required when that channel has two endpoints; blank otherwise |
| `from_channel_type` | channel type of the from endpoint (from the signals list) |
| `to_device_refdes` | device instance refdes of the mapped partner; blank until mapped |
| `to_device_channel_id` | channel id of the mapped partner; blank until mapped |
| `to_repeat_channel_id` | required when that channel has two endpoints; blank otherwise |
| `to_channel_type` | channel type of the mapped partner; blank until mapped |
| `multi_ch_junction_id` | set by map(..., multi_ch_junction_key=...); shared id for a multi-channel junction net |
| `chain_of_connectors` | filled by passthrough_map.resolve(); semicolon-separated refdes.connector path (e.g. MIC3.J1;X1.A;X1.B;PREAMP1.J1) |
| `chain_of_harnesses` | filled by passthrough_map.resolve(); semicolon-separated harness refdes hops (e.g. H1;H2) |
| `manual_map_channel_python_equiv` | channel_map.map(...) call that produced this pairing; copy back into build instructions |


---
##Commands:
*These functions are already available in build instructions as `channel_map`. Use them as written.*
??? info "`channel_map.new()`"

    Makes a new blank channel map. Overwrites existing channel map.
    
    Seeds one row per channel endpoint, including both faces of a passthrough.
    Auto-map skips those multi-endpoint rows; ``map()`` uses a 3-tuple to name
    a face.
    
    Args: none
    
    Returns: none

??? info "`channel_map.map(from_key, to_key=None, multi_ch_junction_key='')`"

    Map one channel endpoint to another (a patch), or consume it onto a
    multi-channel junction.
    
    Each key is ``(device_refdes, channel_id)`` when that channel has one
    endpoint, or ``(device_refdes, channel_id, repeat_channel_id)`` when it
    has two. A 3-tuple on a single-instance channel is an error; omitting the
    repeat on a two-instance channel is an error.
    
    Dual-map is two calls to the two repeats of the same passthrough. That
    consumes both faces as patch ends and does not write a passthrough-map row.
    
    Both endpoints must belong to the same ``group_of_connected_harnesses``.
    Unmated terminating connectors are in no group. An unmated passthrough
    face still belongs to the group of its other, mated face.
    
    A patch may end by crossing a device only if the destination face has no
    harness. If that face has a harness, the last hop must be that harness.
    
    Pass ``multi_ch_junction_key="jcn1"`` instead of ``to_key`` to consume
    ``from_key`` and write ``jcn1`` as ``multi_ch_junction_id``. Several rows
    can share that id (connecting those channels to each other) without
    pairing to a single partner. A channel may join only if its type is, or
    is compatible with, every other member already on that junction.

??? info "`channel_map.compile_hierarchical()`"

    Write the hierarchical channel map for this system and every child subsystem.
    
    Reads this system's channel map, then the channel map imported with each
    child subsystem, recursively. An imported subsystem channel map is the
    source of truth: this does not rebuild those rows.
    
    Rows from a subsystem prefix that subsystem's instance name onto
    ``group_of_connected_harnesses``, ``from_device_refdes``,
    ``to_device_refdes``, ``multi_ch_junction_id``, ``chain_of_connectors``,
    and ``chain_of_harnesses``. A list is prefixed per entry (``AMP.H1+AMP.H2``,
    ``AMP.H1;AMP.H2``, ``AMP.MIC3.J1;AMP.X1.A``). Nested subsystems accumulate
    prefixes (``AMP.PRE.MIC1``). ``manual_map_channel_python_equiv`` is left
    blank. Channel ids, repeat ids, and channel types are copied unchanged.
    This system's own rows are not prefixed. Headers match the channel map.
    
    Call after channel mapping, including
    ``map_unmapped_compatibles_alphabetically()``. The sheet snapshots the
    channel map as it stands at the call.
    
    Args: none
    
    Returns: the written rows

??? info "`channel_map.already_mapped_set_append(key)`"

    Documentation needed.

??? info "`channel_map.already_mapped_set()`"

    Documentation needed.

??? info "`channel_map.already_mapped(key)`"

    Documentation needed.

