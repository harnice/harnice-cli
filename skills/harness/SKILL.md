---
name: harness-build
description: >-
  Write or edit Harnice harness build.py: import a harness from its system,
  call that system's connector choosers, pull parts, turn the available
  network into the chosen network, assign cables, and build the drawings.
  Use when the user asks for harness build instructions, harness rules, a
  chosen network, a formboard, a node move, or a backshell clock. A system
  revision uses the system-build skill. A device pinout uses the
  device-signals-list skill. A catalog of library SKUs uses the part-family
  skill. Follow this skill when it is the best match. Do not ask which skill
  to follow. If the request is not clear, ask for clarification.
---

# Harnice harness build instructions

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

This file is the procedure for a **harness** `build.py`. The pages you
may call are listed below. Each page is the list of calls and how to
use them. Read it before you call. Do not invent a call, a signature,
or a column.

A system revision follows `skills/system/SKILL.md`. A device signals list
follows `skills/device-signals-list/SKILL.md`. A catalog of library SKUs
follows `skills/part-family/SKILL.md`.


## Why the script exists

The instances list is the source of truth for a harness or a system. It
records every piece of data about every item or idea in that project.
Build instructions build that list up. When an artifact has to describe
the project, the same script exports it from the list.


## What runs

The script is `fileio.path("build instructions")` in the harness revision.
Do not run `build.py`. From that revision folder, `harnice -b` runs the
project. If this revision is a system, stop and follow the system skill.

Do not import anything. The names you need are already bound.

Read the `build.py` already in the revision before you replace it. The
stock script is in the clone at:

    src/harnice/defaults/harness_default_build_instructions.py

That script makes a new harness build, and it shows the usual steps.
Remove a section the project does not need. The script has to succeed.
Code at module level runs on every build.

Reach files with `fileio.path` and `fileio.dirpath`. The keys are in
`skills/fileio/SKILL.md`. Do not join folders into a path yourself.

Which extra harness rule to add is my decision. Ask, and put the choice
in front of me. Record it in a comment. `cli.warn` prints a warning and
continues. Raising stops the build.

Connector and backshell part numbers are `connector_chooser` and
`m85049_chooser` on the parent system. This script calls them. It does
not define them. Follow `skills/system/SKILL.md` only when I asked you
to change those functions on the system.


## Design intent

The user describes the goal. Implement it with the calls in this skill.
A stock section can stay, change, or go. The comment on a new rule
states the goal. The script has to succeed.

This skill edits `build.py` only. Do not edit a block diagram, a PDF, or
explain the console.

The available network is the shape the transformation starts from. It is
already on disk. Harnice's own calls read and write the network files.
The script describes the transformation.

Use ordinary Python for the logic: which route, which node, a condition,
a number. Prefer harnice api wherever possible. 

A STEP context is `available_network.source_context_from_path`. Another
project's available network is
`available_network.source_available_network_from_project`. Harnice
functions turn the available network into the chosen network. Each call
changes a small piece: close a free end, add a missing connector node,
keep one route, then move a node.

```python
available_network = available_network.load()
```

If the goal belongs on another project, stop. Say: "This would be better
suited for {project}. Can you point me to that project? I don't want to
modify it without your explicit permission." A system owns channel maps,
passthroughs, circuits, and the connector choosers. A device signals
list is a pinout. A part family is a catalog of SKUs.

If these calls cannot do the goal, or the goal does not name enough to
pick a call, ask and say what is missing. Do not invent a call.

A rule you add is one sentence and a short example. The example uses a
placeholder the user named, such as `connector_group` or `node_id`.


## Call these pages only

