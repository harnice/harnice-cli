# Macros

---

## What is a macro?

A **macro** is a revision-controlled library item: a small project that runs inside a larger one.

It is Python, and it can do anything Python can do — read your instances list, write a drawing, pull other library parts, even call another macro. That is not what makes it a macro. What makes it a macro is that each call is a **full instance** of that library item:

- The script lives in a library under its own manufacturer part number (MPN), with a `{mpn}-revision_history.tsv` and `revN` folders, the same way a connector or titleblock does.
- `build_utils.run_macro()` **pulls** a specific revision of that MPN into your current project, then executes it.
- Each call needs a unique **`artifact_id`**. That string is the **instance name** for this macro run — the same role as `J1` when you place a connector MPN twice. Library history records it as `instance_name`, and files land under `instance_data/macro/{artifact_id}/` with their **own file structure** and nested `instance_data/` if needed.
- You can call the same MPN many times in one build: same MPN, different `artifact_id` and kwargs (two formboards, two PDF drawings, two subsystem symbols).

==A macro is not a function you import. It is a small project running inside a bigger project.==

That is why macros are a first-class project type, listed next to harnesses and systems, even though you almost always *run* them from another project's build instructions rather than building a macro folder on its own.

In the rest of this page, **`artifact_id`** is the API name for that instance; **instance** is used when talking about library history or `instance_data/`.


---

## Why macros are not normal functions

Three ways to run extra Python during a build look similar and are not the same:

| | Normal Python module / function | Instruction from a relative | Macro |
|---|---|---|---|
| Where the code lives | Harnice source, or a script you wrote in this project | A function on another project's build instructions (e.g. ``connector_chooser``, ``m85049_chooser``) | A library MPN: `{lib}/macros/…/{mpn}/revN/{mpn}.py` |
| How you call it | `cable_utils.new_cable(...)` | `build_utils.run_instruction_from_relative(function_name, relative_mpn, relative_repo, relative_subpath, relative_rev)` | `build_utils.run_macro(...)` |
| Revision control of the code | Whatever git commit your Harnice install is on | Whatever revision that *other project* happens to be | The macro's own `{mpn}-revision_history.tsv`; you can pin `lib_rev_used_here` |
| Local files | None of its own. It reads and writes the *caller's* files | None of its own. It runs in the caller's working directory | An instance folder with a `macro_file_structure()`, outputs, and optionally nested instances |
| Library history | Not recorded as an import | Not recorded as an import | One library-history row per `artifact_id` |
| Multiple slightly different runs | You write a loop or pass different arguments | One function; branch on ``state.harness`` | Same MPN, different `artifact_id` and kwargs — two formboards, two PDF drawings, two subsystem symbols |

**Normal functions** (`cable_utils`, `note_utils`, `instances_list.modify`, …) are the language of a project type. They do not come with a folder, a revision, or an instance name.

**Instructions from a relative** (`build_utils.run_instruction_from_relative`) are how one project can call a function defined on another — for example a harness calling ``connector_chooser`` or ``m85049_chooser`` on its parent system. That function lives in the relative revision's build instructions. It is not pulled from a library, it does not get `instance_data/macro/…`, and it does not have its own revision history. Default harness build rules call those functions after the system import. Extra kwargs are passed only if the function accepts them.

**Macros** are the reusable, versioned, instantiable version of that idea. If you want a rule or an export that many projects will call, that you will revise over time, and that needs its own outputs on disk, write a macro.


---

## How to call a macro

From build instructions (or any other Python Harnice is already running):

```python
build_utils.run_macro(
    "standard_harnice_formboard",              # MPN of the macro in the library
    "macros/harness_artifacts",        # path from that library root to the MPN folder
    "https://github.com/harnice/harnice-general-library",      # library repo URL from library_locations.csv
    artifact_id="formboard-overview",          # unique instance name for *this* run
    scale=0.25,                                # extra kwargs become globals inside the macro
    input_instances=formboard_overview_instances,
)
```

**Required arguments**

- `macro_part_number` — the MPN folder name in the library (`standard_harnice_formboard`, `bom_table_bottom_up`, …).
- `lib_subpath` — directories between the library root and the MPN folder. Shipped Harnice macros use `macros/drawing_artifacts`, `macros/harness_artifacts`, `macros/system_artifacts`, or `macros/device_artifacts`.
- `lib_repo` — the repo URL as listed in `library_locations.csv`, or `"local"` for a project-local library.
- `artifact_id` — the instance name of this run. Must be unique in the current project's library history unless you pass `rerun=True`.

