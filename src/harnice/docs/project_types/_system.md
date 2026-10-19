# Systems
A collection of devices and harnesses that satisfies a set of functionality requirements for some external purpose. 

---

## How system data is stored

System data is stored in the following file formats.

??? info "Instances List"

    {% include-markdown "interacting_with_data/_instances_lists.md" %}

??? info "Library Import History"

    {% include-markdown "interacting_with_data/_library_history.md" %}

??? info "Channel Map"

    {% include-markdown "interacting_with_data/_channel_maps.md" %}

??? info "Circuits List"

    {% include-markdown "interacting_with_data/_circuits_lists.md" %}

??? info "Passthrough Map"

    {% include-markdown "interacting_with_data/_passthrough_maps.md" %}

??? info "Netlist"

    {% include-markdown "interacting_with_data/_netlists.md" %}

??? info "Post-Harness Instances List"

    {% include-markdown "interacting_with_data/_post_harness_instances_lists.md" %}

??? info "Signals List"

    {% include-markdown "interacting_with_data/_signals_lists.md" %}


---

## Building a system

1. Harnice runs the build instructions if it's found in the system directory.

1. The system is validated and verified.

1. The external ICD is compiled from external-interface flags (after build instructions).

1. The system block diagram SVG is updated from placed-instance symbol files under `instance_data/` (so device/subsystem symbol edits are picked up), including derived channel/circuit trace overlays based on the built system.

1. PDF drawings: call `run_macro("pdf_generator", …, page_setup=…)` in build instructions after other macros that write masters.

The `subsystem_symbol` macro runs in build instructions, so it reads the ICD from the previous build and runs device signals-list / symbol-pin verification against it. After ICD changes, build twice. That lag is expected.


---

## Channel and passthrough mapping

After Harnice exports a BOM and system connector list from your block diagram SVG, it seeds a **channel map**—one row per channel endpoint, including both faces of a passthrough. Your **build instructions** then declare which endpoints carry the same logical signal (`map()`), and (when a patch must cross a two-face device) which **passthrough routes** each cross-harness link uses. That process is what turns diagram connectivity into a **circuits list** and downstream harness instances.

??? info "Channel map file format"

    {% include-markdown "interacting_with_data/_channel_maps.md" %}

??? info "Passthrough map file format"

    {% include-markdown "interacting_with_data/_passthrough_maps.md" %}

### Where mapping runs in a system build

1. **Before build instructions:** `channel_map.new()` runs automatically during `system.build()`. It reads the system connector list and each device's signals list, and writes one channel-map row per channel endpoint `(device_refdes, channel_id[, repeat_channel_id])`.

1. **In build instructions (typical order):** map channels → `channel_map.compile_hierarchical()` → `passthrough_map.new()` → optional `route()` hops → `passthrough_map.resolve()` → build the circuits list.

1. **After mapping:** `circuits_list.new()` expands every mapped channel pair (and its passthrough path) into individual conductor circuits. A multi-channel junction row (no `to_*` partner) becomes one circuit per signal: from is `from_channel.signal`, to is `mcj.signal`. Signal names come from the first channel type seen on that junction id.

The default system build instructions follow this pattern:

```python
# 2-tuple when the channel has one endpoint; 3-tuple when it has two
# channel_map.map(("MIC1", "out1"), ("PRE1", "in1"))
# channel_map.map(("MIC1", "out1"), ("X1", "ch0", "A"))

channel_map.map_unmapped_compatibles_alphabetically()
channel_map.compile_hierarchical()

passthrough_map.new()

# optional: passthrough_map.route("MIC1", "out1", "X1", intended_channel_id="ch0", repeat_channel_id="A")
passthrough_map.resolve()

circuits_list.new()
```

### Concepts

**Channel.** A channel is one logical link on a device—audio in, power, differential pair, etc. Its **channel type** (from the channel-types library) defines required signals and which other types it may mate with. See channel types documentation for compatibility rules.

**Channel endpoint.** One complete instance of a channel on one connector (`channel_id` + `channel_type` + `connector_id`, plus `repeat_channel_id` when that channel has two faces).

**Patch.** A pair of channel endpoints created by `channel_map.map()`. Stored in the channel map.

**Passthrough.** A channel with exactly two channel endpoints on the same device. Identified by `(device_refdes, channel_id)` plus a `repeat_channel_id` for each face.

