---
name: system-build
description: >-
  Write or edit Harnice system build.py: channel maps, passthroughs, circuits,
  cable recommendations, and connector choosers that a harness will call. Use
  when the user asks for system build instructions, a channel map, or a
  passthrough route. A harness revision uses the harness-build skill. A device
  pinout uses the device-signals-list skill. A catalog of library SKUs uses
  the part-family skill.
---

# Harnice system build instructions

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

Do not import anything. The names you need are already bound.

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
- `chtype` — `docs/project_types/_channel_type.md`
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


## Done

- [ ] The revision is a system, and you edited that `build.py`
- [ ] You did not write harness network code, a device signals list, or a part family
- [ ] A stock section you removed is one the project does not need, and `harnice -b` still succeeds
- [ ] Every Harnice call is on a page this skill lists, with arguments from that page
- [ ] Decisions I made are comments in the file
- [ ] An agent build exited 0. A chatbot told me to click Build and paste the errors back
