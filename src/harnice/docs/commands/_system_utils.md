# System Utilities
---
##Commands
*These functions are already available in build instructions as `system_utils`. Use them as written.*
??? info "`system_utils.create_instances_from_circuits_list()`"

    Use this when a system build needs connector, cavity, channel, and circuit instances created from the circuits list.
    
    Creates connector, cavity, channel, and circuit instances from the circuits list.
    
    Intended to be called from system build instructions (after ``circuits_list.new()``).
    BOM devices/harnesses are imported earlier in ``system.build()`` via
    ``_import_bom_devices``.
    
    For each circuit, it creates:
    
    - Connector instances (at both ends, with MPN lookup from system connector list)
    - Connector cavity instances (at both ends)
    - Circuit instance. ``print_name`` is
      ``{signal}_of_{from_device}.{from_ch}<->{to_device}.{to_ch}``;
      ``print_name_at_end_a`` / ``print_name_at_end_b`` are the from/to cavities.
    - Channel instances. ``print_name`` is
      ``{from_device}.{from_ch} <-> {to_device}.{to_ch}``;
      ``print_name_at_end_a`` / ``print_name_at_end_b`` are the mapped device
      channel IDs.
    - Harness-channel instances use the same ``print_name``, but end labels are
      the hop-local channel IDs (``harness_from_channel_id`` /
      ``harness_to_channel_id``) so a passthrough hop shows that passthrough
      channel, not the far-end device channel.
    - Harness-channel instance names are ``{harness}-{harness_chain_index}:channel-…``
    
    Connector nodes (and parenting connectors to them) are created later when
    the harness is imported via ``import_harness_from_harnice_system``.
    
    After processing all circuits, the function updates device connector instances with
    device-side and harness-side connector information from the system connector list.

??? info "`system_utils.import_harness_from_harnice_system(system_pn, system_rev, system_lib_repo, system_lib_subpath, target_harness)`"

    Use this when a harness that comes from a system needs that system's instances for one harness refdes.
    
    Import harness instances from a system revision's instances list for one harness.
    
    Resolves the system revision folder from ``fileio.path("repository locations")`` as
    ``{local_path}/{system_lib_subpath}/{system_pn}/rev{system_rev}``,
    then reads ``fileio.path("instances list")`` from that folder,
    sets ``state.harness`` to ``target_harness``, and copies every instance whose
    ``harness`` column matches into the current harness instances list. Circuit
    instances are imported as conductors (same fields,
    ``item_type`` set to ``conductor``). ``print_name``, ``print_name_at_end_a``,
    ``print_name_at_end_b``, and ``appearance`` are copied exactly from the circuit,
    as are cable recommendations (``mpn``, ``lib_repo``, ``lib_subpath``,
    ``cable_group``, ``cable_identifier``). Device connector instances are imported
    as harness connectors (same fields, ``item_type`` set to ``harness_connector``,
    keyed by ``harness_side_connector_id``), parented to a matching ``node`` instance
    (``{harness_side_connector_id}.node``) created for each. Device connector
    cavities are renamed from
    ``{device}.{device_connector}.{cavity}`` to
    ``{harness_side_connector_id}.{cavity}``. Print names are set at creation:
    harness connectors use the connector group, cavities use ``cavity {id}``,
    and nodes use the instance name. Then seeds a node for each connector group
    via ``instances_list.seed_connector_nodes()``.
    
    **Args:**
    - `system_pn` (str): Part number of the system whose harness you are importing.
    - `system_rev` (str): System revision label as used in folder/file names (e.g. ``"rev1"``).
    - `system_lib_repo` (str): Library repository URL as listed in ``repository_locations.csv``.
    - `system_lib_subpath` (str): Path from that library root to the system PN folder.
      Empty string if the PN folder sits directly under the library root.
    - `target_harness` (str): Harness reference designator to import.
    
    **Raises:**
    - `FileNotFoundError`: If the system instances list file does not exist.
    - `ValueError`: If required arguments are missing, if ``system_lib_repo`` is
      not in ``repository_locations.csv``, if no connectors/circuits exist for
      ``target_harness``, or if a mating connector on that harness is unnamed.