**Mapped channel.** A mapped channel is a connection from one channel on a device to another. They define the functional requirement of any harness, and form the basis of which circuits are generated and where they go. The channel map is the list of mapped channels (and any still-unmapped channels).

**Group of connected harnesses (`group_of_connected_harnesses`).** Harness wires in your block diagram define equivalence classes of harnesses: any harnesses linked through a passthrough share the same `group_of_connected_harnesses` label on the system connector list, copied onto each channel-map row. Unmated terminating connectors are in no group. An unmated passthrough face still belongs to the group of its other, mated face. Automatic channel mapping only considers pairs **within the same group of connected harnesses**—channels in different groups are never auto-mapped together. Manual `map()` and `route()` also require the same group.

### Channel mapping in detail

#### Seeding: `channel_map.new()`

For every row in the system connector list where `device_refdes` is set, Harnice loads that device's signals list. For each channel endpoint on that connector, it appends a row with:

- `group_of_connected_harnesses` — copied from the matching system connector list row

- `from_device_refdes`, `from_device_channel_id`, `from_repeat_channel_id`, `from_channel_type` — the channel endpoint (`from_repeat_channel_id` is set when that channel has two faces)

- `to_*` columns empty until mapped

It also creates an empty **mapped channels set** TSV used to prevent double-mapping.

#### Manual mapping: `channel_map.map(from_key, to_key=None, multi_ch_junction_key="")`

`from_key` and `to_key` are `(device_refdes, channel_id)` when that channel has one endpoint, or `(device_refdes, channel_id, repeat_channel_id)` when it has two. A 3-tuple on a single-instance channel is an error. Dual-map is two `map()` calls to the two repeats of the same passthrough (no passthrough-map row). A patch may end by crossing a device only if that destination face has no harness. Calling `map(from_key, to_key)`:

1. Finds the row whose `from_*` columns match `from_key` and copies `to_device_refdes`, `to_device_channel_id`, `to_repeat_channel_id`, and `to_channel_type` from the row that matches `to_key`.

1. Removes the separate "to-only" row for `to_key` (each physical endpoint appears once as a `from_*` row; mapping is directed).

1. Records both keys in the mapped channels set and writes a `manual_map_channel_python_equiv` cell you can copy back into build instructions.

To connect several channels to each other on one multi-channel junction, pass `multi_ch_junction_key="jcn1"` instead of `to_key`. That consumes `from_key` and writes `jcn1` as `multi_ch_junction_id` on the same row. Several rows can share that id without pairing to a single partner. A channel may join only if its type is, or is compatible with, every other member already on that junction (`chtype.is_or_is_compatible_with`, either direction). Automatic mapping never attaches leftover channels to a multi-channel junction. On the block-diagram channel overlay, traces of the same id follow the harness to the T (one arm per member). The circuit overlay does the same per signal (`from_channel.signal` → `mcj.signal`), using the first channel type seen on that id for signal names. A junction dot is placed where that net arrives on three or more arms.

Raises `ValueError` if either key was already mapped, if the endpoints are not in the same group, if a required `to_key` row is missing, if both `to_key` and `multi_ch_junction_key` are passed, or if the joining channel is not compatible with every existing junction member.

#### Force mapping: `channel_map.force(from_key, to_key)`

Maps one endpoint to another with the same group and face rules as `map()`, and does not check channel-type compatibility. `map()` itself is unchanged. When both channel types list the same signal names, circuits compile by those names. When the names differ, the patch stays pending until `circuits_list.force(from_key, signal_pairs, drop=())` pairs every from-side name and explicitly drops every unused to-side name. The circuit keeps the from-side name; the to-side cavity is looked up under the paired name. A from-side signal cannot be dropped. `circuits_list.new()` raises if any pending patch is still waiting.

#### Automatic mapping: `channel_map.map_unmapped_compatibles_alphabetically()`

For each `group_of_connected_harnesses`, rows are sorted alphabetically by device refdes and channel id. Channels with more than one endpoint (passthroughs) are skipped, even if nothing else is left. For each remaining row whose `from_key` is not yet mapped, Harnice scans later rows in the same group of connected harnesses and maps to the **first** candidate whose channel types are mutually compatible: either `to_type` is in `chtype.compatibles(from_type)` or `from_type` is in `chtype.compatibles(to_type)`. This is deterministic but not unique—use manual `channel_map.map()` first for anything that must not follow alphabetical pairing.

