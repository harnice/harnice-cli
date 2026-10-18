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
    "library/macros/harness_artifacts",        # path from that library root to the MPN folder
    "https://github.com/harnice/harnice",      # library repo URL from library_locations.csv
    artifact_id="formboard-overview",          # unique instance name for *this* run
    scale=0.25,                                # extra kwargs become globals inside the macro
    input_instances=formboard_overview_instances,
)
```

**Required arguments**

- `macro_part_number` — the MPN folder name in the library (`standard_harnice_formboard`, `bom_exporter_bottom_up`, …).
- `lib_subpath` — directories between the library root and the MPN folder. Shipped Harnice macros use `library/macros/harness_artifacts` or `library/macros/system_artifacts`.
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

Shipped Harnice macros are in this repo under `library/macros/`, grouped by what they produce:

```
library/macros/
├── harness_artifacts/     # macros that write harness deliverables (drawings, tables, STEP, …)
└── system_artifacts/      # macros that write system deliverables (subsystem symbol, …)
```

Each MPN is a library part:

```
library/macros/harness_artifacts/bom_exporter_bottom_up/
├── bom_exporter_bottom_up-revision_history.tsv
└── rev1/
    └── bom_exporter_bottom_up.py
```

That is the same shape as a connector or a titleblock: part-number folder, revision history, revision folder, files. Rolling a macro revision is the same form/fit/function decision as rolling a part revision. Callers that omit `lib_rev_used_here` get the latest; callers that pin a rev keep getting that rev. See [Libraries](../getting_started/libraries.md).


---

## What macros do

Every shipped Harnice macro reads design data (typically the instances list) and writes files under `instance_data/macro/{artifact_id}/`: BOMs, formboards, PDF sheets, analysis drawings, tables, and similar deliverables. Default harness build instructions call a stack of them at the end of the script; default system build instructions call `subsystem_symbol`.

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
#    "library/macros/harness_artifacts",
#    "https://github.com/harnice/harnice",
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

These are the macros that currently ship in this repo. Unless noted, `lib_repo` is `https://github.com/harnice/harnice`. Each one writes under `instance_data/macro/{artifact_id}/`.

| MPN | Library folder | Who calls it by default |
|---|---|---|
| `bom_exporter_bottom_up` | `library/macros/harness_artifacts` | default harness build (`artifact_id="bom-1"`) |
| `tooling_list_exporter` | `library/macros/harness_artifacts` | default harness build (`artifact_id="tool_list-1"`) |
| `standard_harnice_formboard` | `library/macros/harness_artifacts` | default harness build, twice (overview + detail) |
| `basic_segment_generator` | `library/macros/harness_artifacts` | `standard_harnice_formboard`, once per segment |
| `trace_layout_visualizer` | `library/macros/harness_artifacts` | default harness build, twice (conductors + cables) |
| `circuit_visualizer` | `library/macros/harness_artifacts` | default harness build (`artifact_id="circuitviz-1"`) |
| `revision_history_table` | `library/macros/harness_artifacts` | default harness build (`artifact_id="revhistory-1"`) |
| `build_notes_table` | `library/macros/harness_artifacts` | default harness build (`artifact_id="build_notes_table-1"`) |
| `wirelist_exporter` | `library/macros/harness_artifacts` | default harness build (`artifact_id="wirelist-1"`) |
| `harness_step_builder` | `library/macros/harness_artifacts` | default harness build (`artifact_id="harness-step-1"`) |
| `cutlist_exporter_bottom_up` | `library/macros/harness_artifacts` | not in the default script; call it yourself |
| `pdf_generator` | `library/macros/harness_artifacts` | default harness and system build (`artifact_id="pdf_drawing-1"`) |
| `subsystem_symbol` | `library/macros/system_artifacts` | default system build (`artifact_id="subsystem-symbol-1"`) |



### `bom_exporter_bottom_up`

Rolls every instance that has a `bom_line_number` into one row per line number: quantity, MPN, item type, library fields, exact length, and length plus a 12-inch margin (cables are rounded to two decimals before summing). Writes a TSV and an SVG table that grows **up** from the bottom-right, with a `bom_table_item` flagnote bubble in the item column.

**Args:** none beyond `artifact_id` (reads `instances_list` itself).

**Writes** (under `instance_data/macro/{artifact_id}/`):

- `{pn-rev}-{artifact_id}.tsv` — `bom tsv`
- `{pn-rev}-{artifact_id}-master.svg` — `bom svg` (picked up later by `pdf_generator`)

Default call: `artifact_id="bom-1"`.


### `tooling_list_exporter`

Walks the instances list, parses each `lib_tools` cell (`ast.literal_eval` of a list or a single name), and emits a de-duplicated tooling list. Writes an SVG table (one column, header **REQUIRED TOOLING**) and a TSV. If nothing has tools, the TSV is removed so a stale file does not linger.

**Args:** none beyond `artifact_id`.

**Writes:** `{pn-rev}-{artifact_id}.tsv` (`tooling list tsv`), `{pn-rev}-{artifact_id}-master.svg` (`tooling list svg`).

Default call: `artifact_id="tool_list-1"`.


### `standard_harnice_formboard`

Lays harness geometry into a formboard SVG in flattened-network space. Places printable instances (connectors, backshells, segments, flagnotes, …) by coordinate system, draws leader lines for flagnotes, and can draw cable/conductor paths plus a filleted bundle border instead of plotting those item types as symbols.

For each **segment** it calls `basic_segment_generator` as a **child macro** (`artifact_id="{this_artifact_id}-{segment_name}"`, `base_directory` inside this instance). Flagnotes are pulled from the library (without recording them again in the parent library history, because the same bubble can appear on overview and detail). Other drawings are copied from the parent project's `instance_data/`.

**Args:**

