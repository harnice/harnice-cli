---
name: channel-type
description: >-
  Add one row to a Harnice library channel_types.tsv when a device signals
  list needs a channel type that is not already in the table. Use when the
  user agrees to add a channel type, or asks for a new channel type id,
  signals column, or compatible mate.
---

# Harnice channel-type skill

Add one channel type, and only after I have agreed to add it. This file is
the procedure. Then go back to `skills/device-signals-list/SKILL.md` and use
the new id.

Read `project_types/_channel_type.md` for `chtype.signals` and
`chtype.compatibles`. The documentation is in the command-line package
(`harnice --docs`) or, in a clone of
https://github.com/harnice/harnice-cli, at `src/harnice/docs/`. Start with
`index.md`. The same pages are at https://harnice.io/ when you can reach the
internet.


## Look before you add

A channel type is a tuple `(channel_type_id, lib_repo)`.

`lib_repo` is the library URL I gave you. The file is `channel_types.tsv` at
the root of that library. Harnice finds the checkout through
`repository_locations.csv`: the first column is that URL, the second column
is the local path. If that URL is not in the CSV, stop and ask. Do not guess
the path.

Search that file for a row with the same signal names and the same
direction. If one exists, tell me its id and stop. Do not add a second name
for a type the file already has.

Do not edit `https://github.com/harnice/harnice-general-library` unless I said
this type belongs in the public library and the checkout is my branch of
that repo.


## What you still need from me

Ask only for what this conversation does not already say:

- the `lib_repo` URL
- the signal names, which `build.py` will have to use verbatim
- direction: `in` for a load or input, `out` for a source or output, blank
  for chassis
- the mate: an existing id in this file, or none yet
- a description in the same voice as the rows around it

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

```
(2, "https://github.com/harnice/harnice-general-library")
[(13, "https://github.com/harnice/harnice-general-library"), (19, "https://github.com/harnice/harnice-general-library")]
```

Use the `lib_repo` I gave you, not the URL in the example.

When the mate row is in the same file, add this new id to that mate's
`compatible_channel_types` as well. The existing rows name both directions.

Leave `status`, `linked documentation`, and the limit and capacity columns
blank unless I gave those values. Do not invent a voltage, a current, or a
datasheet URL.


## Show me, then wait

If you can edit the library file, edit it and show me the diff. If you
cannot, give me the row to paste and say that it is not in the file yet.

Wait until I accept the row. Then the tuple is `(id, lib_repo)` with that
URL, and the device signals-list skill may use it. Do not write `build.py`
in this skill.