**Optional arguments**

- `base_directory` — root of this instance's file structure. Defaults to `instance_data/macro/{artifact_id}`. Nested macros (the formboard calling `basic_segment_generator` for each segment) pass a subdirectory so the child lives inside the parent instance.
- `rerun` — if `True`, allow the same `artifact_id` again and do not append a second library-history row.
- `**kwargs` — anything else. `run_macro` injects these as **global variables** in the macro script. Macros do not declare a formal function signature; they read `artifact_id`, `base_directory`, `scale`, `input_instances`, and so on from globals. Comment the expected kwargs at the top of the macro instead of defining them.

`run_macro` raises `ValueError` if `artifact_id`, `macro_part_number`, or `lib_repo` is missing, or if that `artifact_id` is already in library history and `rerun` is false. The full signature is on [Build utilities](../commands/_build_utils.md).


---

## What happens when you call one

`build_utils.run_macro()` does this, in order:

1. **Refuse a duplicate `artifact_id`** unless `rerun=True`.
2. **Create the instance directory** (`instance_data/macro/{artifact_id}/` unless you overrode `base_directory`).
3. **`library_utils.pull()` the macro** as `item_type="macro"`, `instance_name=artifact_id`. That copies the chosen library revision into `lib/`, copies the `.py` (and any other editable files) to the instance root if they are not already there, and records the import in library history.
4. **Execute `{mpn}.py` with `runpy`**, passing `artifact_id`, `base_directory`, `artifact_path`, and your kwargs as globals.

From inside the macro, the script defines its own `macro_file_structure()` and its own `path()` / `dirpath()` helpers that wrap `fileio` with that structure and `base_directory`. Outputs land in the instance folder. Nested pulls (flagnote bubbles on a BOM table, titleblocks on a PDF, a child `basic_segment_generator` per segment) land under that instance's `instance_data/`.

After a typical run the caller looks like this:

```
yourpn/
└── rev1/
    └── instance_data/
        └── macro/
            └── formboard-overview/                 # artifact_id
                ├── lib/       # exact library revision that ran
                │   └── rev1/
                ├── standard_harnice_formboard.py   # editable copy that actually executed
                ├── {pn-rev}-formboard-overview-master.svg
                └── instance_data/                  # nested instances this macro created
                    ├── flagnote/
                    └── macro/                      # child macros, e.g. per-segment drawings
```

The parent project type (harness, system, …) never has to know the macro's filenames. It only has to know the MPN, the library location, and the `artifact_id`.


---

## Where macros live in a library