- `instances_list` — `docs/interacting_with_data/_instances_lists.md`
- `available_network` — `docs/interacting_with_data/_available_network.md`
- `chosen_network` — `docs/interacting_with_data/_chosen_network.md`
- `bundle_network_utils` — `docs/commands/_bundle_network_utils.md`
- `flattened_network` — `docs/interacting_with_data/_flattened_network.md`
- `cable_utils` — `docs/commands/_cable_utils.md`
- `rev_history` — `docs/interacting_with_data/_revision_history_lists.md`
- `build_utils` — `docs/commands/_build_utils.md`
- `library_utils` — `docs/commands/_library_utils.md`
- `library_history` — `docs/interacting_with_data/_library_history.md`
- `note_utils` — `docs/commands/_note_utils.md`
- `system_utils.import_harness_from_harnice_system` only — `docs/commands/_system_utils.md`
- `post_harness_instances_list` — `docs/interacting_with_data/_post_harness_instances_lists.md`
- `fileio`, `state`, and `cli` — `docs/commands/_manipulating_files.md`
- Shipped macros except `subsystem_symbol` — `docs/project_types/_macro.md`

Do not call channel maps, passthroughs, circuits, signals, or channel
types. Those are the system script. Do not define `connector_chooser`
or `m85049_chooser` here.


## Data model

Column descriptions live on the doc page for that list. This section
is the harness rule for those columns: which ones a script sets, and
what an import writes.

List cells are strings when a script reads them back. Write a Python
value into `modify` or `new_instance`; the file stores the text form.
`attribute_of` parses a cell that starts with `[` or `{` into a list or
dict. A blank cell and a missing key both come back as `""`.

### Instances list

`fileio.path("instances list")` is `instances.tsv` in the revision.
The columns are on `interacting_with_data/_instances_lists.md`.

A part that belongs on the BOM has `bom_line_number` set to the string
`"True"`. `assign_bom_line_numbers` replaces that cell. The same MPN
shares one line. A marked row with a blank `mpn` raises.

`node_at_end_a` and `node_at_end_b` are node ids on a segment and
cavity names on a conductor. `parent_csys_outputcsys_name` `"origin"`
is the parent's own origin. `output_csys` reads `csys_children`.

`2d_translate` is `{x, y, rotate}` in the parent frame. Drawing Y
points down. `3d_translate` is `{x, y, z, alpha, beta, gamma}`. Angles
are ZYX degrees.

`cable_group` is the cable instance name. `cable_identifier` is one
conductor inside that cable. `diameter` is the bundle diameter in
inches, written by `calculate_bundle_diameter`.

`note_affected_instances` is a Python-literal list of instance names.
A blank cell parses to an empty list.

### Item types after import

`import_harness_from_harnice_system` copies rows whose `harness` column
is `source_refdes`. It keeps connectors, cavities, and circuits, and
drops other system rows such as `harness-channel`.

- A system `device_connector` becomes `item_type` `harness_connector`.
  `instance_name`, `connector_group`, `print_name`, and
  `harness_side_connector_id` are the asserted mating name. It is
  parented to `{name}.node` on output `"origin"`. The device-side
  refdes, connector id, and MPN are kept so a chooser can read
  `device_side_connector_mpn`.
- That import also creates `{name}.node`: `item_type` and
  `location_type` `"node"`, same `connector_group`.
- A system cavity becomes `device_connector_cavity`, named
  `{harness_side_connector_id}.{cavity}`, in that connector group.
  `print_name` is `cavity {cavity}`.
- A system circuit becomes `conductor`, named `conductor-{circuit_id}`,
  `location_type` `"segment"`. `node_at_end_a` and `node_at_end_b` are
  the cavity instance names, `{connector}.{cavity}`. Print names,
  `appearance`, and the cable recommendation (`mpn`, `lib_repo`,
  `lib_subpath`, `cable_group`, `cable_identifier`) are copied from
  the circuit. The recommendation is optional.

`seed_connector_nodes` runs at the end of that import. It creates a
missing `{connector_group}.node` for each `harness_connector` or
`device_connector`, and parents a connector that has no parent yet.

The script then adds:

- `backshell`, in the connector group, parented to the node on
  `"origin"`. The connector's parent then becomes that backshell on
  output `"connector"`.
- `cable`, from `new_cable`. `location_type` is `"segment"`.
  `cable_group` equals the cable's instance name.
