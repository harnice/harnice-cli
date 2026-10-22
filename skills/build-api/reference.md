# System and harness build API

Both `skills/system/SKILL.md` and `skills/harness/SKILL.md` use this file.
Call a function as `module.function(...)`. The skill you are following
names the headings you may use. A heading it does not name is the other
project's script.

This catalog is the console ribbon, plus `chtype` and the list `.read()`
calls the default scripts use.

Read the arguments before you call a function. A doc page is under
`src/harnice/docs/` in the harnice-cli clone, which is also the folder
`harnice --docs` prints. When no page is listed, read the docstring in
the source file in that same clone. Do not guess a signature. Do not
invent a function that is not on this page.

## Instances List

*instances_list: docs `interacting_with_data/_instances_lists.md`; source `lists/instances_list.py`.*

- `instances_list.new` — Create a new empty instances list file with only the standard header (COLUMNS). Overwrites existing file if present.
- `instances_list.new_instance` — Add a new instance to the instances list.
- `instances_list.remove_instance` — Remove one instance from the instances list.
- `instances_list.modify` — Update columns for an existing instance by name.
- `instances_list.attribute_of` — Return the value of one column for a single instance.
- `instances_list.list_of_uniques` — Return a list of unique non-empty values for one column across all instances.
- `instances_list.instance_in_connector_group_with_item_type` — Return the single instance in a connector group with the given item type.
- `instances_list.seed_connector_nodes` — Creates a node instance for each connector group and parents each connector to it.
- `instances_list.raise_error_on_unassigned_connectors` — Raise if any harness_connector instance has no mpn assigned.
- `instances_list.assign_bom_line_numbers` — Assign sequential BOM line numbers to instances that have bom_line_number set to "True".

## Bundle Networks

### Available Network

*available_network: source `lists/available_network.py`.*

- `available_network.load` — Load the available network from disk.
- `available_network.source_context_from_path` — Copy a STEP file into this harness as routing context.
- `available_network.source_available_network_from_project` — Copy another project's available network into this harness.

### Chosen Network

*chosen_network: source `lists/chosen_network.py`.*

- `chosen_network.end_all_segments_in_nodes` — Processes an input network dict.
- `chosen_network.ensure_nodes_exist` — Ensures that every node in the list is present in the network.
- `chosen_network.calculate_possible_sub_networks` — Processes an input dict and searches it for all possible solutions connecting a set of nodes to other nodes via a set of segments.
- `chosen_network.find_network_with` — Processes a list of input dicts and returns just the networks that contain segments or nodes with id's in their respective lists.
- `chosen_network.save` — Stores a network dict into fileio.path("chosen network").

### Bundle Network Utils

*bundle_network_utils: source `utils/bundle_network_utils.py`.*

- `bundle_network_utils.compose_csys` — Compose child CSYS dicts left to right.
- `bundle_network_utils.invert_csys` — Return the opposite of a child CSYS.
- `bundle_network_utils.difference_between_csys` — Direction that takes to_csys onto from_csys.
- `bundle_network_utils.calculate_location_3d` — Calculates the 3D world pose of an instance from the CSYS chain.
- `bundle_network_utils.move_node` — Moves one node in a network.
- `bundle_network_utils.adjacent_nodes` — Traverses the network from a given node and returns a list of dicts representing nodes that are one segment of connection away.
- `bundle_network_utils.path_angle` — Angle of a hop in a node's frame, in degrees [0, 360).
- `bundle_network_utils.output_csys` — Named output CSYS on one instance (no parent-chain walk).
- `bundle_network_utils.output_offset` — Node move taken from one instance output CSYS.
- `bundle_network_utils.rotate_csys` — Rotate a child CSYS about a parent axis.
- `bundle_network_utils.spin` — Write one Euler component of 3d_translate on an instance.
- `bundle_network_utils.clock_backshell` — Clock a backshell on connector_group and un-clock its connector.
- `bundle_network_utils.rename_node` — Finds a node and changes its id.
- `bundle_network_utils.new_node` — Adds a node at a location.
- `bundle_network_utils.reroute_segment` — Moves a segment that ends at an existing node to the coordinates of a new node.