Shipped Harnice macros are in the [general library](https://github.com/harnice/harnice-general-library) under `macros/`, grouped by what they produce:

```
macros/
├── device_artifacts/      # macros that write a device body
├── drawing_artifacts/     # sheets and tables any project type can use (BOM, PDF, revision history, …)
├── harness_artifacts/     # macros that write harness deliverables (formboards, wirelists, STEP, …)
└── system_artifacts/      # macros that write system deliverables (subsystem symbol, …)
```

Each MPN is a library part:

```
macros/drawing_artifacts/bom_table_bottom_up/
├── bom_table_bottom_up-revision_history.tsv
└── rev1/
    └── bom_table_bottom_up.py
```

That is the same shape as a connector or a titleblock: part-number folder, revision history, revision folder, files. Rolling a macro revision is the same form/fit/function decision as rolling a part revision. Callers that omit `lib_rev_used_here` get the latest; callers that pin a rev keep getting that rev. See [Libraries](../getting_started/libraries.md).


---

## What macros do

Every shipped Harnice macro reads design data (typically the instances list) and writes files under `instance_data/macro/{artifact_id}/`: BOMs, formboards, PDF sheets, analysis drawings, tables, and similar deliverables. Default harness build instructions call a stack of them at the end of the script; default system build instructions call `subsystem_symbol`, `physical_model_drawing`, `block-diagram-svg-exporter`, `bom_table_bottom_up`, and `pdf_generator`.

You can write any rule you want in Python, save it to a library, and call it from build instructions.


---

## New macros: start here

Copy this template into a new `{mpn}/rev1/{mpn}.py` (or into an AI tool) and fill it in. Arguments are **not** defined in the macro — the caller injects them via `runpy`.

```python
# import your modules here

# describe your args here. comment them out and do not officially define because they are called via runpy,
# for example, the caller build instructions should define the arguments like this:
# build_utils.run_macro(
#    "standard_harnice_formboard",
#    "macros/harness_artifacts",
#    "https://github.com/harnice/harnice-general-library",
#    artifact_id="formboard-overview",
#    scale=scales.get("A"),
#    input_instances=formboard_overview_instances,
# )

# artifact_id is injected by run_macro: unique instance name for *this* run
# (like J1 for a connector), not the library MPN. Files land under
# instance_data/macro/{artifact_id}/.
# artifact_id = "example_macro"

# =============== PATHS ===================================================================================
# this function does not need to be called in your macro, just by the default functions below.
# add your file structure inside here: keys are filenames, values are human-readable references. keys with contents are folder names.
# you can also add variables to the filenames, like example_variable_tofu. if you don't need to do this, you can delete references to tofu in this guide.
def macro_file_structure(example_variable_tofu=None):
    # define the dictionary of the file structure of this macro
    return {
        f"{artifact_id}-example.txt": "text file",
        "folder": {
            f"{artifact_id}-{example_variable_tofu}.csv": "csv file",
        }
    }


# this runs automatically and is used to assign a default base directory if it is not called by the caller.
if base_directory == None:  # path between cwd and the file structure for this macro
    base_directory = os.path.join("instance_data", "macro", artifact_id)

# call this in your script to get the path to a file in this macro. it references logic from fileio but passes in the structure from this macro.
def path(target_value, example_variable_tofu=None):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
        example_variable_tofu=example_variable_tofu,
        #
    )


def dirpath(target_value):
    # target_value = None will return the root of this macro
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )

# don't forget to make the directories you've defined above.
os.makedirs(
    dirpath("folder"),
    exist_ok=True,
)

# macro initialization complete. write the rest of the macro logic here. there are no remaining required functions to call.
# ==========================================================================================================
```

Add a `{mpn}-revision_history.tsv` next to the rev folder, put the library on `library_locations.csv`, and call it with `run_macro`.


---

## Shipped macros in the Harnice library

These are the macros that ship in the general library. Unless noted, `lib_repo` is `https://github.com/harnice/harnice-general-library`. Each one writes under `instance_data/macro/{artifact_id}/`.

| MPN | Library folder | Who calls it by default |
|---|---|---|
| `bom_table_bottom_up` | `macros/drawing_artifacts` | default harness and system build (`artifact_id="bom-1"`) |
| `tooling_list_exporter` | `macros/drawing_artifacts` | default harness build (`artifact_id="tool_list-1"`) |
| `standard_harnice_formboard` | `macros/harness_artifacts` | default harness build, twice (overview + detail) |
| `basic_segment_generator` | `macros/harness_artifacts` | `standard_harnice_formboard`, once per segment |
| `flying_lead_generator` | `macros/harness_artifacts` | `standard_harnice_formboard`, for each segment that ends at a `flying leads` connector |
| `trace_layout_visualizer` | `macros/harness_artifacts` | default harness build, twice (conductors + cables) |
| `circuit_visualizer` | `macros/harness_artifacts` | default harness build (`artifact_id="circuitviz-1"`) |
| `revision_history_table` | `macros/drawing_artifacts` | default harness build (`artifact_id="revhistory-1"`) |
| `build_notes_table` | `macros/drawing_artifacts` | default harness build (`artifact_id="build_notes_table-1"`) |
| `wirelist_exporter` | `macros/harness_artifacts` | default harness build (`artifact_id="wirelist-1"`) |
| `harness_step_builder` | `macros/harness_artifacts` | default harness build (`artifact_id="harness-step-1"`) |
| `pdf_generator` | `macros/drawing_artifacts` | default harness and system build (`artifact_id="pdf_drawing-1"`) |
| `subsystem_symbol` | `macros/system_artifacts` | default system build (`artifact_id="subsystem-symbol-1"`) |
| `physical_model_drawing` | `macros/system_artifacts` | default system build (`artifact_id="physical-1"`, before `pdf_generator`) |
| `build_rectangular_physical_model` | `macros/device_artifacts` | device build, when you want a rectangular body (`artifact_id="body-1"`) |
| `build_rackmount_physical_model` | `macros/device_artifacts` | device build, when you want a rack chassis (`artifact_id="body-1"`) |
| `build_rackmount_enclosure` | `macros/device_artifacts` | device build, when you want a rack enclosure (`artifact_id="body-1"`) |
| `build_physical_model_from_step` | `macros/device_artifacts` | device build, when the body is an existing STEP file (`artifact_id="body-1"`) |



### `bom_table_bottom_up`

Builds a bill of materials table in any project type. Reads the instances list and groups every instance that has a `bom_line_number` by that number. It does not check the project type: whatever is in the `bom_line_number` column is what goes on the BOM. Stops with an error if no instance has a line number.

Assign the line numbers first. Mark the instances that belong on the BOM with `bom_line_number` `True`, then call `instances_list.assign_bom_line_numbers()`, which gives every instance with the same MPN the same number.

- The default harness build marks `harness_connector`, `cable`, and `backshell` instances.
- The default system build marks `device`, `harness`, and `system` instances. Circuits also carry an MPN (the recommended cable), but they belong on the harness BOMs, so they are not marked.

**The table:**

- Each BOM line gets a total row: a numbered bubble, QTY (every instance on that line), MFG, and MPN.
- Under it, an instance gets its own row only if `per_instance_disclosure` lists it with at least one non-blank value. An arrow marks these rows, their text is italic, and the INSTANCE column shows the instance name. Only the header row is bold.
- Each column header in `per_instance_disclosure` becomes a column. The total row shows the sum of that column when every disclosed value on that line is a number. If any value is blank or not a number, the total stays blank.
- The macro draws the bubble and the arrow itself, straight into the table SVG. It uses no library part and writes no files besides the TSV and the SVG. The SVG table grows **up** from the bottom-right.

**Args:**

- `per_instance_disclosure` — optional. A dict of `{instance_name: {column header: value}}`. Instances not in it get no row of their own. Default `{}`, so only total rows are drawn.

Build the dict in build instructions with a normal loop, then pass it in.

Harness default (cable lengths):

```python
bom_disclosure = {}
for instance in instances_list.read():
    if instance.get("item_type") == "cable" and instance.get("length"):
        bom_disclosure[instance.get("instance_name")] = {
            "Length with margin": float(instance.get("length")) + 12,
        }
```

System default (one configuration field per device; `instances_list.configuration_value` reads one saved answer from `device_configuration`):

```python
bom_disclosure = {}
for instance in instances_list.read():
    bom_disclosure[instance.get("instance_name")] = {
        "IP address": instances_list.configuration_value(instance, "ip_address"),
    }
```

Then: `per_instance_disclosure=bom_disclosure`.

#### Disclosure recipes

The macro never decides what to show. Build instructions build `bom_disclosure` with a normal loop, so a value can come from anything build instructions can read. In a system, a placed device's `instance_name` is its refdes, so the dict is keyed per refdes.

Only instances with a `bom_line_number` appear. Entries for other instances (circuits, connectors in a system) are ignored. Build the dict right before the `run_macro` call so it reads the current instances list.

**Show any instances-list column.** Read the column from the instance row:

```python
bom_disclosure = {}
for instance in instances_list.read():
    bom_disclosure[instance.get("instance_name")] = {
        "Print name": instance.get("print_name"),
        "Library": instance.get("lib_subpath"),
    }
```

**Show a value from a file in `instance_data/`.** A placed device's files are in `instance_data/device/{refdes}/`. Open the file and put the value in the dict. This counts each device's signals from its signals list. `fileio` is always available in build instructions; `os` needs `import os` at the top of the file (the default build instructions already have it).

```python
bom_disclosure = {}
for instance in instances_list.read():
    if instance.get("item_type") != "device":
        continue
    signals_path = os.path.join(
        fileio.dirpath("instance_data"), "device", instance.get("instance_name"), "signals.tsv"
    )
    if os.path.isfile(signals_path):
        bom_disclosure[instance.get("instance_name")] = {
            "Signals": len(fileio.read_tsv(signals_path)),
        }
```

**Do math on a value.** Instances-list cells are text. Convert with `float()` or `int()`, do the math in Python, and put the number in the dict.

- Return a number, not text, when you want a total. The total row sums a column only when every disclosed value on that line is a number. A blank or text value (such as `"30 in"`) leaves the total blank.
- Decimals are rounded to two places in the table and the TSV. Totals print as decimals (`4.0`), even when every value is a whole number.
- The total row only sums. For an average, a maximum, or anything else, work it out in build instructions and put it in a column of its own.
- Skip an instance whose value is blank or does not convert, or `float()` stops the build.

Cable lengths, two ways:

```python
bom_disclosure = {}
for instance in instances_list.read():
    if instance.get("item_type") != "cable" or not instance.get("length"):
        continue
    length = float(instance.get("length"))
    bom_disclosure[instance.get("instance_name")] = {
        "Length + 5% + 12 in": length * 1.05 + 12,
        "Length (ft)": length / 12,
    }
```

Each key is one column, and each column gets its own total.

Distance from origin, from the `3d_translate` column. That cell holds a dict as text (`{'x': …, 'y': …, 'z': …, 'alpha': …, 'beta': …, 'gamma': …}`), so turn it back into a dict with `ast.literal_eval` first. Add `import ast` and `import math` at the top of the file (the default harness build instructions already import `math`).

```python
bom_disclosure = {}
for instance in instances_list.read():
    if not instance.get("3d_translate"):
        continue
    translate = ast.literal_eval(instance.get("3d_translate"))
    bom_disclosure[instance.get("instance_name")] = {
        "Distance From Origin": math.sqrt(
            translate["x"] ** 2 + translate["y"] ** 2 + translate["z"] ** 2
        ),
    }
```

Only instances on the BOM show a row, so this shows a distance only for BOM instances that have a `3d_translate`.

**Writes** (under `instance_data/macro/{artifact_id}/`):

- `{artifact_id}.tsv` — `bom tsv`. One `line` row per BOM line and one `instance` row per disclosed instance (`row_type` column), with one column per disclosure header.
- `{artifact_id}-master.svg` — `bom svg` (picked up later by `pdf_generator`)

Default call: `artifact_id="bom-1"`, before `pdf_generator`.


### `tooling_list_exporter`

Walks the instances list, parses each `lib_tools` cell (`ast.literal_eval` of a list or a single name), and emits a de-duplicated tooling list. Writes an SVG table (one column, header **REQUIRED TOOLING**) and a TSV. If nothing has tools, the TSV is removed so a stale file does not linger.

**Args:** none beyond `artifact_id`.

**Writes:** `{pn-rev}-{artifact_id}.tsv` (`tooling list tsv`), `{pn-rev}-{artifact_id}-master.svg` (`tooling list svg`).

Default call: `artifact_id="tool_list-1"`.


### `standard_harnice_formboard`

Lays harness geometry into a formboard SVG in flattened-network space. Places printable instances (connectors, backshells, segments, flagnotes, …) by coordinate system, draws leader lines for flagnotes, and can draw cable/conductor paths plus a filleted bundle border instead of plotting those item types as symbols.

For each **segment** it calls `basic_segment_generator` as a **child macro**, or `flying_lead_generator` if and only if one of the segment's end nodes has a `harness_connector` whose `mpn` is `flying leads` (that connector has no drawing of its own and is not plotted) (`artifact_id="{this_artifact_id}-{segment_name}"`, `base_directory` inside this instance). Flagnotes are pulled from the library (without recording them again in the parent library history, because the same bubble can appear on overview and detail). Other drawings are copied from the parent project's `instance_data/`.

**Args:**

- `artifact_id` — instance name (`formboard-overview`, `formboard-detail`, …).
- `input_instances` — the rows to plot. Default harness build passes a filtered list: overview gets structure + part-name flagnotes; detail gets structure + BOM bubbles + build-note and rev-change flagnotes.
- `scale` — drawing scale (same numbers as PDF titleblock scales A/B/C).
- `rotation` — optional, degrees (documented on the macro; placement uses flattened-network angles).
- `dimension` — 0–100, opacity of segment length dimensions. Default harness overview passes `0` (hidden); omit for fully opaque (100).
- `trace_path_item_types` — optional list of `item_type`s to draw as paths along the bundle instead of as symbols.
- `flying_lead_splay_angle` — optional, degrees between neighboring conductors on every flying-lead segment (default 10), passed to `flying_lead_generator` as `splay_angle`. Flying-lead segments are drawn before anything is placed, so terminals find their `flying_lead_end` csys. Placement chains are resolved against the full instances list.

**Writes:** `{pn-rev}-{artifact_id}-master.svg` (`output svg`).

Default harness build calls it twice: `formboard-overview` at scale A with `dimension=0`, and `formboard-detail` at scale C.


### `basic_segment_generator`

Draws one segment: a stroked line whose width is the bundle diameter, plus an optional length dimension (arrows, label, units). Not meant to be called from harness build instructions; `standard_harnice_formboard` calls it per segment.

**Args:**

- `instance` — one instances-list row, `item_type` must be `segment`, with `length` and `diameter`. Optional `length_tolerance` and `appearance`.
- `dimension` — 0–100 opacity (default 50 if omitted).
- `dimension_units` — `"in"` (default), `"mm"`, or `"ft"`. Instance length is always inches; the label is converted.
- `scale` — formboard scale, used so dimension text stays a readable size on the sheet.

**Writes:** `{artifact_id}-drawing.svg`.


### `flying_lead_generator`

Draws a segment that ends at a `harness_connector` whose `mpn` is `flying leads`; `standard_harnice_formboard` uses it for exactly those segments, instead of `basic_segment_generator`. Every conductor on the segment, including each conductor inside every cable on it, is drawn at its own outer diameter and color. All conductors meet at one point at the other end of the segment and splay apart over the whole segment toward the `flying leads` end, where each one ends on its own. Exactly one end of the segment must have a `flying leads` connector. Run `map_cables_and_conductors_to_segments` first. Conductors are ordered by their cavity at the connector, so neighbors in the fan are neighbors in the connector. A subdivided segment is splayed in a straight line from end to end.

Each splayed conductor gets a 2D output csys named `flying_lead_end` at its tip, pointing outward. It is written to `csys_children` on that conductor's conductor-segment row (`{conductor}.{segment}`, parented to the segment) and on the cavity the conductor ends in at the `flying leads` connector (e.g. `P4.3`, which the macro parents to the segment origin). A terminal or flagnote attaches with `parent_csys_instance_name="P4.3"` and `parent_csys_outputcsys_name="flying_lead_end"`.

To use it, assign the connector at the loose end of the segment the general library part `flying leads` (`mpn="flying leads"`, `lib_repo="https://github.com/harnice/harnice-general-library"`, `lib_subpath="parts/flying_leads/"`). That part has no manufacturer and no drawing, has a `3d-mate` at its origin, and sets `"exclude_from_bom": true`, so `instances_list.assign_bom_line_numbers` leaves it off the BOM.

Terminals are not part of this drawing. Make them in the build instructions as ordinary instances, then add `terminal` to the item types in the formboard's `input_instances` to draw them (`tests/test-harness-4` does this):

```python
for conductor in instances_list.read():
    for cavity in (conductor.get("node_at_end_a"), conductor.get("node_at_end_b")):
        if conductor.get("item_type") == "conductor" and str(cavity).startswith("P4."):
            terminal = {
                "instance_name": f"{cavity}.terminal",
                "item_type": "terminal",
                "mpn": "RING_TERMINAL-22-8-FF0000",
                "lib_repo": "https://github.com/harnice/harnice-general-library",
                "lib_subpath": "parts/generic_ring_terminals/",
                "parent_csys_instance_name": cavity,
                "parent_csys_outputcsys_name": "flying_lead_end",
                "bom_line_number": True,
            }
            instances_list.new_instance(terminal["instance_name"], terminal)
            library_utils.pull(terminal)
```

**Args:**

- `instance`, `dimension`, `dimension_units`, `scale` — same as `basic_segment_generator`.
- `splay_angle` — optional, degrees between neighboring conductors (default 10). `standard_harnice_formboard` passes its `flying_lead_splay_angle`.

**Writes:** `{artifact_id}-drawing.svg`; `csys_children` / `parent_csys_outputcsys_name` on each conductor-segment row of the segment; and `csys_children` plus `parent_csys_instance_name` / `parent_csys_outputcsys_name` (the segment, `origin`) on each cavity at the `flying leads` connector.


### `trace_layout_visualizer`

Draws conductor and/or cable routes across the bundle network in the same flattened-network space as the formboard, so `scale` means the same thing. Uses the Analyze-circuits overlay geometry (`flattened_network.trace_layer_markup`). White fills with no outline get a gray outline so they print.

**Args:**

- `artifact_id`
- `trace_item_types` — list (or a single string) in back-to-front order. Defaults to `["conductor", "cable"]`.
- `input_instances` — optional filter; non-conductor/cable rows are ignored, so you can reuse a formboard list. Omit to draw every conductor/cable.
- `scale` — default `1`.

**Writes:** `{pn-rev}-{artifact_id}-master.svg`.

Default harness build calls it as `conductor_layout-1` (`trace_item_types=["conductor"]`) and `cable_layout-1` (`trace_item_types=["cable"]`), both at scale A.


### `circuit_visualizer`

One schematic row per conductor: circuit ID on the left, a left-to-right path on the right (end A, mid nodes such as contacts, the conductor, end B). Ends come from `node_at_end_*` when set, otherwise from `circuit_utils.end_ports_of_circuit`.

**Args:** `input_instances`. Rows that are not `item_type=="conductor"` are skipped. Default harness build passes `instances_list.read()`.

**Writes:** `{pn-rev}-{artifact_id}-circuit-visualizer-master.svg`.

Default call: `artifact_id="circuitviz-1"`.


### `revision_history_table`

Reads every revision of the current project (`rev_history.info(all=True)`) and draws an SVG table: rev, update, status, drawn, checked, started, modified. Rows that list `affectedinstances` get a `rev_change_callout` flagnote bubble in the rev column.

**Args:** none beyond `artifact_id`.

**Writes:** `{pn-rev}-{artifact_id}-master.svg`.

Default call: `artifact_id="revhistory-1"`.


### `build_notes_table`

Renders the build-note instances you pass in as an SVG table (number + text). Notes that point at instances get a flagnote bubble (pulled from that note's library MPN) in the number column.

**Args:** `input_instances` — rows with `note_type=="build_note"`. Default harness build collects those from the instances list.

**Writes:** `{pn-rev}-{artifact_id}-master.svg`, and declares `{pn-rev}-{artifact_id}-build_notes-list.tsv` in its file structure.

Default call: `artifact_id="build_notes_table-1"`.


### `wirelist_exporter`

One row per conductor: circuit ID, length (3 significant figures), cable group, conductor identifier, from/to connector group and cavity. Row fill is derived from the conductor's appearance (average of base + stripe colors) so the sheet, the CSV, and the Excel file stay in sync. Excel is Excel 97–2003 (`.xls`) because of the xlwt palette.

**Args:** `input_instances` (optional; defaults to `instances_list.read()`). Non-conductors are skipped.

**Writes:**

- `{pn-rev}-{artifact_id}-wirelist.csv`
- `{pn-rev}-{artifact_id}-wirelist.xls`
- `{pn-rev}-{artifact_id}-wirelist-master.svg`

Default call: `artifact_id="wirelist-1"`.


### `harness_step_builder`

Builds one 3D STEP of the harness from the chosen network and the instances list. Each chosen-network segment is swept as a circular tube along its existing Bezier (or straight line) using that segment's `diameter`. Each cable and conductor mapped onto those segments is swept as its own tube on the same centerline (jacket OD or conductor OD), so the solids overlap and can be shown or hidden independently in STEP mode. Every other instance that already has `model.step` is copied into the same file at the pose from `bundle_network_utils.calculate_location_3d` (`parent_csys` plus `3d_translate`). Missing models are skipped.

**Args:** `chosen_network` — the chosen (solved) 3D network dict. Default harness build passes `bundle_network`. `input_instances` — which instances to write into the STEP. Default harness build passes `instances_list.read()`. Placement still walks the full instances list.

**Writes:** `{pn-rev}-{artifact_id}.step`.

Default call: `artifact_id="harness-step-1"`.


### `pdf_generator`

Assembles every `*-master.svg` in the current revision into a multi-page PDF: page frame, titleblock, and a master-contents layer you can clone onto sheets. Each `run_macro("pdf_generator", …)` call is one drawing; open it from **instance data** → that imported instance → **pdf drawing**.

Call this from build instructions with a `page_setup` **object** (not a file). Put the call after the macros that write `*-master.svg` files so those masters are included.

How it works:

1. Reads `page_setup` from the `run_macro` kwargs (`{"pages": […]}`). Edit pages there — the console page-info panel is read-only.
2. Walks the revision folder for files named `{pn-rev}-{master_name}-master.svg` whose SVG contains `id="{master_name}-contents-start"`, and composites them into `{artifact_id}-mastercontents.svg` (parked far off-page).
3. For each page in the setup: pulls the titleblock (`tblock_mpn` / `tblock_lib_repo` / `tblock_lib_subpath`), applies text replacements, writes a user-editable page SVG under `page_svgs/`. Page identity is `text_replacements["tblock-key-pagedesc"]`. Default callers fill PN/rev from `state.partnumber`, description/drawn-by from `rev_history.info`, scale from `scales.get("A")`, and `autosheet` for the sheet number.
4. Exports each page SVG to PDF with Inkscape and merges them to `{pn-rev}-{artifact_id}.pdf` at the **revision root**. Linked raster images stay links in the sheet SVG. The export copy embeds those files so the PDF contains the pixels.

**Args:** `artifact_id` (instance name, default `"pdf_drawing-1"`), `page_setup` (dict of pages). Put the drawing scale in `text_replacements["tblock-key-scale"]` (typically `scales.get("A")`). Default harness and system build instructions inline this dict (harness: overview / to-from table / channel map; system: a single `block_diagram` page).

**Page setup fields:** `tblock_mpn`, `tblock_lib_repo`, `tblock_lib_subpath`, `page_size_in`, `tblock_anchor`, `tblock_offset_px`, `text_replacements` (page name is `tblock-key-pagedesc`). Inkscape is resolved from `paths/paths.json`, then `paths.example.json`, then the macOS default app path.

Default: one drawing, `artifact_id="pdf_drawing-1"`, with `page_setup` inlined in the default build instructions.


### `subsystem_symbol`

Seeds (and later verifies) a symbol SVG so this system can be dropped into a parent system as a device. Each `run_macro` call is one imported instance; open it from **instance data** → that instance → **subsystem symbol**. The editor is the device-symbol toolset plus **System diagram**, which drops the current block diagram contents as a primitive. `scale` sets that primitive's scale. Each `show_*` argument is one layer (`show_boundary`, `show_devices`, `show_subsystems`, `show_harnesses`, `show_mating_connectors`, `show_external_interface_flags`, `show_harness_labels`, `show_channel_traces`, `show_circuit_traces`). True draws it. False sets `display="none"`. Omitted flags are True. A later build keeps each primitive where you put it, updates its scale, and replaces its contents with a new copy of the current block diagram using those flags.

On first seed the macro writes a blank SVG. It does not add, move, or delete primitives you placed; it only refreshes diagram copies already on the symbol. Connector pins come from unique `connector_name` values in the system ICD (`fileio.path("icd")`). It also runs device signals-list checks against that ICD. Pin mismatches vs the ICD print a warning and do not fail the build.

==The ICD is compiled *after* build instructions, so this macro always reads the ICD from the previous build.== After you add, remove, or rename external-interface flags, build twice. If no previous ICD exists yet, verification is skipped.

**Args:** `artifact_id` (default `"subsystem-symbol-1"`), `scale` (default `0.1`), and the `show_*` layer flags above (each default `True`).

**Writes:** `{pn-rev}-{artifact_id}-subsystem-symbol.svg`, `{pn-rev}-{artifact_id}-params.json` (stores `scale` and the `show_*` flags).


### `physical_model_drawing`

Draws the system physical assembly as one orthographic view. OpenCascade projects each placed device body to its visible edges and silhouettes, then the drawing adds that device's instance name. The name is left off when other bodies hide half or more of its silhouette. Hidden lines, mate connectors, and devices named in `hidden_instances` are left out.

A face photo that faces the camera is an SVG `<image>` link to the PNG already stored on that device, relative to the revision folder. The picture sits on the bounding-box face, the same face the physical-model viewer paints. A screenshot is drawn when any part of its face can be seen, even if its center is covered. Where a body shows, its screenshot is painted over the others there, so gear seen through an open rack frame stays on top of the frame's face. Anything else paints from farthest to nearest. `pdf_generator` embeds those links as raster images when it writes the PDF.

**Args:**

- `scale` — drawing scale, the same numbers as a formboard. `1` is full size (96 px per model inch, then this factor).
- `lineweight` — stroke thickness on the sheet, in px. `1` is the default. It stays that thick when `scale` changes.
- `hidden_instances` — device names to omit. A list, or one name.
- `orientation` — `front`, `back`, `left`, `right`, `top`, or `bottom`, or the viewport as `alpha`, `beta`, `gamma` (a dict or a 3-number list). `(0, 0, 0)` is the front view: look along +Y, with +X to the right and +Z up. The rotation is `R = Rx(α) · Ry(β) · Rz(γ)`, the same convention as a device pose. Named views look straight at that face, with the photo upright the way the physical-model viewer shows it.

**Writes:** `{artifact_id}-master.svg`.

Default system build calls it once (`artifact_id="physical-1"`, `scale=1`, `lineweight=1`, `orientation="front"`), before `pdf_generator`.


### Device body macros

`build_rectangular_physical_model`, `build_rackmount_physical_model`, `build_rackmount_enclosure`, and `build_physical_model_from_step` live in `macros/device_artifacts`. A device build calls one of them. The macro writes `fileio.path("body")`, the device's `body.step`. Arguments, the inch frame, and mate connectors are on the [CAD](../cad.md) page.

Default call: `artifact_id="body-1"`.


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
fileio.path("gitignore")                       L-- .gitignore
```

A build writes `.gitignore` in the revision folder. This project type ignores:

- `*.tmp`

Rules already in the file stay.

The empty tree above is the *macro project type* itself (`harnice.project_types.macro.file_structure()`), which has no fixed files. That is expected. A macro's real files are the ones **that macro** declares in `macro_file_structure()`, rooted at `instance_data/macro/{artifact_id}/` inside whatever project type called it.
