---
name: harness-build
description: >-
  Write or edit Harnice harness build.py: import a harness from its system,
  call that system's connector choosers, pull parts, and build the network
  and drawings. Use when the user asks for harness build instructions, harness
  rules, a chosen network, or a formboard. A system revision uses the
  system-build skill. A device pinout uses the device-signals-list skill. A
  catalog of library SKUs uses the part-family skill.
---

# Harnice harness build instructions

This file is the procedure for a **harness** `build.py`. The functions you
may call are the headings named below in
[reference.md](../build-api/reference.md).

A system revision follows `skills/system/SKILL.md`. A device signals list
follows `skills/device-signals-list/SKILL.md`. A catalog of library SKUs
follows `skills/part-family/SKILL.md`.


## What runs

The script is `fileio.path("build instructions")` in the harness revision.
Harnice runs it as `__main__`. If this revision is a system, stop and
follow the system skill.

These names are already bound. Do not write `from harnice import ...`.
You may import the standard library.

Read the `build.py` already in the revision before you replace it. The
stock script is in the clone at:

    src/harnice/defaults/harness_default_build_instructions.py

Keep that order. Put new rules in the section they belong to. Code at
module level runs on every build.

Reach files with `fileio.path` and `fileio.dirpath`. Do not join folders
into a path yourself.

Which extra harness rule to add is my decision. Ask, and put the choice
in front of me. Record it in a comment. `cli.warn` prints a warning and
continues. Raising stops the build.

Connector and backshell part numbers are `connector_chooser` and
`m85049_chooser` on the parent system. This script calls them. It does
not define them. Follow `skills/system/SKILL.md` only when I asked you
to change those functions on the system.


## Call these headings only

In [reference.md](../build-api/reference.md):

- Instances List
- Bundle Networks
- Electrical, the Cables subsection
- Revision History
- Build instructions tools: General, Macros, and Part Libraries
- Build Notes
- System, the General subsection, and only `system_utils.import_harness_from_harnice_system`
- System, the Post-Harness Instances subsection
- Files and State
- Reading a list back: `instances_list.read`, `rev_history.read`, `library_history.read`
- Shipped macros except `subsystem_symbol`

Do not call Channels and Mapping, Circuits, or Channel types. Those are
the system script. Do not define `connector_chooser` or `m85049_chooser`
here.


## Order

A harness made from a system position already stores `source_part_number`,
`source_revision`, `source_lib_repo`, `source_subpath`, and
`source_refdes` on the revision history. The stock script starts by
importing that harness. Keep that call.

1. `system_utils.import_harness_from_harnice_system` from those fields.
2. `build_utils.run_instruction_from_relative` for `connector_chooser`
   and `m85049_chooser` on that parent system.
3. Harness-local rules, if I asked for any, go here.
4. `instances_list.raise_error_on_unassigned_connectors()`
5. `library_utils.pull` for each `harness_connector` and `backshell`.
6. Available network, then chosen network, `chosen_network.save`, then
   `flattened_network.derive`.
7. Assign cables and conductors, map them onto segments, then bundle
   diameters.
8. BOM line numbers, build notes, then the output macros
   (`bom_exporter_bottom_up`, formboard, wirelist, `pdf_generator`,
   `harness_step_builder`, and the rest of the stock list).


## Run the build

From the harness revision folder:

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
- [ ] Connector part numbers stayed on the system's chooser
- [ ] You kept the stock script's order
- [ ] Every Harnice call is under a heading this skill allows in [reference.md](../build-api/reference.md), with arguments from that function's doc page or docstring
- [ ] Decisions I made are comments in the file
- [ ] An agent build exited 0. A chatbot told me to click Build and paste the errors back