- `segment` and any network node `derive` did not already find.
- `conductor-segment` and `cable-segment`, one per hop, named
  `{owner}.{segment_id}`.
- `note`, from `new_note`, named `note-1`, `note-2`, … for the life of
  the process.
- `flagnote` dicts passed into the formboard macro. Those makers return
  a dict. The stock script appends the dict to the formboard instance
  list. It does not call `new_instance`.

### Parent pose and named outputs

A row's world pose is the walk from `origin` through each
`parent_csys_instance_name`. At each link the parent's named output is
applied, then that row's `3d_translate`. `calculate_location_3d` reads
that walk. It does not move a network node.

A named output lives in `csys_children`. A child may give Cartesian
`x`, `y`, and `z`, or polar `distance` and `angle` in the parent's XY
plane. Rotation prefers `alpha`, `beta`, `gamma`, then library `rx`,
`ry`, `rz`. A 2D `rotation` is about Z and becomes `gamma`. `"origin"`
is the zero output and does not need a child entry. The lookup also
accepts a library name `3d-{name}` when `{name}` is missing, and the
name `"connector"` also matches `"3d-connector"`.

`output_csys` returns `{x, y, z, alpha, beta, gamma}` for one child on
one part. It does not walk parents. `output_offset` inverts that child:
the shift from the feature back to the part origin, in the current node
frame. Pass that dict to `move_node`.

`lookup_outputcsys_from_lib_used` is the 2D reader. It returns
`(x, y, rotation)` from the pulled `attributes.json`, with polar
`distance` and `angle` folded into `x` and `y`. `"origin"` and a
missing attributes file return `(0, 0, 0)`. A named child that is
absent from an attributes file that does exist raises.

### Appearance

`appearance` is a dict, stored as a Python literal in the TSV:

- `base_color` is the insulation or jacket. A drawn path needs it.
- `outline_color` is an optional second band.
- `parallelstripe` and `perpstripe` are lists of colors.
- `twisted` is `None`, `"RH"`, or `"LH"`.
- `slash_lines` is `{direction, angle, step, color, slash_width_inches}`.
  `direction` is `"RH"` or `"LH"`.

A color is an SVG/CSS Level 1 keyword, `#rgb`, or `#rrggbb`.
`assign_conductor_to_cable` copies the conductor-list `appearance`
onto the conductor, and the cable attributes `appearance` (or a
`properties.color` used as `base_color`) onto the cable.

### Network JSON

`fileio.path("available network")` is `networks/available.json`.
`fileio.path("chosen network")` is `networks/chosen.json`. Both are:

```python
{
    "nodes": [
        {"node_id": "P1.node", "location": [x, y, z], "alpha": 0, "beta": 0, "gamma": 0}
    ],
    "segments": [
        {
            "segment_id": "P1.node_leg",
            "location_at_end_a": [x, y, z],
            "location_at_end_b": [x, y, z],
            "spline_control_points": [],
        }
    ],
}
```

Angles on a node are ZYX degrees and may be `None` until something sets
them. `location` matches a segment end when the points are within
`1e-6`. Two nodes with different ids at one location are an error.
Two segments on the same pair of endpoints are an error.

`spline_control_points` are offsets from end A, in order from A to B.
Each stored control triple is an offset from end A. An empty list is a straight
line. `spline_points` and `spline_length` place the stored triples in
the Bezier polygon as `[end_a, *stored, end_b]` without adding end A.
`derive` measures length with `spline_length`. `move_node` moves an
end that sits on the old node location, and moves a stored control
triple only when that triple itself sits on the old location.

`new_node` appends a node and does not add a segment. A segment the
script appends is the four fields above. The stock sprout uses
`segment_id` `{missing_node}_leg`.

`load()` writes a starter file when `available.json` is missing. Zero
node instances raises. One node is parked at the origin and a partner
named `far` (or `far-2`) is added at `(-4, 0, 0)` with one segment.
Two nodes sit at the origin and at `(x, 0, 0)` with `x` random in
`[6, 18]`. Three or more get a `hub` at the origin and a spoke per
node, length 6 to 18, at a random angle. The stock sprout for a node
the file does not already contain is the same 6-to-18 leg off the
first existing node, or the origin when the file has no nodes.

