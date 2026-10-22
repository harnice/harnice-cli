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

This file is the procedure for a **system** `build.py`. The functions you
may call are the headings named below in
[reference.md](../build-api/reference.md).

A harness revision follows `skills/harness/SKILL.md`. A device signals
list follows `skills/device-signals-list/SKILL.md`. A catalog of library
SKUs follows `skills/part-family/SKILL.md`.


## What runs

The script is `fileio.path("build instructions")` in the system revision.
Harnice runs it as `__main__`. If this revision is a harness, stop and
follow the harness skill.

These names are already bound. Do not write `from harnice import ...`.
You may import the standard library.

Read the `build.py` already in the revision before you replace it. The
stock script is in the clone at:

    src/harnice/defaults/system_default_build_instructions.py

Keep that order. Put new rules in the section they belong to. Code at
module level runs on every build. `connector_chooser` and
`m85049_chooser` are `def`s on this system. A child harness calls them
with `build_utils.run_instruction_from_relative`. Do not put those part
numbers in the harness script.

Reach files with `fileio.path` and `fileio.dirpath`. Do not join folders
into a path yourself.

Which endpoints are one patch, which connector mates, and which cable a
circuit uses are my decisions. Ask, and put the choice in front of me.
Record it in a comment. `cli.warn` prints a warning and continues.
Raising stops the build.


## Call these headings only

In [reference.md](../build-api/reference.md):

- Instances List
- Channels and Mapping
- Electrical, the Circuits subsection
- Revision History
- Build instructions tools: General and Macros
- System, the General subsection
- Files and State
- Channel types
- Reading a list back: `instances_list.read`, `circuits_list.read`, `channel_map.read`, `passthrough_map.read`, `rev_history.read`
- Shipped macros: `subsystem_symbol` and `pdf_generator`

Do not call Bundle Networks, Cables, Build Notes, Part Libraries, or
Post-Harness Instances. Those are the harness script.


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
3. `channel_map.compile_hierarchical()`
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

From the system revision folder:

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
- [ ] You kept the stock script's order
- [ ] Every Harnice call is under a heading this skill allows in [reference.md](../build-api/reference.md), with arguments from that function's doc page or docstring
- [ ] Decisions I made are comments in the file
- [ ] An agent build exited 0. A chatbot told me to click Build and paste the errors back
