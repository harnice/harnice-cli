---
name: device-signals-list
description: >-
  Write Harnice device build.py from a pinout, ICD, datasheet, or spreadsheet,
  then run harnice -b until the signal-row count matches the documentation.
  Use when the user asks for a signals list, device build instructions, or
  build.py from a pinout. Follow this skill when it is the best match. Do
  not ask which skill to follow. If the request is not clear, ask for
  clarification.
---

# Harnice device signals-list prompt

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

## Documentation is in the package

The `harnice` command-line package includes the Harnice documentation.
Read those files for file formats, project layout, and functions. Use that
folder when you cannot open a website. This file is the procedure.

    harnice --docs

That prints the folder. If the `harnice` command is not on PATH:

    python3 /path/to/harnice-cli/src/harnice/__main__.py --docs

A clone of https://github.com/harnice/harnice-cli keeps the same folder at
`src/harnice/docs/`, next to `__main__.py`.

Start with `index.md`. An include-markdown directive (opening `{%`,
the words include-markdown, a quoted path such as "some/path.md",
closing `%}`) means that file continues the page, under the same folder.

The same pages are at https://harnice.io/ when you can reach the internet.


Write Harnice device **build instructions** (`build.py`) from the supporting
documentation. I may attach or paste it in this chat, or put it in the device
revision folder. Either way is enough. The output must be a complete, runnable
script. A finished build exits 0 and prints a signal-row count equal to the
number of signals you think the device has from the documentation. That count
is greater than zero.

## Online chatbot or agent

Pick the role that is true, in the first reply, and stay in it.

**Online chatbot.** You cannot run commands on my computer, and you cannot
run Python. Do not pretend that you can. Do not ask for my drawn-by name.
Do not ask how to install Harnice, and do not ask how to run `harnice -b`.
Say this, and then do it:

I am going to write a signals list, and you are going to run it in Harnice,
click Build, and copy and paste me back the error messages until we get it
right.

You write `build.py`. I paste it into the build instructions, click Build,
and paste the error text back to you. You revise the script from that text.
Do not claim the build exited 0 unless I pasted a result that says so.
The `harnice -b` and `drawnby.json` instructions later in this prompt are
not for you.

**Agent on my computer.** You can run a shell in the revision folder. You
run the build yourself. If `drawnby.json` is missing, ask what my drawn-by
name usually is, tell me you will append `-AGENT`, and write that file
before the build. Do not invent the name, and do not ask me to type the
suffix. Do not ask me to run the build for you.

You are not filling `signals.tsv` by hand. You are writing Python that Harnice
runs. The signals are `signals_list.append` calls a person can read. The script
does not open the supporting documentation at build time. Cite it in comments.
If I gave you an absolute path, that path may live in a constant.

Do not write `build.py` until I have answered your questions. A blatantly
obvious mapping is not a question. If the documentation says `fan_umb_pos`
and `fan_umb_neg`, and the channel type is `FAN_UMBILICAL` with signals
`pos,neg`, use that and write the assumption in a comment. Anything less
direct than that, ask. The script you write is the build instructions. It
does not have to be right on the first try, and a revision is okay. Do not
stay blocked trying to make that first try perfect. Record the citations,
decisions, and assumptions in comments, so a person or the next agent can
see how and why the rows got there and can revise them. A build that exits 0
means the file is valid. It is not a reason to keep asking until the pinout
is perfect.


## Ask me for the engineering decisions

Assigning channel types, deciding whether a ground is chassis, choosing what
a connector plugs into, and the rest of the design are my job. Yours is to
ask for clarification, and to bring enough context that I can decide quickly.

Ask when a decision is not already clear from what I said, and is not
blatantly obvious from the documentation and the channel type. With the
question, show what the supporting documentation says, which choices could
fit, and what each choice does to the signals. Do not make me reconstruct
that from the pinout. One answer can cover every pin that follows from it.
Do not ask me to confirm each signal. Do not ask me to confirm a mapping
like `fan_umb_pos` / `fan_umb_neg` onto `FAN_UMBILICAL` signals `pos,neg`.
Write that assumption in a comment and proceed.