#### Hierarchical channel map: `channel_map.compile_hierarchical()`

Writes `maps/hierarchical_channel_map.tsv` with the same columns as the channel map. The sheet starts with this system's channel map, then appends the channel map imported with each child subsystem, and repeats that walk through every nested subsystem. Those imported channel maps are the source of truth — this does not rebuild a subsystem's mappings.

Rows from a subsystem prefix that subsystem's instance name onto `group_of_connected_harnesses`, `from_device_refdes`, `to_device_refdes`, `multi_ch_junction_id`, `chain_of_connectors`, and `chain_of_harnesses`. Each entry in a list is prefixed (`AMP.H1+AMP.H2`, `AMP.MIC3.J1;AMP.X1.A`). Nested subsystems accumulate prefixes (`AMP.PRE.MIC1`). `manual_map_channel_python_equiv` is left blank. Channel ids, repeat ids, and channel types are copied unchanged. This system's own rows are not prefixed. Call it after `map_unmapped_compatibles_alphabetically()`. It snapshots the channel map as it stands at the call.

#### Channel-map columns filled later

| Column | When it is filled |

|--------|-------------------|

| `chain_of_connectors`, `chain_of_harnesses` | Via `passthrough_map.resolve()` from the passthrough path |

| `multi_ch_junction_id` | When you pass `multi_ch_junction_key=` to `channel_map.map()`. Copied onto circuits (`from_channel.signal` → `mcj.signal`) |

A row is **fully mapped** when `to_device_refdes` and `to_device_channel_id` are set. Passthrough routing requires fully mapped rows whose endpoints sit on **different** harnesses.

### Passthrough routing in detail

Channel mapping answers *which device channels are the same signal*. The **passthrough map** lists every unused passthrough channel; **`passthrough_map.resolve()`** chooses which passthroughs carry each mapped signal and writes `chain_of_connectors` / `chain_of_harnesses` on the channel map. Dual-map consumes both faces as patch ends and does not write a passthrough-map row.

#### `passthrough_map.new()`

Reads the system BOM, loads each device's signals list, and writes one row per unused passthrough channel. Builds the routing context used by `route()` / `resolve()`. Passthroughs already consumed as dual-map ends are omitted.

#### `passthrough_map.route()`

Pins a mapped channel through a chosen passthrough (optional channel id and `repeat_channel_id` for the face the patch arrives on). Call after `new()` and before `resolve()` for required hops. The passthrough must be in the same group as the mapped channel. Routing a channel whose faces are already map-consumed is an error.

#### `passthrough_map.resolve()`

Completes passthrough routing for each mapped channel (optional user `route()` waypoints first). Writes `satisfaction` on the passthrough map and fills `chain_of_connectors` / `chain_of_harnesses` on the channel map. Connector tokens are `refdes.connector` (e.g. `MIC3.J1;X1.A;X1.B;PREAMP1.J1`); harness names are refdes per hop (`H1;H2`).

### Practical tips

- Map critical channel pairs manually **before** `map_unmapped_compatibles_alphabetically()`.

- Use `route()` for required passthrough hops; let `resolve()` fill the rest.

- Both endpoints of a `map()`, and any `route()` hop, must be in the same group of connected harnesses.


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")                 |-- yourpn/
                                                     |-- earlier revs/