### Flattened network

`fileio.path("flattened network")` is `networks/flat.csv`. The columns
are on `interacting_with_data/_flattened_network.md`.

`derive` is the stock call after `chosen_network.save`. Leave the
heading columns in the CSV. A harness script does not call
`oriented_spline_points`.

### Cable mapping rows

`map_cables_and_conductors_to_segments` resolves each conductor end to
the `node` in that cavity's `connector_group`, searches the segment
graph, and writes one `conductor-segment` per hop through
`write_mapped_segment_instances`. A conductor whose ends resolve to
the same node is a loopback: it goes out and back on that connector's
free stub, and each hop length is twice the segment length. The
conductor's own `length` becomes the sum of its hop lengths.

A cable has no ends of its own. It is laid on the segments shared by
every assigned conductor, as `cable-segment` rows. Those shared ends
are written to the cable's `node_at_end_a` / `node_at_end_b`. The
cable's `length` is the longest member conductor.

`conductors.tsv` for a pulled cable lives at
`instance_data/cable/{instance_name}/conductors.tsv`. The `identifier`
column is what `assign_conductor_to_cable` takes as
`cable_identifier`. Jacket and conductor diameters come from the
cable `attributes.json` and from `od` or `gauge` / `awg` on that
conductor row. An assigned conductor with neither raises. An
unassigned conductor with neither is counted as 0.2 in, and that
assumption is printed. Bundle OD is average member OD times Stringer's
1978 bundle factor, written to the segment's `diameter`.

### Revision history

The revision-history file is the part file above the revision folder.
The columns are on `interacting_with_data/_revision_history_lists.md`.

`status` with any text blocks a build. Leave it blank while the
revision is in work.

The stock import reads `source_part_number`, `source_revision`,
`source_lib_repo`, `source_subpath`, and `source_refdes`.

`overwrite` may set `desc`, those `source_*` fields, `datemodified`,
`datereleased`, `checkedby`, `revisionupdates`, and
`affectedinstances`. These keys raise if a script writes them:
`project_type`, `mfg`, `pn`, `rev`, `releaseticket`, `library_repo`,
`library_subpath`, `datestarted`, `last_build`. An unknown key raises.
The row updated is `state.rev`. The arguments of `info` and `read`
are on that same page.

### Library history

`fileio.path("library history")` is `libhist.tsv`. One row per pull:
`instance_name`, `mpn`, `item_type`, `lib_repo`, `lib_subpath`, and the
same `lib_*` metadata columns as the instances list, plus
`project_editable_lib_modified`. `run_macro` refuses an `artifact_id`
already in this file unless `rerun=True`.

### Notes and flagnotes

A `note` row is `item_type` `"note"`. `new_note` names it
`note-{n}` and stores `note_type`, `note_text`, `note_number`,
`print_name` (the bubble), `mpn` (the flagnote shape, defaulting to
`note_type`), and `note_affected_instances`. The shape is pulled from
`library/flagnotes/` in `https://github.com/harnice/harnice-general-library`.
The same `note_type` and `note_text` update the existing row. Merging
requires both the old and the new affected-instance lists to be
non-empty. `assign_buildnote_numbers` then sets `note_number` and
`print_name` to 1, 2, … on each `build_note`.

A formboard flagnote dict uses `item_type` `"flagnote"`. Its
`instance_name` is `note-bom_item-{part}`, `note-part_name-{part}`,
`note-build_note-{note}-{part}`, or
`note-rev_change_callout-{note}-{part}`. It is parented to the part,
on the output CSYS passed as the last argument. Stock parts expose
`flagnote-1`, `flagnote-2`, … and the stock script starts that count
over on each part. `print_name` is the BOM line, the part's
`print_name` (or its instance name when the print name is blank), or
the note's bubble. `mpn` is `bom_item`, `part_name`, `build_note`, or
`rev_change_callout` under `library/flagnotes/`.