### Flattened Network

*flattened_network: source `lists/flattened_network.py`.*

- `flattened_network.derive` — Builds the flattened network CSV from a JSON network dict.

## Channels and Mapping

### Channel Map

*channel_map: docs `interacting_with_data/_channel_maps.md`; source `lists/channel_map.py`.*

- `channel_map.new` — Makes a new blank channel map. Overwrites existing channel map.
- `channel_map.map` — Map one channel endpoint to another (a patch), or consume it onto a multi-channel junction.
- `channel_map.force` — Map one channel endpoint to another regardless of channel-type compatibility.
- `channel_map.compile_hierarchical` — Write the hierarchical channel map for this system and every child subsystem.
- `channel_map.already_mapped` — Return whether an endpoint is already in the mapped-channels set.
- `channel_map.already_mapped_set` — Return the set of endpoint keys already consumed by map or route.
- `channel_map.already_mapped_set_append` — Mark one endpoint as already mapped.

### Passthrough Map

*passthrough_map: docs `interacting_with_data/_passthrough_maps.md`; source `lists/passthrough_map.py`.*

- `passthrough_map.new` — Create passthrough channel rows from placed-device signals lists.
- `passthrough_map.route` — Route a mapped channel through a passthrough device.
- `passthrough_map.resolve` — Complete passthrough routing for each mapped channel (channel-map order).

## Signals

*signals_list: docs `interacting_with_data/_signals_lists.md`; source `lists/signals_list.py`.*

- `signals_list.new` — Create a signals TSV at fileio.path("signals list") with only the header row.
- `signals_list.append` — Append one signal row. Missing optional fields are written as empty strings.
- `signals_list.cavity_of_signal` — Return the cavity a signal uses on one channel endpoint.
- `signals_list.connector_id_of_channel` — Return connector_id for a channel endpoint.

## Electrical

### Circuits

*circuits_list: docs `interacting_with_data/_circuits_lists.md`; source `lists/circuits_list.py`.*

- `circuits_list.force` — Pair the signals of one pending channel_map.force() patch.
- `circuits_list.new` — Build the circuits list from the channel map and passthrough map.

### Cables

*cable_utils: docs `commands/_cable_utils.md`; source `utils/cable_utils.py`.*

- `cable_utils.new_cable` — Imports a library cable into the project as a new cable instance.
- `cable_utils.prepare_for_conductor_assign` — Clears system cable-recommendation fields on a conductor so it can be assigned.
- `cable_utils.assign_conductor_to_cable` — Assigns a conductor instance to one conductor inside an existing cable.
- `cable_utils.map_cables_and_conductors_to_segments` — Routes every conductor and cable onto the flattened network and writes lengths.
- `cable_utils.calculate_bundle_diameter` — Estimates the outer diameter of a segment from the cables it carries.

## Revision History

### Revision History

*rev_history: docs `interacting_with_data/_revision_history_lists.md`; source `lists/rev_history.py`.*

- `rev_history.new` — Create a new revision history file.
- `rev_history.append` — Append a new revision history entry to the current revision history file.
- `rev_history.overwrite` — Overwrite a revision history entry.
- `rev_history.info` — Get information about a revision history entry.
- `rev_history.initial_release_exists` — Check if an initial release exists.
- `rev_history.initial_release_desc` — Get the description of the initial release.
- `rev_history.part_family_append` — Append a new revision history entry to the part family revision history file.
- `rev_history.update_datemodified` — Update the datemodified field of the current revision with today's date.

## Build instructions tools

### General

*build_utils: docs `commands/_build_utils.md`; source `utils/build_utils.py`.*

- `build_utils.run_instruction_from_relative` — Imports a function from a relative project's build instructions and calls it here.
- `build_utils.lookup_outputcsys_from_lib_used` — Looks up coordinate system transform from an instance's library attributes.

### Macros

*build_utils: docs `commands/_build_utils.md`; source `utils/build_utils.py`.*

- `build_utils.run_macro` — Runs a macro script from the library with the given artifact ID.

### Part Libraries

*library_utils: docs `commands/_library_utils.md`; source `utils/library_utils.py`.*