fileio.path("revision history")                      |-- revhistory.csv
fileio.dirpath("rev_directory")                      L-- your rev/
fileio.path("build instructions")                        |-- build.py
fileio.path("instances list")                            |-- instances.tsv
fileio.path("block diagram")                             |-- blockdiagram.svg
fileio.path("icd")                                       |-- signals.tsv
fileio.dirpath("instance_data")                          |-- instance_data/
fileio.dirpath("harnesses")                              |-- harnesses/
fileio.dirpath("lists")                                  |-- lists/
fileio.path("bom")                                       |   |-- bom.tsv
fileio.path("circuits list")                             |   |-- circuits.tsv
fileio.path("post harness instances list")               |   |-- instances_w_hrns.tsv
fileio.path("system connector list")                     |   |-- connectors.tsv
fileio.path("mapped channels set")                       |   |-- mapped.tsv
fileio.path("library history")                           |   L-- libhist.tsv
fileio.dirpath("maps")                                   L-- maps/
fileio.path("channel map")                                   |-- channels.tsv
fileio.path("hierarchical channel map")                      |-- hierarchical_channel_map.tsv
fileio.path("passthrough map")                               |-- passthrough.tsv
fileio.path("passthrough routing context")                   |-- context.tsv
fileio.path("pending forced channels")                       |-- forced_channels_pending.tsv
fileio.path("forced signal map")                             L-- forced_signals.tsv
```


---

## Instructions for child harnesses

A system can define functions such as ``connector_chooser`` and ``m85049_chooser`` in its build instructions. Child harnesses call them after they import from this revision:

```python
build_utils.run_instruction_from_relative(
    "connector_chooser",
    system_pn,
    system_lib_repo,
    system_lib_subpath,
    system_rev,
)
build_utils.run_instruction_from_relative(
    "m85049_chooser",
    system_pn,
    system_lib_repo,
    system_lib_subpath,
    system_rev,
)
```

That is how system-level **behavior** (mating-connector policy, per-position assignments) stays on the parent instead of being copy-pasted into every harness. A missing file or function raises. It runs in the **harness** working directory. It is not a macro: no instance folder, no library-history row. Only the function (plus any remaining imports and literal data) is loaded from the system file — Harnice list, utility, and channel-type modules are already in the namespace. The system's own channel-mapping and macros are not re-run.

Use ``state.harness`` inside the function for one harness position. When the system revision changes, the next harness rebuild picks up the new rules.


---

## How to define a new system

1. Make a folder for the part number of your system somewhere on your computer. Click **Build** in Harnice, which will generate an example system that you can then edit.

    ??? info "Building a project"

        {% include-markdown "fragments/how-to-build.md" %}

1. Open that system in Harnice and edit the **block diagram**. Place devices from your library, draw harness wires between connectors, then save.

1. Click **Build** often as you refine the diagram and build instructions.


---

## Designing your block diagram

Device symbols are placed in the system block diagram SVG from the Harnice console (**Place device**). A two-face passthrough is a device.

Harness wires represent entire harnesses between connectors. The diagram is agnostic to the individual conductors, channels, or signals of a harness—only that certain connectors are connected via a harness.

To join two harnesses through a passthrough, place a two-face device and route harness wires to its faces. Set library pull fields on the placed symbol (same attributes used when placing from the library):

1. `MPN` — part number of the device

2. `lib_repo` — traceable path to the repo that contains the device

3. `lib_subpath` — path between the library root and the part number, if any (for example, if the part lives at `{library_root}/devices/audio/tascam-db25/rev1/`, use `devices/audio/`)

4. `rev` — revision to use in this system (optional)


An **external interface flag** (red triangle) marks a connector that appears on the system's external ICD (`fileio.path("icd")`). Place it on a harness mating connector (yellow dot) or on a device connector that has no harness mated to it. It cannot be placed on a device connector that already has a harness. On build, flags on harness-mated passthrough connectors fill the ICD from circuits; flags on unmated device connectors copy that connector's rows from the device's signals list.

### Block diagram symbols

Default system build instructions run the `subsystem_symbol` macro once (`artifact_id="subsystem-symbol-1"`, `scale=0.1`). Each additional `run_macro` call of that MPN is another imported instance; open it from **instance data**. The editor is the same drawing tools as a device symbol, plus **System diagram**, which drops the current system block diagram contents (not trace overlays) as a primitive. `scale` sets that primitive's scale; a later build updates the scale of a diagram already on the symbol and leaves its position. The macro seeds a blank SVG if none exists and does not otherwise redraw a symbol you have already drawn.

On first seed (and on later builds when pins are still missing), the macro places one connector pin per unique `connector_name` in the system ICD (`fileio.path("icd")`). It also runs device signals-list checks against that ICD (the system's signals list). Pin mismatches vs the ICD print a warning and do not fail the build; missing pins are still appended. The ICD is compiled *after* build instructions, so this macro always reads the ICD from the **previous** build. After you add, remove, or rename external-interface flags, build twice: the first build writes the ICD, and the second build updates symbol pins and re-checks from it. That one-build lag is expected. If no previous ICD exists yet, verification is skipped.