### Files a harness script reaches

The keys are in `skills/fileio/SKILL.md`. Use the harness list there,
plus the keys that exist for every project. `"post harness instances
list"` is on the system, and `push` writes it.

`state.rev` is the token `overwrite` matches. `import` sets
`state.harness` to the harness refdes.


## How to call

Names are already bound. Call them as `module.function(...)`.
The calls and their arguments are on the page listed above. Read that
page before you call. `.read()` is on that module's page.

A `bundle_network_utils` function returns a new network dict. Assign
it back.

`find_network_with` runs only when more than one solution came back
and the user named a stable id. Both id lists empty matches nothing.

A harness script uses `rev_history.read`, `info`, and `overwrite`.
`state.set_pn`, `state.set_rev`, `state.set_project_type`,
`state.set_harness`, and `state.set_file_structure` belong to the
runner. Read `state.partnumber`, `state.rev`, and `state.harness`.

`cli.warn` prints a warning and continues. Raising stops the build.


## Order

A harness made from a system position already stores `source_part_number`,
`source_revision`, `source_lib_repo`, `source_subpath`, and
`source_refdes` on the revision history. The stock script starts by
importing that harness. Keep the import when the harness comes from a
system. A harness that does not come from a system does not need it.

1. Import the harness, then write the revision description.
2. Call the parent system's choosers. Harness-local part rules go here,
   before the pull.
3. `instances_list.raise_error_on_unassigned_connectors()`, then
   `library_utils.pull` each `harness_connector` and `backshell`.
4. Load the available network, require every connector node, pick one
   chosen network, apply the layout moves, `chosen_network.save`, then
   `flattened_network.derive`.
5. Assign cables and conductors, map them onto segments, then bundle
   diameters.
6. BOM line numbers, build notes, formboard flagnotes, then the output
   macros.

### Import

```python
system_utils.import_harness_from_harnice_system(
    system_pn=rev_history.info().get("source_part_number"),
    system_rev=rev_history.info().get("source_revision"),
    system_lib_repo=rev_history.info().get("source_lib_repo"),
    system_lib_subpath=rev_history.info().get("source_subpath"),
    target_harness=rev_history.info().get("source_refdes"),
)
rev_history.overwrite(
    {
        "desc": f"HARNESS '{rev_history.info().get('source_refdes')}' FROM SYSTEM '{rev_history.info().get('source_part_number')}-{rev_history.info().get('source_revision')}'",
    }
)
```

`build_utils.run_instruction_from_relative` takes the function name,
then the parent part number, library repo, subpath, and revision, in
that order. Call `connector_chooser`, then `m85049_chooser`.

A local rule that replaces a part sets `mpn`, `lib_repo`, and
`lib_subpath` with `instances_list.modify` before `library_utils.pull`.
`pull` copies that library revision into this harness. A backshell the
local rule creates is an instance in that connector group,
`item_type` `"backshell"`, parented to the group's node. The connector
then parents to that backshell on output CSYS `"connector"`.
`clock_backshell` finds the backshell by the group. It does not create
the instance.

`instances_list.raise_error_on_unassigned_connectors()` runs after the
part numbers are set and before the pull. Pull every instance whose
`item_type` is `harness_connector` or `backshell`.


## Chosen network

The available network is the input. These calls turn it into one chosen
network. They stay in this order. A move you add goes after one
solution is chosen and before `chosen_network.save`. Assign every
returned network back to `bundle_network`.

The stock script does this:

1. `available_network.load()`.
2. `chosen_network.end_all_segments_in_nodes` gives a free end a node.
3. Collect `instance_name` for every instance with `item_type` `"node"`.
   `chosen_network.ensure_nodes_exist` returns the names the available
   network does not contain.
4. The stock script sprouts each missing node. An empty network parks
   it at the origin. Otherwise it is a straight segment, 6 to 18 units
   long, at a random angle, off the first existing node.
   `bundle_network_utils.new_node` appends the node and does not add
   the segment. The script appends `{segment_id, location_at_end_a,
   location_at_end_b, spline_control_points: []}`. Ask before you
   replace that sprout with a raise.