- `library_utils.pull` — Imports a part from the library into the project.
- `library_utils.get_local_path` — Looks up the local filesystem path for a library repository URL.

### Part Library History

*library_history: docs `interacting_with_data/_library_history.md`; source `lists/library_history.py`.*

- `library_history.new` — Create an empty library-history file, replacing one that already exists.
- `library_history.append` — Record one library import in the library history.

## Build Notes

### General

*note_utils: docs `commands/_note_utils.md`; source `utils/note_utils.py`.*

- `note_utils.new_note` — Creates or updates a note instance.
- `note_utils.combine_notes` — Combines multiple notes by merging their affected instances into one note.
- `note_utils.parse_note_instance` — Return a full copy of instance, but with note_affected_instances parsed into a real Python list (or left alone if blank).
- `note_utils.assign_buildnote_numbers` — Assigns sequential numbers to build note instances.
- `note_utils.get_lib_build_notes` — Returns list of build_notes for this instance from the TSV row. Safely parses with ast.literal_eval.
- `note_utils.get_lib_tools` — Returns list of tools for this instance from the TSV row. Safely parses with ast.literal_eval.
- `note_utils.make_bom_flagnote` — Creates a BOM item flagnote dictionary for an instance.
- `note_utils.make_buildnote_flagnote` — Creates a build note flagnote dictionary linking a note to an instance.
- `note_utils.make_part_name_flagnote` — Creates a part name flagnote dictionary for an instance.
- `note_utils.make_rev_change_flagnote` — Creates a revision change callout flagnote dictionary linking a note to an instance.
- `note_utils.make_rev_history_notes` — Creates revision change callout notes based on revision history.

## Utils

### SVG

*svg_utils: docs `commands/_svg_utils.md`; source `utils/svg_utils.py`.*

- `svg_utils.add_entire_svg_file_contents_to_group` — Wraps the entire contents of an SVG file in a new group element.
- `svg_utils.find_and_replace_svg_group` — Copies SVG group content from one file to another, replacing existing group content.
- `svg_utils.draw_filleted_styled_path` — Draws a path through a list of corner points, inserting a circular fillet at each interior point, and appends a single SVG <path> element to
- `svg_utils.table` — This function is called when the user needs to build a general SVG table. python
- `svg_utils.label_svg` — Generate an SVG label: text in a rectangular box, aligned to a wire tangent.
- `svg_utils.draw_segments_across_paths` — Maps segment-type instances onto a 2D wire network, offsets parallel paths at shared nodes, draws each path and its labels, and returns raw SVG markup.
- `svg_utils.draw_clean_line` — Generates SVG markup for a line connecting two instance locations, with optional arrowheads.

### Appearance

*appearance: docs `commands/_appearance.md`; source `utils/appearance.py`.*

- `appearance.parse` — Parse a dict or dict-string, converting color-like values to #rrggbb.
- `appearance.to_rgb` — Return (r, g, b) in 0–255 from a color name, hex string, or appearance dict.
- `appearance.black_or_white_to_contrast_with_color` — Return #ffffff or #000000, whichever has higher WCAG contrast against the color.

## System

### General

*system_utils: docs `commands/_system_utils.md`; source `utils/system_utils.py`.*

- `system_utils.create_instances_from_circuits_list` — Creates connector, cavity, channel, and circuit instances from the circuits list.
- `system_utils.import_harness_from_harnice_system` — Import harness instances from a system revision's instances list for one harness.
- `system_utils.connector_of_channel` — Connector id for a channel endpoint.
- `system_utils.find_connector_with_no_circuit` — Validates that all connectors have associated circuits.
- `system_utils.mpn_of_device_refdes` — Looks up manufacturer part number information for a device reference designator.

### Post-Harness Instances

*post_harness_instances_list: docs `interacting_with_data/_post_harness_instances_lists.md`; source `lists/post_harness_instances_list.py`.*

- `post_harness_instances_list.rebuild` — Build the 'post harness instances list' by merging instance data from: - Every instances.tsv under the system harnesses/ directory
- `post_harness_instances_list.push` — Copy this harness instances list into a system revision's harnesses folder.

## Files and State

### Current State

*state: source `state.py`.*

