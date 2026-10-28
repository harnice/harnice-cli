---
name: fileio
description: >-
  Find a Harnice project file from build instructions. Use when the user
  asks where a file is, which file key to pass, or how to read the revision
  history, a list, a network, repository locations, or a pulled part.
  A harness revision also follows the harness-build skill. A system
  revision also follows the system-build skill. Follow this skill when it
  is the best match. Do not ask which skill to follow. If the request is
  not clear, ask for clarification.
---

# Harnice file access

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

`fileio` is already bound. Do not import it. Do not build a path from a
part number, a revision, and a filename. Do not modify a project file
with `open`, `write`, or `json.dump`. Harnice functions write the lists
and the networks. `fileio` tells you where they are.

Arguments for these calls are on `docs/commands/_manipulating_files.md`.


## The two lookups

A file structure is a dict. A filename or a nested folder is a key. The
human name of a file is the value. `harnice -b` loads the structure for
the open project type.

`fileio.path("file key")` searches the values and returns the absolute
path of that file, under the revision folder.

`fileio.dirpath("folder name")` searches the keys and returns the
absolute path of that folder.

Omit `structure_dict` and `base_directory` in a harness, system, device,
part, cable, flagnote, or title block. Pass them only inside a macro,
described below.

A key this project type does not have raises `TypeError`. The message
names the project types that do have it. Use a key from the list for
the revision that is open.


## Every project

These are not stored in a project type's file structure. They work from
any revision.

- `fileio.path("revision history")` is `{part folder}/{pn}-revision_history.tsv`.
  The part folder is the parent of the revision folder. `{pn}` is
  `state.partnumber("pn")`.
- `fileio.path("repository locations")` is `repository_locations.csv` in
  the Harnice user-data folder. Harnice creates an empty file if it is
  missing. The first column is a library URL. The second column is the
  local checkout of that library.
- `fileio.path("drawnby")` is `drawnby.json` in that same user-data
  folder. `fileio.drawnby()` returns the name stored there.
- `fileio.dirpath("part directory")` and `fileio.part_directory()` are
  the part folder.
- `fileio.dirpath("rev directory")`, `fileio.dirpath(None)`, and
  `fileio.rev_directory()` are the revision folder. During `harnice -b`
  that folder is the current working directory.
- `fileio.harnice_root()` is the user-data folder that holds
  `repository_locations.csv` and `drawnby.json`.
- `fileio.read_tsv(path_or_key)` returns one dict per row. Pass a file
  key, or a path you already resolved. The default delimiter is a tab.
- `fileio.today()` is today's date as `M/D/YY`.

`state.partnumber("pn")` is the part number. `"R"` is the revision
token (`"1"`). `"rev"` is `"rev1"`. `"pn-rev"` is `"mypart-rev1"`.
`state.rev` is the token a revision-history update matches.

The runner calls `fileio.verify_revision_structure()` before the script
starts. A build script does not call it.


## Harness

Paths are under the revision folder.

- `"build instructions"` → `build.py`
- `"instances list"` → `instances.tsv`
- `"library history"` → `libhist.tsv`
- `"flattened network"` → `networks/flat.csv`
- `"chosen network"` → `networks/chosen.json`
- `"available network"` → `networks/available.json`
- `"chosen entity list"` → `networks/entities.json`
- `"flattened network svg"` → `generated_svgs/flat.svg`
- `"circuits overlay"` → `generated_svgs/circuits.svg`
- `"cable overlay"` → `generated_svgs/cable.svg`

Folders, with `fileio.dirpath`:

- `"networks"` → `networks/`
- `"contexts"` → `networks/contexts/`. Reference `.step` and `.stp`
  files dropped here are drawn with the network. They have no file key
  of their own.
- `"generated_svgs"` → `generated_svgs/`
- `"instance_data"` → `instance_data/`


## System

- `"build instructions"` → `build.py`
- `"instances list"` → `instances.tsv`
- `"block diagram"` → `blockdiagram.svg`
- `"icd"` → `signals.tsv`
- `"bom"` → `lists/bom.tsv`
- `"circuits list"` → `lists/circuits.tsv`
- `"post harness instances list"` → `lists/instances_w_hrns.tsv`
- `"system connector list"` → `lists/connectors.tsv`
- `"mapped channels set"` → `lists/mapped.tsv`
- `"library history"` → `lists/libhist.tsv`
- `"channel map"` → `maps/channels.tsv`
- `"flattened channel map"` → `maps/channel_map_flattened.tsv`
- `"passthrough map"` → `maps/passthrough.tsv`
- `"passthrough routing context"` → `maps/context.tsv`
- `"pending forced channels"` → `maps/forced_channels_pending.tsv`
- `"forced signal map"` → `maps/forced_signals.tsv`

Folders, with `fileio.dirpath`:

- `"instance_data"` → `instance_data/`
- `"harnesses"` → `harnesses/`. A harness `push` writes
  `harnesses/instances.tsv` here. That copy has no file key of its own.
- `"lists"` → `lists/`
- `"maps"` → `maps/`


## Device

- `"build instructions"` → `build.py`
- `"signals list"` → `signals.tsv`
- `"attributes"` → `attributes.json`
- `"block diagram symbol"` → `symbol.svg`
- `"configuration setup"` → `config.yaml`

A device revision has no `instance_data` folder in its file structure.


## Part

A part revision has no `build.py` in its file structure.

- `"drawing"` → `drawing.svg`
- `"drawing png"` → `drawing.png`
- `"attributes"` → `attributes.json`
- `"model"` → `model.step`


## Cable

A cable revision has no `build.py` in its file structure.

- `"attributes"` → `attributes.json`
- `"conductor list"` → `conductors.tsv`


## Flagnote

- `"params"` → `params.json`
- `"drawing"` → `drawing.svg`


## Title block

- `"params"` → `params.json`
- `"drawing"` → `drawing.svg`
- `"attributes"` → `attributes.json`


## Channel type

A channel type has no revision files. `chtype.path((channel_type_id, lib_repo))`
is `channel_types.tsv` at the root of that library's checkout. The
checkout is the `repository locations` row for `lib_repo`.


## Inside instance_data

`fileio.dirpath("instance_data")` is the one key for that tree. A pulled
part is `instance_data/{item_type}/{instance_name}/`. Those inner files
are not file keys. Join onto `fileio.dirpath("instance_data")` only when
the file structure does not name the file. A device pulled into a system
keeps its signals list at `instance_data/device/{refdes}/signals.tsv`.


## Macro

The macro project type has no files of its own. A macro defines
`macro_file_structure()` and passes that dict as `structure_dict`.
`base_directory` is `instance_data/macro/{artifact_id}` inside the
project that called `build_utils.run_macro`. A harness or system script
does not look up a macro's files with a bare `fileio.path`. It calls
`run_macro`.