5. `chosen_network.calculate_possible_sub_networks` finds routes that
   touch every required node. When more than one route comes back and
   I named a stable id, `chosen_network.find_network_with` keeps the
   routes that contain `preferred_segment_ids` or `preferred_node_ids`.
   Leave those lists empty unless I named those ids. An empty pair
   matches nothing, so do not call `find_network_with` with both lists
   empty. Exactly one solution remains, or the script raises. That
   dict is `bundle_network`.

A group with a backshell is clocked toward its hop. `clock_backshell`
already moves that node by the connector mate, so this group does not
also call `move_node` with `3d-mate`.

```python
bundle_network = bundle_network_utils.clock_backshell(
    bundle_network, connector_group
)
```

A group with no backshell keeps the mate on the available-network
point. `node_id` is `{connector_group}.node`.

```python
bundle_network = bundle_network_utils.move_node(
    bundle_network,
    node_id,
    bundle_network_utils.output_offset(instance, "3d-mate"),
)
```

```python
chosen_network.save(bundle_network)
flattened_network.derive(bundle_network)
```

The stock script calls `derive` here so the flat drawing exists. Remove
that call when the project does not need the drawing.

Pass `towards_node` as a node id when the connector has more than one
hop. The arguments are on `docs/commands/_bundle_network_utils.md`.

A move those two calls do not make still goes through one Harnice
function, after the single solution exists and before `save`.

```python
bundle_network = bundle_network_utils.move_node(
    bundle_network, node_id, direction=direction
)
```


## Cables

A conductor may arrive from the system with `cable_group`, `mpn`,
`lib_repo`, `lib_subpath`, and `cable_identifier` already set. That
recommendation is optional. A blank `mpn`, `lib_repo`, or
`cable_identifier` is a warning, and that conductor is skipped.

For each usable recommendation, `cable_utils.prepare_for_conductor_assign`
clears the system fields on that conductor. `cable_utils.new_cable`
runs once per `cable_group`, with the group name, mpn, library repo,
and library subpath. `cable_utils.assign_conductor_to_cable` then
takes the conductor instance name, the cable instance name, and the
`cable_identifier` of one conductor inside that cable. A `ValueError`
from a stale recommendation is a warning.

A cable the user names, with no system recommendation, is the same two
calls. `cable_name` and `conductor_name` are the instance names they
gave.

```python
cable_utils.new_cable(cable_name, mpn, lib_repo, lib_subpath)
cable_utils.assign_conductor_to_cable(
    conductor_name, cable_name, cable_identifier
)
```

`cable_utils.map_cables_and_conductors_to_segments()` runs after the
assignments. It routes each conductor between its end nodes and lays
each cable on the segments its conductors share.

`cable_utils.calculate_bundle_diameter` then runs once per instance
whose `item_type` is `"segment"`, passed that instance's name.


## BOM, notes, and drawings

Set `bom_line_number` to `True` on each `harness_connector`, `cable`,
and `backshell`, then `instances_list.assign_bom_line_numbers()`.

`note_utils.make_rev_history_notes` runs for the revision-history row
whose rev is this revision. `note_utils.get_lib_build_notes` returns
the notes stored on a pulled part. `note_utils.new_note` adds a shop instruction the user asked for. A
note with no affected instances is allowed.

```python
note_utils.new_note(
    "build_note",
    text,
    affectedinstances=[instance_name],
)
```

`note_utils.combine_notes` merges two notes whose text the user says
is the same fact. `note_utils.assign_buildnote_numbers()` runs after
the notes exist.

The formboard takes two instance lists. Both start from
`harness_connector`, `backshell`, `segment`, `node`, and `origin`.
The overview list also gets `note_utils.make_part_name_flagnote` for
each connector. The detail list also gets `make_bom_flagnote` and
`make_part_name_flagnote` for each connector and backshell, plus
`make_buildnote_flagnote` or `make_rev_change_flagnote` when that
note's affected instances include the part. Parse note rows with
`note_utils.parse_note_instance` before that test. The last argument
of each flagnote maker is the output CSYS name on that part
(`flagnote-1`, `flagnote-2`, …). The maker returns a dict for the
formboard list. It does not write `instances.tsv`.