The supporting documentation is a claim, not a proof. Pinouts, ICDs,
spreadsheets, and screenshots may contain wrong pin numbers, swapped
polarity, missing grounds, duplicate cavities, and names that are not in any
channel type. If something looks wrong, or two pages disagree, say what you
found and ask. Do not silently pick a side. Do not average a pin number. Do
not pick a nearby channel type. Do not drop a connector to force a
passthrough. Do not write the script while a question is still open. An
obvious mapping is not an open question. If we proceed on an assumption,
write it in a comment, whether I accepted it or it was blatantly obvious.
Hiding it is the failure. If a later try shows something wrong, revise from
those comments. Do not stay blocked on making the first try perfect.

A configuration is a change in use case, not a change in hardware. The part
stays the same. The way it is used changes which signals the list describes.
A digital multimeter is one piece of hardware. The switch setting chooses
the channel types: voltage, current, resistance, and the rest. The meter
does not become a different part when the switch moves. A different
connector or any other hardware change is a different part number, not a
configuration.

An unused pin is not a signal. Leave it off the signals list unless a
channel in this configuration uses it. Omitting that pin is correct. Do
not call it a problem, and do not ask for a new part number because a pin
is unused. A channel that is on the list still includes every signal its
channel type defines.

`configuration` is how Harnice stores that use case. It comes from
`config.yaml` or from the system BOM. Assume one signals list unless I say
otherwise. If a use might add, remove, or retype a signal while the hardware
stays the same, ask. If I name the cases, branch only on those. Do not
invent a mode. An online chatbot does not ask for a drawn-by name. An agent
asks for that name only as described under "Online chatbot or agent".

When the open questions are answered, write the script. In comments above
the rows they affect, record the citation, each decision, and each
assumption, with my answer. A blatantly obvious mapping gets the reason
instead of an answer. That record is what makes a later revision easier. A
later person or agent should be able to see how and why a row is what it is
without this chat. If I gave an absolute path, put it in a constant. If I
said to use the document, name which page you followed.

    # Citation: J1_pinout.pdf, page 2, in the revision folder.
    # Clarification: J1 is a balanced mic input. Pin 1 is chassis, on its own.
    # Answer: mic channel is type 1. Pin 1 is type 5.
    # Assumption: pinout says pin 2 is pos; schematic says pin 2 is ground.
    # Answer: pin 2 is pos. Follow the pinout, page 2.


## Write the smallest script that works

Straight-line code at module level. Constants and dicts at the top are fine.
Do not add a helper function or a nested function. No classes. No
decorators. The script runs once at build time. A reader should be able to
follow it from the first line to the last without jumping to another def.

No emojis in the script, in comments, in strings, or in your reply.


## Run the build

Run this after I have answered.

If you are an online chatbot, you already said you cannot run Python. Keep
that. Give me `build.py` and wait for the error text I paste back from
Build. Do not walk me through `pip`, `uv`, `git clone`, `harnice -b`, or
`drawnby.json`.

If you are an agent on my computer, run the build yourself. Prefer the
command-line package. It does not include the Harnice window.

    pip install harnice

If pip cannot install Harnice, install it with uv. uv is a package manager.
Use it when pip cannot write to the environment.

    uv tool install harnice

From the device revision folder (the folder that contains `build.py`,
usually `rev1/`):

    harnice -b

If neither pip nor uv can install Harnice, or `harnice` is not on PATH,
stop trying to install it. Clone the public command-line repo and run its
entry file. Stay in the revision folder. Do not set PYTHONPATH.

    git clone https://github.com/harnice/harnice-cli.git
    python3 /path/to/harnice-cli/src/harnice/__main__.py -b

Python 3 is enough for a device build. A device `config.yaml` that contains
fields still needs PyYAML. An empty configuration file does not.

