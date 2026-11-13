---
name: channel-type
description: >-
  Add one row to a Harnice library channel_types.tsv when a device signals
  list needs a channel type that is not already in the table. A channel type
  is electrical information only and must not specify a connector type. Use
  when the user agrees to add a channel type, or asks for a new channel type
  id, signals column, or compatible mate. Follow this skill when it is the
  best match. Do not ask which skill to follow. If the request is not clear,
  ask for clarification.
---

# Harnice channel-type skill

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

Before you follow the rest of this skill, pull the latest `main` from the skills repository, https://github.com/harnice/harnice-cli. Check out `main` in that clone and pull. Read this file again after the pull. If you cannot pull, stop and tell me to pull that repository to the latest `main`. Wait until I have, then read this file again from that `main`.

When you write a path to reference material, write it with respect to the library folder if one is available. Use library locations to establish where you are, then write `(url)/path/file`. Library locations are `repository_locations.csv`. The first column is the library URL. The second column is the local checkout. `url` is the URL of the checkout that contains the file. `path/file` is the path under that checkout. A file outside every checkout keeps the path I gave you.

Add one channel type, and only after I have agreed to add it. This file is
the procedure. Then go back to the skill you came from and use the new id.
One device is `skills/device-signals-list/SKILL.md`. A catalog of devices is
`skills/part-family/SKILL.md`.

Read `project_types/_channel_type.md` for `chtype.signals` and
`chtype.compatibles`. The documentation is in the command-line package
(`harnice --docs`) or, in a clone of
https://github.com/harnice/harnice-cli, at `src/harnice/docs/`. Start with
`index.md`. The same pages are at https://harnice.io/ when you can reach the
internet.


## A channel type is electrical only

A channel type must not specify a connector type. It records electrical
information only:

- signal names
- direction: `in`, `out`, or blank
- electrical limits, when I gave them (voltage, current, power, level)
- which other channel types it may connect to

Connector family, gender, shell, insert, and part number are not channel-type
fields. They belong on the device signals list (`connector_id`,
`device_connector_mpn`, `harness_connector_mpn`) and on the connector part.

The same signals, direction, and limits on two connectors are one channel
type. Do not add a row because the connector changed. Do not put a connector
name in `description` or `signals`. `balanced audio mic level` is a
description. `XLR mic input`, `RJ45`, `USB-C`, `D-sub`, `speakON`, `male`,
and `female` are connector words, so they stay out of the row.


## Look before you add

A channel type is a tuple `(channel_type_id, lib_repo)`.

`lib_repo` is the library URL I gave you. The file is `channel_types.tsv` at
the root of that library. Harnice finds the checkout through
`repository_locations.csv`: the first column is that URL, the second column
is the local path. If that URL is not in the CSV, stop and ask. Do not guess
the path.

Search that file for a row with the same signal names, the same
direction, and the same electrical limits. If one exists, tell me its id and
stop. A different connector is not a different channel type. Do not add a
second name for a type the file already has.

Do not edit the public general library unless I said this type belongs
there. Its files live in `harnice-general-library/` in the Harnice source
repository. `lib_repo` stays
`https://github.com/harnice/harnice-general-library`. A merge to `main`
publishes that directory to the public library repository.


## What you still need from me

Ask only for what this conversation does not already say:

- the `lib_repo` URL
- the signal names, which `build.py` will have to use verbatim
- direction: `in` for a load or input, `out` for a source or output, blank
  for chassis
- the mate: an existing id in this file, or none yet
- a description of the electrical interface, in the same voice as the rows
  around it. The description must not name a connector type

One new type per agreement. If the mate also does not exist, ask before you
add a second row.


## The row

Append one row. The id is the next integer above the highest
`channel_type_id` in that file. Do not reuse an id, including a gap.

Keep the header. Match the quoting of the rows already in the file. A cell
that contains a comma is quoted. After that quoting is removed, the cells
`chtype` reads are:

- `signals`: comma-separated names, for example `pos,neg`
- `compatible_channel_types`: one Python tuple, or a list of tuples, which
  `ast.literal_eval` accepts
- `channel_default_appearance`: optional Python dict literal, one engineering
  appearance. A channel trace and the channel card use it. Example:
  `{'base_color': '#D59A10'}`
- `signal_default_appearances`: optional Python dict literal, signal name to
  appearance dict. A circuit trace and that signal's bar use the matching
  name. Example:
  `{'pos': {'base_color': '#E24B4A'}, 'neg': {'base_color': '#2E6B9F'}}`

```
(2, "https://github.com/harnice/harnice-general-library")
[(13, "https://github.com/harnice/harnice-general-library"), (19, "https://github.com/harnice/harnice-general-library")]
```

Use the `lib_repo` I gave you, not the URL in the example.

Compatibility does not need to be listed in both directions. Harnice treats
two types as compatible when either row names the other. Put the mate in the
new row's `compatible_channel_types` and leave the mate's row alone. Do not
add the new id to the mate's row, even if older rows in the file name each
other both ways. If the mate's row already names the new id, the new row may
leave the mate out.

Leave `status`, `linked documentation`, the limit and capacity columns, and
both appearance columns blank unless I gave those values. Do not invent a
voltage, a current, a datasheet URL, or a color.


## Show me, then wait

If you can edit the library file, edit it and show me the diff. If you
cannot, give me the row to paste and say that it is not in the file yet.

Wait until I accept the row. Then the tuple is `(id, lib_repo)` with that
URL, and the device signals-list skill may use it. Do not write `build.py`
in this skill.