- `state.partnumber` — Return the current part number and/or revision in the requested format.
- `state.set_pn` — Set the current part number (e.g. "mypart"). Called by fileio.verify_revision_structure().
- `state.set_rev` — Set the current revision (number or string, e.g. 1 or "A"). Called by fileio.verify_revision_structure().
- `state.set_project_type` — Set the current project type (e.g. "harness", "system").
- `state.set_harness` — Set the current harness context (used during build).
- `state.set_file_structure` — Set the default file structure dict used by fileio.path() and fileio.dirpath().

### Finding Files

*fileio: docs `commands/_manipulating_files.md`; source `fileio.py`.*

- `fileio.path` — Return the full path to a file identified by its file key.
- `fileio.dirpath` — Return the full path to a directory identified by its key in the file structure.
- `fileio.part_directory` — Return the part directory: the parent of the current working directory.
- `fileio.rev_directory` — Return the current revision directory (the current working directory).
- `fileio.read_tsv` — Read a TSV file and return a list of row dicts (one dict per row, keys from header).
- `fileio.verify_revision_structure` — Ensure the current directory is a valid revision folder and set state.pn and state.rev.
- `fileio.harnice_root` — Return the Harnice user-data directory on this computer.
- `fileio.drawnby` — Load and return the contents of the drawnby file (path from fileio.path("drawnby")).
- `fileio.today` — Return today's date as a short string: M/D/YY (e.g. 2/12/25).

### Commands

*fileio: docs `commands/_manipulating_files.md`; source `fileio.py`.*

- `fileio.silentremove` — Remove a file or directory and its contents if it exists.
- `fileio.get_git_hash_of_harnice_src` — Return the git commit hash of the Harnice source repo (HEAD).

### Output

*cli: source `cli.py`.*

- `cli.warn` — Print Warning: {message} to stdout in yellow.

## Channel types

*chtype: docs `project_types/_channel_type.md`; source `project_types/chtype.py`.*

- `chtype.parse` — Convert stored string into a tuple (chid:int, lib_repo:str). Handles both single tuples and extracts first tuple from lists.
- `chtype.signals` — Return the list of signal names associated with a specific channel type.
- `chtype.compatibles` — Look up other channel types that are declared as compatible with the given channel type.
- `chtype.is_or_is_compatible_with` — Return the given channel type plus all channel types declared as compatible with it.
- `chtype.attribute` — Read any additional column from channel_types.tsv for a given channel type.
- `chtype.path` — Resolve the on-disk path to the channel_types.tsv file for a given channel type.

## Reading a list back

The ribbon writes lists. The default scripts read them back with `.read()`.
Use the same doc page as that module above.

- `instances_list.read` — Return the current instances list (cached).
- `signals_list.read` — Return signals-list rows from a path, file key, or the current project list.
- `channel_map.read` — Return the channel map (cached).
- `circuits_list.read` — Return the circuits list (cached).
- `passthrough_map.read` — Return the passthrough map (cached).
- `rev_history.read` — Return a revision history (cached).
- `library_history.read` — Return the library import history (cached).

## Shipped macros

`build_utils.run_macro` runs these from
`https://github.com/harnice/harnice-general-library`.
Harness macros use `library/macros/harness_artifacts`.
`subsystem_symbol` uses `library/macros/system_artifacts`.
Read `project_types/_macro.md` before you change the arguments.

- `bom_exporter_bottom_up` — BOM table (TSV + SVG)
- `tooling_list_exporter` — required-tooling list
- `standard_harnice_formboard` — formboard SVG from the flattened network
- `basic_segment_generator` — one segment drawing (usually called by the formboard)
- `trace_layout_visualizer` — conductor or cable routes on the formboard
- `circuit_visualizer` — one schematic row per conductor
- `revision_history_table` — revision-history SVG table
- `build_notes_table` — build-notes SVG table
- `wirelist_exporter` — wirelist CSV / XLS / SVG
- `harness_step_builder` — 3D STEP of the harness
- `cutlist_exporter_bottom_up` — cut-list table
- `pdf_generator` — multi-page PDF from *-master.svg files
- `subsystem_symbol` — system-as-device symbol SVG
