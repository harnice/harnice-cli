## Interacting with Instances Lists
An instances list is a list of every physical or notional item, idea, note, part, instruction, circuit, drawing element, thing, concept literally anything that describes how to build that harness or system.

Instances lists are the single comprehensive source of truth for the project you are working on. Other inputs—especially **build instructions** (your Python script)—build this list, and all output documentation are derived from it.

---
##Columns 
*Columns are automatically generated when `instances_list.new()` is called. Additional columns for this kind of list may be added by the user.*

| Column | Description |
|--------|-------------|
| `harness` | the physical harness (harness refdes) that this instance is part of |
| `instance_name` | the unique name of this instance |
| `print_name` | the non-unique, human-readable name of this instance, used for printing on output documents |
| `bom_line_number` | if this instance represents a physical procurable good, it gets assigned a line number on a bill of materials |
| `mfg` | manufacturer of this instance |
| `mpn` | manufacturer part number |
| `item_type` | connector, backshell, whatever |
| `location_type` | each instance is either better represented by one or ther other |
| `segment_group` | the group of segments that this instance is part of |
| `segment_order` | the sequential id of this item in its segment group |
| `connector_group` | a group of co-located parts (connectors, backshells, nodes) |
| `channel_group` | other instances associated with this one because they are part of the same channel will share this value |
| `circuit_id` | which signal this component is electrically connected to |
| `circuit_port_number` | the sequential id of this item in its signal chain |
| `node_at_end_a` | derived from formboard definition |
| `node_at_end_b` | derived from formboard definition |
| `print_name_at_end_a` | human-readable name of this instance if needed, associated with 'node_at_end_a' |
| `print_name_at_end_b` | human-readable name of this instance if needed, associated with 'node_at_end_b' |
| `parent_csys_instance_name` | the other instance upon which this instance's location is based |
| `parent_csys_outputcsys_name` | the specific output coordinate system of the parent that this instance's location is based |
| `2d_translate` | dict {x, y, rotate} in the parent CSYS; used by flattened drawings |
| `3d_translate` | 6DOF dict {x, y, z, alpha, beta, gamma}; α about X, γ about Z, used by STEP |
| `absolute_rotation` | manual add, not nominally used unless it's a flagnote, segment, or node |
| `csys_children` | imported csys children from library attributes file |
| `cable_group` | other instances associated with this one because they are part of the same cable will share this value |
| `cable_identifier` | which conductor in that cable this instance is assigned to (unique within the cable) |
| `length` | derived from formboard definition, the length of a segment |
| `length_tolerance` | derived from formboard definition, the tolerance on the length of a segment |
| `diameter` | apparent diameter of a segment <---------- change to print_diameter |
| `appearance` | see harnice.utils.appearance for details |
| `device_configuration` | compact JSON of filled configuration-setup answers (from BOM) |
| `note_type` | build_note, rev_note, etc |
| `note_number` | if there is a counter involved (rev, bom, build_note, etc) |
| `note_parent` | the instance the note applies to. typically don't use this in the instances list, just note_utils |
| `note_text` | the content of the note |
| `note_affected_instances` | list of instances that are affected by the note |
| `lib_repo` | publically-traceable URL of the library this instance is from |
| `lib_subpath` | path to the instance within the library (directories between the project type and the part number) |
| `lib_desc` | description of the instance per the library's revision history |
| `lib_latest_rev` | the latest revision of the instance that exists in the remote library |
| `lib_rev_used_here` | the revision of the instance that is currently used in this project |
| `lib_status` | the status of the instance per the library's revision history |
| `lib_releaseticket` | documentation needed |
| `lib_datestarted` | the date this instance was first added to the library |
| `lib_datemodified` | the date this instance was last modified in the library |
| `lib_datereleased` | the date this instance was released in the library, if applicable, per the library's revision history |
| `lib_drawnby` | the name of the person who drew the instance, per the library's revision history |
| `lib_checkedby` | the name of the person who checked the instance, per the library's revision history |
| `project_editable_lib_modified` | a flag to indicate if the imported contents do not match the library's version (it's been locally modified) |
| `lib_build_notes` | recommended build notes that come with the instance from the library |
| `lib_tools` | recommended tools that come with the instance from the library |
| `attributes_json` | if an instance is imported with an attributes json attached, it's added here |
| `device_side_refdes` | if device_connector, refdes of the device it plugs into |
| `device_side_connector_id` | if device_connector, name of the connector it plugs into |
| `device_side_connector_mpn` | if device_connector, mpn of the connector it plugs into |
| `device_side_from_cavity` | if circuit, cavity on the from side (from circuits list harness_from_cavity) |
| `device_side_to_cavity` | if circuit, cavity on the to side (from circuits list harness_to_cavity) |
| `harness_side_connector_id` | asserted name of the mating harness connector (from system connector list) |
| `this_harness_from_device_refdes` | if this instance is a channel, circuit, conductor, etc, the refdes of the device it interfaces with, just within this harness |
| `this_harness_from_device_channel_id` | if this instance is a channel, circuit, conductor, etc, the channel id in the device it interfaces with, just within this harness |
| `this_harness_from_device_connector_name` | if this instance is a channel, circuit, conductor, etc, the name of the connector it interfaces with, just within this harness |
| `this_harness_to_device_refdes` | if this instance is a channel, circuit, conductor, etc, the refdes of the device it plugs into just within this harness |
| `this_harness_to_device_channel_id` | if this instance is a channel, circuit, conductor, etc, the channel id in the device it plugs into, just within this harness |
| `this_harness_to_device_connector_name` | if this instance is a channel, circuit, conductor, etc, the name of the connector it plugs into, just within this harness |
| `this_channel_from_device_refdes` | if this instance is a channel, circuit, conductor, etc, the refdes of the device it interfaces with, at the very end of the channel |
| `this_channel_from_device_channel_id` | if this instance is a channel, circuit, conductor, etc, the channel id in the device it interfaces with, at the very end of the channel |
| `this_channel_to_device_refdes` | if this instance is a channel, circuit, conductor, etc, the refdes of the device it plugs into, at the very end of the channel |
| `this_channel_to_device_channel_id` | if this instance is a channel, circuit, conductor, etc, the channel id in the device it plugs into, at the very end of the channel |
| `this_channel_from_channel_type` | if this instance is a channel, circuit, conductor, etc, the type of the channel it interfaces with, at the very end of the channel |
| `this_channel_to_channel_type` | if this instance is a channel, circuit, conductor, etc, the type of the channel it plugs into, at the very end of the channel |
| `signal_of_channel_type` | if this instance is a channel, circuit, conductor, etc, the signal of the channel it interfaces with, at the very end of the channel |