`chtype.signals` reads `channel_types.tsv` from the library path in
`repository_locations.csv`, not from a file that only exists in the chat.
Save the TSV I attached to that path when the file is missing.

The build also reads `drawnby.json` before it runs `build.py`. If that file
is missing or the name is blank, write it before you run the build. The
name is the drawn-by name I gave you, with `-AGENT` appended. A usual name
of `K SHUTT` is written as `K SHUTT-AGENT`.

    {"name": "K SHUTT-AGENT"}

Put the file at the root of the checkout you are running, the directory
that contains `src/`. If `HARNICE_ROOT` is set, write
`$HARNICE_ROOT/drawnby.json` instead. Do not put it in the revision folder.
If the file already contains a name, leave it.

If you can run a shell command, run it. Read the output.

- Exit 0 and a line `Wrote N signal rows.` where N is the number of
  signals you think the device has from the documentation, and N is
  greater than 0: show me the rows, using the signals list columns.
  Additional columns are ok but discouraged due to consistency. If you
  need more columns, use data structures in build instructions. You make
  that comparison when you read the output.
- Traceback, or N is 0, or N is some other count, or the line is missing:
  fix `build.py` and run the build again.

If you are an agent, do not stop after writing the file. Do not add
`from harnice` imports to make the command work. Those names are already
in the build script.

If you are an online chatbot, you cannot run a command. Give me the script.
Remind me to click Build in Harnice and paste the error messages back. Do
not claim the build exited 0. Do not ask me to run `harnice -b`.


## What I was going for

A device in Harnice is its signals list. That list is the as-designed truth:
every signal that a channel uses, on a named channel, on a named connector
cavity, with a channel type Harnice already knows how to map. A pin no
channel uses is left off. `build.py` is that list. It does not
have to be right on the first try. A revision is okay, and the comments are
what make the revision possible.

The source of that truth is rarely a Harnice file. It is a vendor pinout, an
ICD, a spreadsheet, a screenshot of a panel, a KiCad netlist, a paragraph in
an email. I want one prompt plus that source to become `build.py`.

A later rebuild runs the same appends until someone revises them. The
comments are how a person or the next agent picks up the citations,
decisions, and assumptions. I may leave the supporting documentation in the
revision folder, or only in the chat. If I give an absolute path, put it in
a constant.


## Where the files live

A device revision folder looks like:

    {pn}/
      {pn}-revision_history.tsv
      rev1/                  ← cwd when this device is built
        build.py             ← you write this
        signals.tsv          ← you must NOT write this by hand; the script does
        attributes.json
        symbol.svg
        config.yaml
        <source file>        ← optional; I may put the pinout here, or only paste it in chat

`fileio.rev_directory()` is that `rev1/` folder (same as `os.getcwd()` during
build). Extra files are allowed; they are not in the official file structure.

A body for this device is `skills/cad/SKILL.md`. This skill does not write
`body.step`.


## Supporting documentation — read it now, cite it in comments

Use whichever of these I gave you:

1. Attached or pasted in this chat.
2. A file already in the revision folder, next to `build.py`.
3. An absolute path I name. Put that path in a constant.

    PINOUT = r"/absolute/path/I/gave/you.pdf"

You do the understanding in this chat. The appends are the signals. Do not
write a parser, a sidecar table, or a check that the file exists at build
time. A missing file is not a reason to invent a pinout, and it is not a
reason to refuse the appends once I have answered.


## Optional: paste this table if you have nothing else

If I do not attach a vendor file, I may paste rows in this shape (tab or
comma separated). These are the signals list columns. Treat the pasted rows
as the supporting documentation. Transcribe them into `append` calls, and
cite the pasted table in a comment. Do not write a parser that reads them
back.

    channel_id	repeat_channel_id	channel_type	signal	cavity	connector_id	device_connector_mpn	harness_connector_mpn
    in1		(1, 'https://github.com/harnice/harnice-general-library')	pos	2	J1	XLR3F
    in1		(1, 'https://github.com/harnice/harnice-general-library')	neg	3	J1	XLR3F
    ch0	A	(1, 'https://github.com/harnice/harnice-general-library')	pos	24	A		DB25F
    ch0	B	(2, 'https://github.com/harnice/harnice-general-library')	pos	24	B		DB25M