??? info "`system_utils.connector_of_channel(key)`"

    Use this when a system build needs the connector id for one channel endpoint.
    
    Connector id for a channel endpoint.
    
    **Args:**
    - `key` (tuple): `(device_refdes, channel_id)` or
      `(device_refdes, channel_id, repeat_channel_id)` when that channel has
      two endpoints.
    
    **Returns:**
    - `str`: The ``connector_id`` for that endpoint.
    
    **Raises:**
    - `ValueError`: If the connector is not found for the given channel.

??? info "`system_utils.find_connector_with_no_circuit(connector_list, circuits_list)`"

    Use this when a system build should stop if a connector has no circuit.
    
    Validates that all connectors have associated circuits.
    
    Checks each connector in the connector list to ensure it has at least one
    corresponding circuit in the circuits list. Skips connectors whose
    ``mating_harness_refdes`` is ``<unmated>`` or contains ``"unconnected"``. Raises an
    error if any connector lacks a circuit.
    
    **Args:**
    - `connector_list` (list): List of connector dictionaries from the system connector list
        (columns include ``device_refdes``, ``device_connector``, ``mating_harness_refdes``, …).
    - `circuits_list` (list): List of circuit dictionaries from the circuits list.
    
    **Raises:**
    - `ValueError`: If a connector is found that has no associated circuits. The error
        message suggests checking the channel map and channel compatibility.

??? info "`system_utils.mpn_of_device_refdes(refdes)`"

    Use this when a system build needs the manufacturer part number of a device reference designator.
    
    Looks up manufacturer part number information for a device reference designator.
    
    Searches the BOM (Bill of Materials) for a device with the given reference designator
    and returns its manufacturer, part number, and revision.
    
    **Args:**
    - `refdes` (str): Device reference designator to look up (e.g., `"J1"`, `"X1"`).
    
    **Returns:**
    - `tuple`: A tuple of `(MFG, MPN, rev)` if found, or `(None, None, None)` if not found.

??? info "`system_utils.make_connector_list()`"

    Use this when a system build needs the system connector list rebuilt from the block diagram. system.build() writes it before the script.
    
    Build the system connector list TSV from the block diagram SVG.
    
    Reads ``fileio.path("block diagram")``, writes ``fileio.path("system connector list")``,
    and updates ``system.connector_list``.
    Each row is one harness connector circle under a placed **device**
    symbol—every connector on every placed instance, whether or not a harness wire mates to
    it. When a harness wire endpoint is within mate tolerance of the connector,
    ``mating_harness_refdes`` is taken from that harness cluster's refdes marker (blank if the
    cluster has no marker). When no harness wire mates to the connector,
    ``mating_harness_refdes`` is ``<unmated>``. Multiple wire segments meeting the same
    connector still produce a single row. ``device_connector_mpn`` is resolved from each
    instance's signals list by ``connector_id``. The
    ``external_interface_flag`` column is ``TRUE`` when the block diagram has an
    ``external-interface-flag`` polygon whose ``data-mating-pos`` matches that connector's
    rounded world position (same key as the editor's yellow mating connector). The
    ``mating_harness_asserted_connector_name`` column is the ``data-name`` on the yellow
    ``mating connector`` circle at that same rounded world position (empty when unnamed).
    
    **Columns:** ``device_refdes``, ``device_connector``,
    ``mating_harness_asserted_connector_name``, ``mating_harness_refdes``,
    ``group_of_connected_harnesses``, ``device_connector_mpn``,
    ``external_interface_flag``.
    
    ``group_of_connected_harnesses`` is the equivalence class of ``mating_harness_refdes``
    values linked through passthroughs: harnesses mated to the two faces of the same
    passthrough channel are unioned. Labels are sorted harness names joined by ``+``
    (e.g. ``H1+H2``). ``<unmated>`` is not grouped; those rows keep an empty
    ``group_of_connected_harnesses``.