---
##Commands:
*These functions are already available in build instructions as `instances_list`. Use them as written.*
??? info "`instances_list.new_instance(instance_name, instance_data, ignore_duplicates=False)`"

    Add a new instance to the instances list.
    
    ## Usage
    `new_instance(instance_name, instance_data, ignore_duplicates=False)`
    
    ## Args
    - `instance_name`: String; must be unique within the list.
    - `instance_data`: Dict of column names to values. May include `instance_name`; if present it must match the `instance_name` argument or the code will fail.
    - `ignore_duplicates`: If True, does nothing when an instance with the same `instance_name` already exists. If False (default), raises an error on duplicate.
    
    ## Returns
    -1 on success. Raises on invalid input or duplicate (when `ignore_duplicates` is False).

??? info "`instances_list.modify(instance_name, instance_data)`"

    Update columns for an existing instance by name.
    
    ## Args
    - `instance_name`: The unique name of the instance to modify.
    - `instance_data`: Dict of column names to new values. Only provided keys are updated; others are unchanged.
    
    ## Raises
    ValueError if no instance with `instance_name` exists.

??? info "`instances_list.remove_instance(instance_to_delete)`"

    Remove one instance from the instances list.
    
    ## Args
    - `instance_to_delete`: Instance row dict (or any dict) whose `instance_name` key identifies the instance to remove. Matching is done by `instance_name` only.

??? info "`instances_list.new()`"

    Create a new empty instances list file with only the standard header (COLUMNS). Overwrites existing file if present.

??? info "`instances_list.assign_bom_line_numbers()`"

    Assign sequential BOM line numbers to instances that have `bom_line_number` set to "True".
    
    Groups by MPN and assigns the same line number to all instances sharing an MPN. Requires every such instance to have a non-empty `mpn`. Line numbers are assigned in order of first occurrence of each MPN.
    
    ## Raises
    ValueError if any instance marked for BOM has an empty `mpn`.

??? info "`instances_list.attribute_of(target_instance, attribute)`"

    Return the value of one column for a single instance.
    
        String values that look like Python literals (list or dict, e.g. starting with `[` or `{`) are parsed with `ast.literal_eval` and the parsed value is returned; otherwise the raw string is returned.
    
    ## Args
    - `target_instance`: The `instance_name` of the instance to look up.
    - `attribute`: The column name to read (e.g. `"mpn"`, `"harness"`).
    
    ## Returns
    The value of that column for the matching instance, or None if not found or attribute missing. List/dict-like strings are returned as list/dict.

??? info "`instances_list.instance_in_connector_group_with_item_type(connector_group, item_type)`"

    Return the single instance in a connector group with the given item type.
    
    ## Args
    - `connector_group`: The `connector_group` value to match.
    - `item_type`: The `item_type` value to match (e.g. connector, backshell).
    
    ## Returns
    The matching instance row dict, or 0 if no match.
    
    ## Raises
    ValueError if `connector_group` or `item_type` is blank, or if more than one instance matches.

??? info "`instances_list.seed_connector_nodes()`"

    Creates a node instance for each connector group and parents each connector to it.
    
    Intended for harness build instructions after connectors exist (for example after
    importing a harness from a system). For each ``harness_connector`` or
    ``device_connector`` with a non-blank ``connector_group``:
    
    - Ensures ``{connector_group}.node`` exists (``item_type`` / ``location_type``
      ``"node"``)
    - If the connector has no ``parent_csys_instance_name``, sets it to that node
      with ``parent_csys_outputcsys_name`` ``"origin"``
    
    Connectors that already have a parent coordinate system are left unchanged.

??? info "`instances_list.list_of_uniques(attribute)`"

    Return a list of unique non-empty values for one column across all instances.
    
    ## Args
    - `attribute`: The column name to collect (e.g. `"harness"`, `"item_type"`).
    
    ## Returns
    List of unique values; blanks and None are omitted. Order follows first occurrence in the instances list.