Column meanings:

- `channel_id` — one electrical channel. Same id on two connectors = a
  passthrough.
- `repeat_channel_id` — blank for a terminating (one-connector) channel.
  For a passthrough, two distinct values (convention: `A` and `B`).
- `channel_type` — the Harnice channel type tuple `(id, lib_repo)`
- `signal` — must be a signal name of that channel type (see below)
- `cavity` — pin, socket, or stud on that connector. Unique per connector.
- `connector_id` — name of the connector on this device (`J1`, `in1`, `A`)
- `device_connector_mpn` — manufacturer part number when the connector is on
  the device. Set this or `harness_connector_mpn`, not both.
- `harness_connector_mpn` — manufacturer part number when the harness owns
  that face. Passthrough adapters are usually harness-owned.

Additional columns are ok but discouraged due to consistency. If you need
more columns, use data structures in build instructions. If a pasted table
has some other column, keep that meaning in the script and leave it off
the signals list. When you show me the rows, use these columns.


## Harnice names already in scope

Do **not** write `from harnice …`. Build instructions already have:

    signals_list, chtype, fileio, state, cli

and the other list and util names a build script already has. You may `import` stdlib (`os`,
`csv`, `json`, `re`, `xml.etree.ElementTree`, `pathlib`).

`configuration` is a dict Harnice injects (defaults from `config.yaml`, or
the system BOM answers). It records a use case, not a hardware change. A
digital multimeter keeps the same hardware while the switch setting selects
voltage, current, or resistance channel types. Read `configuration` only
after I have named that kind of case. A different connector is a new part
number. A pin this configuration does not use is left off the list.


## The only API you need

    signals_list.new()          # wipe and write the header; call once, immediately before the appends
    signals_list.append(        # one row per signal on one endpoint
        channel_id=...,
        repeat_channel_id=...,  # omit or "" unless this is a passthrough
        signal=...,
        cavity=...,
        connector_id=...,
        channel_type=(id, lib_repo),  # lib_repo from repository_locations.csv
        device_connector_mpn=...,   # XOR
        harness_connector_mpn=...,  # XOR — exactly one of these two
    )
    chtype.signals(channel_type)    # list of required signal names
    chtype.parse(val)
    chtype.compatibles(channel_type)

Do not invent Harnice APIs. The documentation from `harnice --docs` names
the functions that exist. A system `build.py` follows
`skills/system/SKILL.md`. A harness `build.py` follows
`skills/harness/SKILL.md`. Do not write `signals.tsv` with `open()`.

`chtype.signals(channel_type)` reads `<local path>/channel_types.tsv` for that
tuple's `lib_repo`. If the id is missing or the `signals` cell is blank, it
returns `[]`. It does not raise. A loop over that empty list appends nothing.


## Channel types (do not invent ids)

A channel type is a tuple `(channel_type_id, lib_repo)`.

`lib_repo` is the library URL exactly as it appears in
`repository_locations.csv`. Harnice does not read the file attached to this
chat when the device builds. It reads
`<local path for that URL>/channel_types.tsv`. The docs mention
`channel_types/channel_types.csv`; the code does not look there.

**If a channel-types table is attached, that table is the catalog.** Use its
`channel_type_id` values and the `lib_repo` the human wrote in the chat.
Copy each signal name from that row's `signals` column, character for
character (`CAN_H`, not `CAN High`, not `pos`). Do not remap those rows onto
the public table below. Do not pair a company id with
`https://github.com/harnice/harnice-general-library`. That combination looks up the public
file, finds no such id, `chtype.signals()` returns `[]`, and the signals
page stays empty after a successful build.

