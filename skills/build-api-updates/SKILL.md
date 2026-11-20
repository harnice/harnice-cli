---
name: build-api-updates
description: >-
  Update an existing Harnice build.py (harness, system, device, part, or any
  project) to the current build API: functions that moved, were renamed or
  removed, changed what they return, or gained arguments. Use when a build
  fails with an AttributeError, NameError, or TypeError on a Harnice call,
  when I ask to upgrade or migrate build instructions, or when a build was
  written for an older Harnice. Writing new harness build instructions uses
  the harness-build skill. Follow this skill when it is the best match. Do
  not ask which skill to follow. If the request is not clear, ask for
  clarification.
---

# Update build instructions to the current build API

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

Before you follow the rest of this skill, pull the latest `main` from the skills repository, https://github.com/harnice/harnice-cli. Check out `main` in that clone and pull. Read this file again after the pull. If you cannot pull, stop and tell me to pull that repository to the latest `main`. Wait until I have, then read this file again from that `main`.

## How to update a build.py

- Open the project's `build.py`. Search it for every call named in the
  change log below.
- Apply each matching entry, oldest first, so a call that changed twice
  ends up at its newest form.
- Change only the calls an entry names. Keep my own rules, values,
  comments, and layout.
- For an entry marked **behavior**, read what changed and check that the
  script still does what I meant. Ask me before you change logic.
- Build the project. Fix any call the build still reports, then build
  again until it succeeds.
- Do not edit or commit generated files (`instances.tsv`, `networks/`,
  `instance_data/`, drawings) to make the build pass. Tell me which files
  the build changed.
- Tell me which entries you applied, and which **behavior** entries need my
  decision.

A function is in the public build API when a build script can call it by
name: anything without a leading `_` in `fileio`, `state`, `cli`, and the
list, utility, and channel-type modules that the build runner provides.
The stock build instructions in `src/harnice/defaults/` are part of it too.

## Change log

Newest first. Each entry has the date, the pull request, what changed, and
how to update a script.

### 2026-11-20 — #1560: available network source of truth, chosen network helpers moved

**Moved** from `chosen_network` to `bundle_network_utils`. The old names are
gone. Replace the module name and keep the arguments:

| Old call | New call |
| --- | --- |
| `chosen_network.end_all_segments_in_nodes(...)` | `bundle_network_utils.end_all_segments_in_nodes(...)` |
| `chosen_network.ensure_nodes_exist(...)` | `bundle_network_utils.ensure_nodes_exist(...)` |
| `chosen_network.calculate_possible_sub_networks(...)` | `bundle_network_utils.calculate_possible_sub_networks(...)` |
| `chosen_network.find_network_with(...)` | `bundle_network_utils.find_network_with(...)` |

`chosen_network.save` did not move.

**Behavior:** `bundle_network_utils.calculate_possible_sub_networks` returns
an empty list when no route joins the required nodes. Before, it raised
`ValueError`. A missing required node still raises. Replace a
`try`/`except ValueError` around it with a check for `len(...) == 0`. The
stock check that exactly one solution came back still stops the build.

**Behavior:** the available network editor shows only what is in
`available.json`. It no longer adds the source system's mating connector
nodes by itself, and with no file it shows an empty network. Every node and
segment has a `source_of_truth`: `"gui"` or the routing context id it came
from (`"source physical model.step"` for the source system). A harness
build that adds source system nodes or segments only in memory leaves them
out of the editor. To show them, copy the network section of the stock
harness build (`src/harnice/defaults/harness_default_build_instructions.py`,
from `available = available_network.load()` to
`available_network.save(available)`) over the old section, then put my own
network rules back. Ask me before you replace that section.

**Behavior:** `bundle_network_utils.end_all_segments_in_nodes` leaves a
mating connector node that is alone at its location as it is. Before, it
rebuilt the node and named it from its `mate` tag, which undid a rename by
`adopt_mating_connector_nodes` and dropped `source_of_truth`. When mating
connector nodes share a location, the merged node keeps an adopted name
instead of `{A.J1+B.J2}`. No change is needed unless a script relied on the
old renaming.

**Added** argument: `bundle_network_utils.adopt_mating_connector_nodes(...,
replace_existing=True)`. The default does what it did before. `False`
renames without dropping a node that already has the connector's name, so
`bundle_network_utils.raise_on_duplicate_node_ids` reports the clash.

**Added** fields: `physical_assembly.list_mating_connectors` and
`physical_assembly.list_segments` return items with
`"source_of_truth": "source physical model.step"`. No change is needed.

**Added** calls, no change needed: `available_network.save`,
`available_network.source_of_truth`, `available_network.tag_source_of_truth`,
`available_network.keep_only_gui`, `available_network.GUI`,
`available_network.SOURCE_SYSTEM_CONTEXT`,
`bundle_network_utils.raise_on_duplicate_node_ids`,
`bundle_network_utils.average_location`.