- `artifact_id` — instance name (`formboard-overview`, `formboard-detail`, …).
- `input_instances` — the rows to plot. Default harness build passes a filtered list: overview gets structure + part-name flagnotes; detail gets structure + BOM bubbles + build-note and rev-change flagnotes.
- `scale` — drawing scale (same numbers as PDF titleblock scales A/B/C).
- `rotation` — optional, degrees (documented on the macro; placement uses flattened-network angles).
- `dimension` — 0–100, opacity of segment length dimensions. Default harness overview passes `0` (hidden); omit for fully opaque (100).
- `trace_path_item_types` — optional list of `item_type`s to draw as paths along the bundle instead of as symbols.

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

Builds one 3D STEP of the harness from the chosen network and the instances list. Each chosen-network segment is swept as a circular tube along its existing Bezier (or straight line) using that segment's `diameter`. Each cable and conductor mapped onto those segments is swept as its own tube on the same centerline (jacket OD or conductor OD), so the solids overlap and can be shown or hidden independently in STEP mode. Every other instance that already has `{instance_name}-model.step` is copied into the same file at the pose from `bundle_network_utils.calculate_location_3d` (`parent_csys` plus `3d_translate`). Missing models are skipped.

**Args:** `chosen_network` — the chosen (solved) 3D network dict. Default harness build passes `bundle_network`. `input_instances` — which instances to write into the STEP. Default harness build passes `instances_list.read()`. Placement still walks the full instances list.

**Writes:** `{pn-rev}-{artifact_id}.step`.

Default call: `artifact_id="harness-step-1"`.


### `cutlist_exporter_bottom_up`

Same grouping idea as the BOM, but only for BOM lines that have a length. Each line number gets a bold total row (exact length and length + 12 in margin) plus one row per cut (instance name and that cut's length). BOM bubbles and `down_right_arrow` flagnotes mark the rows.

**Args:** none beyond `artifact_id` (reads `instances_list`).

**Writes:** `{pn-rev}-{artifact_id}.tsv`, `{pn-rev}-{artifact_id}-master.svg`.

Not in the default harness script. Call it next to `bom_exporter_bottom_up` if you want a cut list on the drawing.


### `pdf_generator`

Assembles every `*-master.svg` in the current revision into a multi-page PDF: page frame, titleblock, and a master-contents layer you can clone onto sheets. Each `run_macro("pdf_generator", …)` call is one drawing; open it from **instance data** → that imported instance → **pdf drawing**.

Call this from build instructions with a `page_setup` **object** (not a file). Put the call after the macros that write `*-master.svg` files so those masters are included.

How it works:

1. Reads `page_setup` from the `run_macro` kwargs (`{"pages": […]}`). Edit pages there — the console page-info panel is read-only.
2. Walks the revision folder for files named `{pn-rev}-{master_name}-master.svg` whose SVG contains `id="{master_name}-contents-start"`, and composites them into `{artifact_id}-mastercontents.svg` (parked far off-page).
3. For each page in the setup: pulls the titleblock (`tblock_mpn` / `tblock_lib_repo` / `tblock_lib_subpath`), applies text replacements, writes a user-editable page SVG under `page_svgs/`. Page identity is `text_replacements["tblock-key-pagedesc"]`. Default callers fill PN/rev from `state.partnumber`, description/drawn-by from `rev_history.info`, scale from `scales.get("A")`, and `autosheet` for the sheet number.
4. Exports each page SVG to PDF with Inkscape and merges them to `{pn-rev}-{artifact_id}.pdf` at the **revision root**.

**Args:** `artifact_id` (instance name, default `"pdf_drawing-1"`), `page_setup` (dict of pages). Put the drawing scale in `text_replacements["tblock-key-scale"]` (typically `scales.get("A")`). Default harness and system build instructions inline this dict (harness: overview / to-from table / channel map; system: a single `block_diagram` page).

**Page setup fields:** `tblock_mpn`, `tblock_lib_repo`, `tblock_lib_subpath`, `page_size_in`, `tblock_anchor`, `tblock_offset_px`, `text_replacements` (page name is `tblock-key-pagedesc`). Inkscape is resolved from `paths/paths.json`, then `paths.example.json`, then the macOS default app path.

Default: one drawing, `artifact_id="pdf_drawing-1"`, with `page_setup` inlined in the default build instructions.


### `subsystem_symbol`

Seeds (and later verifies) a symbol SVG so this system can be dropped into a parent system as a device. Each `run_macro` call is one imported instance; open it from **instance data** → that instance → **subsystem symbol**. The editor is the device-symbol toolset plus **System diagram**, which drops the current block diagram contents (not trace overlays) as a primitive. `scale` sets that primitive's scale, and a later build updates the scale of a diagram already on the symbol.

On first seed the macro writes a blank SVG and does not otherwise redraw a symbol you have already drawn. Connector pins come from unique `connector_name` values in the system ICD (`fileio.path("icd")`). It also runs device signals-list checks against that ICD. Pin mismatches vs the ICD print a warning and do not fail the build.

==The ICD is compiled *after* build instructions, so this macro always reads the ICD from the previous build.== After you add, remove, or rename external-interface flags, build twice. If no previous ICD exists yet, verification is skipped.

**Args:** `artifact_id` (default `"subsystem-symbol-1"`), `scale` (default `0.1`).

**Writes:** `{pn-rev}-{artifact_id}-subsystem-symbol.svg`, `{pn-rev}-{artifact_id}-params.json` (stores `scale`).


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
```

The empty tree above is the *macro project type* itself (`harnice.project_types.macro.file_structure()`), which has no fixed files. That is expected. A macro's real files are the ones **that macro** declares in `macro_file_structure()`, rooted at `instance_data/macro/{artifact_id}/` inside whatever project type called it.
