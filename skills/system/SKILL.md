---
name: system-build
description: >-
  Write or edit Harnice system build.py: channel maps, passthroughs, circuits,
  cable recommendations, and connector choosers that a harness will call. Use
  when the user asks for system build instructions, a channel map, or a
  passthrough route. A harness revision uses the harness-build skill. A device
  pinout uses the device-signals-list skill. A catalog of library SKUs uses
  the part-family skill. Follow this skill when it is the best match. Do not
  ask which skill to follow. If the request is not clear, ask for
  clarification.
---

# Harnice system build instructions

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

Before you follow the rest of this skill, pull the latest `main` from the skills repository, https://github.com/harnice/harnice-cli. Check out `main` in that clone and pull. Read this file again after the pull. If you cannot pull, stop and tell me to pull that repository to the latest `main`. Wait until I have, then read this file again from that `main`.

When you write a path to reference material, write it with respect to the library folder if one is available. Use library locations to establish where you are, then write `(url)/path/file`. Library locations are `repository_locations.csv`. The first column is the library URL. The second column is the local checkout. `url` is the URL of the checkout that contains the file. `path/file` is the path under that checkout. A file outside every checkout keeps the path I gave you.

This file is the procedure for a **system** `build.py`. The pages you
may call are listed below. Each page is the list of calls and how to
use them. Read it before you call.

A harness revision follows `skills/harness/SKILL.md`. A device signals
list follows `skills/device-signals-list/SKILL.md`. A catalog of library
SKUs follows `skills/part-family/SKILL.md`. Arranging device solids
follows `skills/cad/SKILL.md`. This script does not write `physical.json`
or `assembly.step`.


## Why the script exists

The instances list is the source of truth for a harness or a system. It
records every piece of data about every item or idea in that project.
Build instructions build that list up. When an artifact has to describe
the project, the same script exports it from the list.


## What runs

The script is `fileio.path("build instructions")` in the system revision.
Do not run `build.py`. From that revision folder, `harnice -b` runs the
project. If this revision is a harness, stop and follow the harness skill.

Do not import anything. The names you need are already bound. The one
exception is `import json` when this script reads a placed device's
configuration from the BOM.

Read the `build.py` already in the revision before you replace it. The
stock script is in the clone at:

    src/harnice/defaults/system_default_build_instructions.py

That script makes a new system build, and it shows the usual steps.
Remove a section the project does not need. The script has to succeed.
Code at module level runs on every build. `connector_chooser` and
`m85049_chooser` are `def`s on this system. A child harness calls them
with `build_utils.run_instruction_from_relative`. Do not put those part
numbers in the harness script.

Reach files with `fileio.path` and `fileio.dirpath`. The keys are in
`skills/fileio/SKILL.md`. Do not join folders into a path yourself.

Which endpoints are one patch, which connector mates, and which cable a
circuit uses are my decisions. Ask, and put the choice in front of me.
Record it in a comment. `cli.warn` prints a warning and continues.
Raising stops the build.


## Call these pages only

- `instances_list` — `docs/interacting_with_data/_instances_lists.md`
- `channel_map` — `docs/interacting_with_data/_channel_maps.md`
- `passthrough_map` — `docs/interacting_with_data/_passthrough_maps.md`
- `circuits_list` — `docs/interacting_with_data/_circuits_lists.md`
- `rev_history` — `docs/interacting_with_data/_revision_history_lists.md`
- `build_utils` — `docs/commands/_build_utils.md`
- `system_utils` — `docs/commands/_system_utils.md`
- `fileio`, `state`, and `cli` — `docs/commands/_manipulating_files.md`
- `chtype` — `docs/project_types/_channel_type.md`. A channel type is electrical information only. It must not specify a connector type. The connector is on the device signals list.
- Shipped macros `subsystem_symbol` and `pdf_generator` — `docs/project_types/_macro.md`

Do not call bundle networks, cables, build notes, part libraries, or
post-harness instances. Those are the harness script.


## Order

`system.build()` already called `channel_map.new()` before this script
runs. One row per channel endpoint. Do not call `channel_map.new()` again.

1. `channel_map.map` or `channel_map.force` for patches I named. A key is
   `(device_refdes, channel_id)` for one endpoint, or
   `(device_refdes, channel_id, repeat_channel_id)` for one face of a
   passthrough. Both ends of a patch are in the same group of connected
   harnesses.
2. `channel_map.map_unmapped_compatibles_alphabetically()` only if I said
   to auto-map what is left.
3. `channel_map.flatten()`
4. `passthrough_map.new()`, then any `passthrough_map.route()` hops I
   named, then `passthrough_map.resolve()`
5. `circuits_list.new()`
6. `system_utils.create_instances_from_circuits_list()`
7. The design checks, channel-type colors, and cable recommendations
   already in the stock script. Change them from what I said. Do not
   invent a cable MPN.
8. `subsystem_symbol`, then `pdf_generator`. The ICD is written after
   build instructions, so a subsystem symbol needs a second build after
   an ICD change.
9. `connector_chooser` and `m85049_chooser` at the end of the file, as
   module-level functions. A harness calls them by those names. Write
   the mating part here.


## Run the build

Do not run `build.py`. From the system revision folder:

    harnice -b

If `harnice` is not on PATH, and you already cloned
https://github.com/harnice/harnice-cli, stay in the revision folder and run:

    python3 /path/to/harnice-cli/src/harnice/__main__.py -b

If you can run that command, run it. A traceback is the review: fix
`build.py` and run it again.

If you cannot run a command, give me the script and tell me to click
Build and paste the error text back. Do not invent an exit code.


## Reading a placed device's configuration

This script does not receive a `configuration` dict. Harnice has already rebuilt each placed device. Read a placed device's answers for any reason, including a setup note the build would otherwise ignore. Choosing a `channel_map.map` is one example. Read the BOM row. The page is `docs/interacting_with_data/_reading_device_configurations.md`, section "From the system build instructions".

    import json
    text = ""
    for row in fileio.read_tsv("bom"):
        if row["device_refdes"] == refdes:
            text = (row.get("configuration") or "").strip()
            break
    answers = json.loads(text) if text else {}
    value = answers.get(variable)

`value` is a string, a number, `True`, `False`, `None`, or a list of strings. A `json`, `yaml`, or `toml` field is still the document text. Parse that string again for the data inside it. An empty cell means that instance has no saved answers. The device's own build script is the other section of that page: there the name is `configuration["field_id"]`, and those structured fields are already parsed. A program outside Harnice uses the page section "From another program".


## Done

- [ ] The revision is a system, and you edited that `build.py`
- [ ] You did not write harness network code, a device signals list, or a part family
- [ ] A stock section you removed is one the project does not need, and `harnice -b` still succeeds
- [ ] Every Harnice call is on a page this skill lists, with arguments from that page
- [ ] Decisions I made are comments in the file
- [ ] An agent build exited 0. A chatbot told me to click Build and paste the errors back