**If no channel-types table is attached,** the only legal types are the
public ones in the general library's `channel_types.tsv` (`lib_repo` =
`https://github.com/harnice/harnice-general-library`):

| id | description | direction | signals | typical mate |
|----|-------------|-----------|---------|--------------|
| 1 | balanced audio mic level | in | pos,neg | 2 |
| 2 | balanced audio mic level | out | pos,neg | 1 |
| 3 | balanced audio line level | in | pos,neg | 4 |
| 4 | balanced audio line level | out | pos,neg | 3 |
| 5 | chassis ground | — | chassis | 5 |
| 6 / 7 | mic with shield | in / out | pos,neg,shield | each other |
| 8 / 9 | line with shield | in / out | pos,neg,shield | each other |
| 12 | 12vdc load | in | pos,neg | 13, 19, 21 |
| 13 | 12vdc supply 10A | out | pos,neg | 12 |
| 17 / 18 | NA 120VAC 15A | out / in | live,neutral,earth | each other |

`in` on a device is a load / input. `out` is a source / output. Map vendor
words (TX, RX, MIC IN, LINE OUT, GND, PIN 1) onto the signal names of the
type you picked. Use `pos` / `neg` only when that type's `signals` cell is
`pos,neg`.

If the interface needs a type that is neither in the attached table nor in
the public table, **stop**. Name the signals you could not type. Do not pick
a nearby id. Do not invent `(99, …)`. If a company table was attached and
the human did not give `lib_repo`, **stop** and ask for that URL. Do not
guess it.

If I tell you to add the missing type, stop this skill and follow
`skills/channel-type/SKILL.md` in the same clone. If you opened this file
from GitHub and cannot read the clone, open this URL and read the entire
file:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/channel-type/SKILL.md

Come back to this skill after I have accepted the new row. Do not add a
channel type unless I said to.


## harnice -b is the checker

Do not reimplement Harnice's rules inside `build.py`. `harnice -b` already
checks them, and a second copy of those checks makes the script harder to
read. If the build raises, fix the row it names and run it again.

`harnice -b` checks:

- Every `signal` is a member of `chtype.signals(channel_type)` for that row.
- Every endpoint `(channel_id, repeat_channel_id)` has all signals of its
  channel type, and no extras.
- `(channel_id, signal, repeat_channel_id)` is unique.
- One endpoint lives on exactly one `connector_id`.
- Exactly one of `device_connector_mpn` / `harness_connector_mpn` per row.
  The same connector id does not mix ownership.
- An additional column produces a warning. Additional columns are ok but
  discouraged due to consistency. If you need more columns, use data
  structures in build instructions.
- Cavity is never blank. Cavity is unique on a connector.
- Terminating channel: one endpoint, `repeat_channel_id` blank.
- Passthrough: same `channel_id` on exactly two connectors, two different
  `repeat_channel_id` values, and the two channel types compatible
  (`chtype.compatibles`).
- More than two endpoints on one `channel_id` is an error.

One thing the build will not catch: `signals_list.new()` followed by zero
appends. A header-only `signals.tsv` still exits 0. Write the signal names
you and I agreed on. Call `new()` once, on the line immediately above those
appends. Do not discover the signal names by looping `chtype.signals()` and
skipping an empty result. An empty result means the tuple does not resolve.
The build will also tell you that if you append a signal from it.

Copy each `lib_repo` from my message. A URL that does not match
`repository_locations.csv` looks up the wrong file.


## Console output

Print statements must use ASCII-only characters. Windows consoles default to
cp1252 and cannot display Unicode checkmarks, fancy quotes, or emoji. The
status line is `Wrote N signal rows.`


## Shape of a good script