`build_utils.run_macro` takes the macro MPN, the library subpath, and
the library repo, then keyword arguments. Harness macros use
`"library/macros/harness_artifacts"` and
`https://github.com/harnice/harnice-general-library`. The stock script
calls these so the drawings exist. Remove a call the project does not
need:

- `bom_exporter_bottom_up`, artifact `bom-1`
- `tooling_list_exporter`, artifact `tool_list-1`
- `standard_harnice_formboard`, artifact `formboard-overview`,
  `dimension=0`, `scale` of sheet A (stock `0.25`), and the overview
  instance list
- `standard_harnice_formboard`, artifact `formboard-detail`, `scale`
  of sheet C (stock `1`), and the detail instance list
- `trace_layout_visualizer`, artifact `conductor_layout-1`,
  `trace_item_types=["conductor"]`, scale A
- `trace_layout_visualizer`, artifact `cable_layout-1`,
  `trace_item_types=["cable"]`, scale A
- `circuit_visualizer`, artifact `circuitviz-1`,
  `input_instances=instances_list.read()`
- `revision_history_table`, artifact `revhistory-1`
- `build_notes_table`, artifact `build_notes_table-1`, and the
  instances whose `item_type` is `"note"` and `note_type` is
  `"build_note"`
- `wirelist_exporter`, artifact `wirelist-1`,
  `input_instances=instances_list.read()`
- `harness_step_builder`, artifact `harness-step-1`,
  `chosen_network=bundle_network`,
  `input_instances=instances_list.read()`
- `pdf_generator`, artifact `pdf_drawing-1`

`page_setup` is a dict in this script, not a file. The stock drawing
is three letter pages, overview, to-from table, and channel map, each
anchored `bottom-right` on title block `harnice_tblock` from
`library/titleblocks/` in the general library. `text_replacements`
fills `tblock-key-pagedesc`, `tblock-key-desc`, `tblock-key-pn`,
`tblock-key-drawnby`, `tblock-key-rev`, `tblock-key-scale`, and
`tblock-key-sheet`. Description, part number, drawn-by, and rev come
from `rev_history.info` and `state.partnumber`. Sheet is `"autosheet"`.
The scale on each page is the scale of the master on that page. Edit
`page_setup` here. The PDF editor does not own that list.

Do not call `subsystem_symbol`. That macro is the system script.


## Run the build

Do not run `build.py`. From the harness revision folder:

    harnice -b

If `harnice` is not on PATH, and you already cloned
https://github.com/harnice/harnice-cli, stay in the revision folder and run:

    python3 /path/to/harnice-cli/src/harnice/__main__.py -b

If you can run that command, run it. A traceback is the review: fix
`build.py` and run it again.

If you cannot run a command, give me the script and tell me to click
Build and paste the error text back. Do not invent an exit code.


## Done

- [ ] The revision is a harness, and you edited that `build.py`
- [ ] You did not map channels, write a device signals list, or write a part family
- [ ] Connector part numbers stayed on the system's chooser, unless I named a local part rule that runs before `library_utils.pull`
- [ ] A stock section you removed is one the project does not need, and `harnice -b` still succeeds
- [ ] Ordinary Python did the logic and did not modify project files
- [ ] Harnice functions produced the chosen network
- [ ] Chosen-network moves are assigned back and run before `chosen_network.save`
- [ ] A group with a backshell uses `clock_backshell` and does not also `move_node` by `3d-mate`
- [ ] A connector with no backshell uses `move_node` and `output_offset(..., "3d-mate")`
- [ ] Every Harnice call is on a page this skill lists, with arguments from that page
- [ ] Decisions I made are comments in the file
- [ ] An agent build exited 0. A chatbot told me to click Build and paste the errors back