Comments that cite the supporting documentation and record each design
intent, assumption, and clarification, including my answer. The rows
themselves are the script: a few constants, then `new()`, then one `append`
per signal, or
one plain loop over a dict whose keys are the signal names (`pos`, not
`Pin 2`). No helper functions. No nested functions. No `planned` list. No
row-count check. No preflight that raises before `new()`.

    signals_list.new()
    signals_list.append(
        channel_id="in1",
        signal="pos",
        cavity="2",
        connector_id="J1",
        channel_type=(1, "https://github.com/harnice/harnice-general-library"),
        device_connector_mpn="XLR3F",
    )
    signals_list.append(
        channel_id="in1",
        signal="neg",
        cavity="3",
        connector_id="J1",
        channel_type=(1, "https://github.com/harnice/harnice-general-library"),
        device_connector_mpn="XLR3F",
    )
    print("Wrote 2 signal rows.")

Call this at module level. A `main()` that is never called leaves the
previous list untouched. `if __name__ == "__main__"` is fine: Harnice runs
the file as `__main__`.

If I confirmed a use case that changes the list while the hardware stays the
same, branch with a plain `if` on `configuration` around those appends.
Example: a digital multimeter's switch setting selects voltage, current, or
resistance channel types. The meter is still the same hardware. If I said
the list does not change, there is no branch.

After you write it, an agent runs `harnice -b`. A traceback is the review.
Fix that row. A script that prints `Wrote 0 signal rows.` or omits the line
is not finished.

Exit 0 means the file is valid. It does not mean the decisions match the
device. Show me what you wrote, with enough context that I can check it.
If I say something is wrong, ask and fix it.

If you are an online chatbot, show me the same thing from the script. Tell
me to click Build in Harnice and paste the error messages back. Do not
invent an exit code, and do not tell me to run `harnice -b`.


## COMMON FAILURE MODES

### Empty signals page after a build that exited 0

The device project's signals list page is `revN/signals.tsv`. Header plus
zero data rows means this script wiped the list and appended nothing. A
system BOM row is a different file: `instance_data/device/<refdes>/signals.tsv`,
copied when that device was placed. Rebuilding the device project does not
update that copy.

Cause: `signals_list.new()` ran and nothing was appended. Usual reasons:

- The script looped `chtype.signals()` and that returned `[]` (wrong repo
  or missing id), so the loop body never appended.
- The appends live in a function that is never called.

Prevention: write the signal names out, and put `new()` on the line
immediately above those appends. `harnice -b` will not flag a header-only
file. It will flag a bad row. Read that traceback and fix the row. Do not
add a checker to the script.

### Unicode print errors on Windows

Cause: `print()` with non-ASCII characters (checkmarks, crosses, bullets,
ellipsis, fancy quotes, emoji) fails on Windows `cmd.exe`.

Prevention: ASCII only in every `print`.

### Channel type not found despite being in the table

Cause: `lib_repo` does not exactly match `repository_locations.csv`.

Prevention: copy the URL from my message or from the table I gave you.
"repo" is not a valid URL.


## HARD RULES

- Read the documentation from `harnice --docs` when you need a file format
  or a function. The same pages are at https://harnice.io/ when you can
  reach the internet.
- No `from harnice` / `import harnice`. Names are already in the namespace.
- Do not hand-write `signals.tsv`.
- Additional columns are ok but discouraged due to consistency. If you need more columns, use data structures in build instructions.
- Do not invent channel type ids. A new id is a row from the channel-type
  skill, and only after I agreed to add it.
- Do not point a company channel-type id at `https://github.com/harnice/harnice-general-library`.
- Do not reimplement the build's checks inside `build.py`. `harnice -b` is
  the validator. If the `harnice` command is missing, run
  `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` from the
  revision folder. That is the same build.
- No `planned` list, no preflight raises, no row-count comparison.
- `signals_list.new()` sits on the line immediately above the appends.
- Signal names are the `signals` column, verbatim.
- Stdlib only unless I named a third-party library I already have.
- No helper functions. No nested functions.
- No emoji. No non-ASCII characters in `print` statements.
- Output is the full `build.py`. Not a sketch. Not "add your pinout here".
  Not a parser. Not a sidecar table.
- If you are an agent, you have run `harnice -b`, or
  `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` when the
  `harnice` command is missing. The process exited 0. The log
  contains `Wrote N signal rows.` where N is the number of signals you
  think the device has from the documentation, and N is greater than 0.
  If you are an online chatbot, you said you cannot run Python, you did not
  invent that result, you did not ask for a drawn-by name, and you told me
  to click Build and paste the error messages back.
- Comments cite the supporting documentation and record each decision and
  assumption. An answer I gave is in the comment. A blatantly obvious mapping
  is in the comment too, with the reason. An absolute path I gave is a
  constant.
- You did not write the script while a question was still open. A wrong
  first try is revised from those comments. You did not stay blocked trying
  to make that first try perfect.


## SELF-CHECK BEFORE SUBMITTING build.py

Ask yourself these questions. If any answer is no, revise the script and
run `harnice -b` again.

- [ ] Can a person read the appends and see every signal without reading a checker?
- [ ] Is extra information kept in data structures in the build instructions? Additional columns are ok but discouraged due to consistency.
- [ ] Is `signals_list.new()` immediately above those appends, with no preflight between them?
- [ ] Are all `print()` statements ASCII-only (no checkmarks, crosses, bullets, or fancy quotes)?
- [ ] Do the comments cite the supporting documentation and record each decision and assumption, including a blatantly obvious mapping and the reason?
- [ ] Do all channel type tuples use the exact repo URL I provided?
- [ ] If you are an agent, did `harnice -b` or `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` print `Wrote N signal rows.` where N is the number of signals you think the device has from the documentation, and N is greater than 0? If you are an online chatbot, did you say you cannot run Python, skip the drawn-by question, and tell me to click Build and paste the errors back?
- [ ] Did you wait until I answered before writing the file, except for a blatantly obvious mapping you recorded in a comment?
- [ ] If you are an agent and `drawnby.json` was missing, did you ask what my drawn-by name usually is and write that name with `-AGENT` appended at the checkout root? If you are an online chatbot, did you leave drawn-by alone?
- [ ] Does the script match the decisions I made, including whether a use case changes the signals list?


## DONE CRITERIA

- [ ] Comments cite the supporting documentation. An absolute path I gave is a constant. The script does not parse that file at build time
- [ ] `signals_list.new()` is immediately followed by the appends a person can read
- [ ] The script does not check the rules that `harnice -b` already checks
- [ ] The script prints `Wrote N signal rows.` and `harnice -b` agrees
- [ ] No invented channel types; company ids use the human's `lib_repo`
- [ ] The script is straight-line module-level code, with no helper or nested function
- [ ] An agent build (`harnice -b`, or `python3 /path/to/harnice-cli/src/harnice/__main__.py -b`) exited 0 with a row count equal to the number of signals you think the device has from the documentation, and that count is greater than 0. An online chatbot did not pretend to run that command. It told me to click Build and paste the errors back
- [ ] Each decision and assumption is a comment in `build.py`. My answers are there. A blatantly obvious mapping is there too, with the reason
- [ ] No pin number was averaged. You did not write the script while a question was still open
- [ ] After the build, or from the script if you could not run it, you showed me what you wrote with enough context to check it

Do not send `build.py` while a question is still open. If the first try is
wrong, revise it. Do not stay blocked trying to make that first try perfect.

When I have answered, reply with:
1. The complete `build.py`
2. Where the supporting documentation lives: the revision folder, this chat, or the absolute-path constant
3. One sentence: terminating, passthrough, or mixed
4. Channel types you used (id, lib_repo, signal names)
5. How many signal rows the build printed. An online chatbot instead says I will click Build and paste the errors back
6. Anything in the source you could not map (a pin that looked used but has no channel, types you need me to add). An unused pin left off the list is not one of these.
7. Whether the signals list depends on configuration, and the cases I named
