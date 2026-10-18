# AI Prompts

Copy-paste briefs for an agent chat.

1. [Device signals list](#device-signals-list-buildpy) — turn any pinout, ICD, or datasheet into device `build.py`
2. [Part family](#part-family-library-skus) — encode a catalog into library SKUs

Each brief tells the agent that this documentation ships with the `harnice` command-line package. `harnice --docs` prints the folder. The agent reads those files when it cannot open the website. The same pages are at [harnice.io](https://harnice.io/).

---

## Device signals list (`build.py`)

You'll get better results with an agent on your computer that can run commands, because it can self-verify and correct mistakes by calling `harnice -b` and reading the terminal errors. Open your project's repository in that application (ClaudeCode, Cursor, etc) so the agent can see your project, channel_types.tsv, and other projects as examples. Consider copying your supporting docs into the rev folder (a pinout PDF, an ICD, a spreadsheet, a screenshot, a schematic note, a vendor table, a netlist, or the optional table format) for traceability and for the agent. The build instructions can still hardcode a path to that documentation wherever the file sits.

Without a desktop agent, a web chatbot can write the script and you run the build yourself in the Harnice application. Attach or paste your supporting docs into the prompt. Name the channel types in that same message if you already know them. Attach `channel_types.tsv` and give the library URL, for example: `Channel types are the attached TSV. lib_repo is https://github.com/my-org/my-library.` That URL is the key in `repository_locations.csv`. The TSV does not contain it. At build time Harnice reads `<local path for that URL>/channel_types.tsv`, not the file you uploaded to the chat.

The engineering decisions are yours: which channel type to use, whether a ground is chassis, what a connector plugs into, and the rest. The agent asks for clarification and puts the context for that decision in front of you so you can answer quickly. It does not write `build.py` until you have answered. A blatantly obvious mapping can proceed without that buyoff: if the documentation says `fan_umb_pos` and `fan_umb_neg`, and the channel type is `FAN_UMBILICAL` with signals `pos,neg`, the agent may use that and still write the assumption in a comment. The supporting documentation is a starting point. The agent will tell you about errors or unclear spots it thinks it found.

The file it writes is the build instructions. It does not have to be right on the first try, and a revision is okay. Decisions and assumptions go into the file so the next pass can see how and why the rows got there. A clean `harnice -b` means the file is valid, which is not a reason to keep going until the pinout is perfect.

An agent that can run commands installs the command-line tool if it is missing (`pip install harnice`) and runs `harnice -b` in the revision folder. If pip cannot install it, the agent clones https://github.com/harnice/harnice-cli and, still in the revision folder, runs `python3 /path/to/harnice-cli/src/harnice/__main__.py -b`. Python 3 is enough for a device build. The build reads `drawnby.json` before it runs `build.py`. If that file is missing, the agent asks what your drawn-by name usually is and writes that name with `-AGENT` appended. It reads the traceback, edits `build.py`, and runs the build again until the process exits 0 and the printed row count equals the number of signals it thinks the device has from the documentation, greater than zero. If it cannot run commands, it gives you the script and you run `harnice -b` there, or click **Build** in Harnice.

The signals list page reads `signals.tsv` in that same revision folder. `harnice -b` checks the rows. A header and no data rows still exits 0, so the prompt tells the agent to write the signals out and put `new()` immediately above those lines.

````markdown
# Harnice device signals-list prompt

## Documentation is in the package

The `harnice` command-line package includes the Harnice documentation,
including this prompt. Read those files for file formats, project layout,
and functions. Use that folder when you cannot open a website.

    harnice --docs

That prints the folder. If the `harnice` command is not on PATH:

    python3 /path/to/harnice-cli/src/harnice/__main__.py --docs

A clone of https://github.com/harnice/harnice-cli keeps the same folder at
`src/harnice/docs/`, next to `__main__.py`.

Start with `index.md`. A line `{% include-markdown "some/path.md" %}`
continues in that file, under the same folder.

The same pages are at https://harnice.io/ when you can reach the internet.


Write Harnice device **build instructions** (`build.py`) from the supporting
documentation. I may attach or paste it in this chat, or put it in the device
revision folder. Either way is enough. The output must be a complete, runnable
script. When the build is run in the revision folder, by you with `harnice -b`
or with `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` if the
`harnice` command is not available, or by me if you do not have Python
access, it must exit 0 and print a signal-row
count equal to the number of signals you think the device has from the
documentation. That count is greater than zero.

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

`configuration` can change the signals list between uses of the same device,
from `config.yaml` or from the system BOM. A different connector is a
different part number. Assume one signals list unless I say otherwise. If a
use might add, remove, or retype a signal, ask. If I name the cases, branch
only on those. Do not invent a mode.

Also ask what my drawn-by name usually is. Tell me you will append `-AGENT`
to that name. Do not invent the name, and do not ask me to type the suffix.

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

Run this after I have answered. Prefer the command-line package. It does
not include the Harnice window.

    pip install harnice

From the device revision folder (the folder that contains `build.py`,
usually `rev1/`):

    harnice -b

If pip cannot install Harnice, or `harnice` is not on PATH, stop trying to
install it. Clone the public command-line repo and run its entry file.
Stay in the revision folder. Do not set PYTHONPATH.

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
  greater than 0: show me the rows. You make that comparison when you
  read the output.
- Traceback, or N is 0, or N is some other count, or the line is missing:
  fix `build.py` and run the build again.

Do not stop after writing the file. Do not add `from harnice` imports to
make the command work. Those names are already in the build script.

If you cannot run a command, say so. Give me the script and tell me to run
`harnice -b` in the revision folder. Do not claim the build exited 0.


## What I was going for

A device in Harnice is its signals list. That list is the as-designed truth:
every signal, on a named channel, on a named connector cavity, with a channel
type Harnice already knows how to map. `build.py` is that list. It does not
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
comma separated). Treat the pasted rows as the supporting documentation.
Transcribe them into `append` calls, and cite the pasted table in a comment.
Do not write a parser that reads them back.

    connector_id	connector_mpn	owned_by	channel_id	repeat_channel_id	signal	cavity	channel_type_id	channel_type_repo
    J1	XLR3F	device	in1		pos	2	1	https://github.com/harnice/harnice
    J1	XLR3F	device	in1		neg	3	1	https://github.com/harnice/harnice
    A	DB25F	harness	ch0	A	pos	24	1	https://github.com/harnice/harnice
    B	DB25M	harness	ch0	B	pos	24	2	https://github.com/harnice/harnice

Column meanings:

- `connector_id` — name of the connector on this device (`J1`, `in1`, `A`)
- `connector_mpn` — manufacturer part number of that connector
- `owned_by` — `device` if the connector is on the device (use
  `device_connector_mpn`); `harness` if the harness owns that face (use
  `harness_connector_mpn`). Passthrough adapters are usually harness-owned.
- `channel_id` — one electrical channel. Same id on two connectors = a
  passthrough.
- `repeat_channel_id` — blank for a terminating (one-connector) channel.
  For a passthrough, two distinct values (convention: `A` and `B`).
- `signal` — must be a signal name of that channel type (see below)
- `cavity` — pin, socket, or stud on that connector. Unique per connector.
- `channel_type_id` + `channel_type_repo` — the Harnice channel type tuple


## Harnice names already in scope

Do **not** write `from harnice …`. Build instructions already have:

    signals_list, chtype, fileio, state, cli

and the rest of the lists / utils ribbon. You may `import` stdlib (`os`,
`csv`, `json`, `re`, `xml.etree.ElementTree`, `pathlib`).

`configuration` is a dict Harnice injects (defaults from `config.yaml`, or
the system BOM answers). Read it only after I have told you a use case that
changes the signals list. A different connector or a different cavity is a
new part number.


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
the functions that exist. Do not write `signals.tsv` with `open()`.

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
`https://github.com/harnice/harnice`. That combination looks up the public
file, finds no such id, `chtype.signals()` returns `[]`, and the signals
page stays empty after a successful build.

**If no channel-types table is attached,** the only legal types are the
public ones in Harnice's `channel_types.tsv` (`lib_repo` =
`https://github.com/harnice/harnice`):

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
        channel_type=(1, "https://github.com/harnice/harnice"),
        device_connector_mpn="XLR3F",
    )
    signals_list.append(
        channel_id="in1",
        signal="neg",
        cavity="3",
        connector_id="J1",
        channel_type=(1, "https://github.com/harnice/harnice"),
        device_connector_mpn="XLR3F",
    )
    print("Wrote 2 signal rows.")

Call this at module level. A `main()` that is never called leaves the
previous list untouched. `if __name__ == "__main__"` is fine: Harnice runs
the file as `__main__`.

If I confirmed a use case that changes the list, branch with a plain `if`
on `configuration` around those appends. Example: SM58 balanced vs
unbalanced changes channel type, not the XLR part number. If I said the
list does not change, there is no branch.

After you write it, run `harnice -b` if you can. A traceback is the review.
Fix that row. A script that prints `Wrote 0 signal rows.` or omits the line
is not finished.

Exit 0 means the file is valid. It does not mean the decisions match the
device. Show me what you wrote, with enough context that I can check it.
If I say something is wrong, ask and fix it.

If you could not run the command, show me the same thing from the script and
tell me to run `harnice -b`. Do not invent an exit code.


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
- Do not invent channel type ids.
- Do not point a company channel-type id at `https://github.com/harnice/harnice`.
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
- If you can run commands, you have run `harnice -b`, or
  `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` when the
  `harnice` command is missing. The process exited 0. The log
  contains `Wrote N signal rows.` where N is the number of signals you
  think the device has from the documentation, and N is greater than 0.
  If you cannot run commands, you said so and did not invent that result.
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
- [ ] Is `signals_list.new()` immediately above those appends, with no preflight between them?
- [ ] Are all `print()` statements ASCII-only (no checkmarks, crosses, bullets, or fancy quotes)?
- [ ] Do the comments cite the supporting documentation and record each decision and assumption, including a blatantly obvious mapping and the reason?
- [ ] Do all channel type tuples use the exact repo URL I provided?
- [ ] If you can run commands, did `harnice -b` or `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` print `Wrote N signal rows.` where N is the number of signals you think the device has from the documentation, and N is greater than 0? If you cannot, did you say so instead of inventing that result?
- [ ] Did you wait until I answered before writing the file, except for a blatantly obvious mapping you recorded in a comment?
- [ ] Did you ask what my drawn-by name usually is, and if `drawnby.json` was missing, write that name with `-AGENT` appended at the checkout root?
- [ ] Does the script match the decisions I made, including whether a use case changes the signals list?


## DONE CRITERIA

- [ ] Comments cite the supporting documentation. An absolute path I gave is a constant. The script does not parse that file at build time
- [ ] `signals_list.new()` is immediately followed by the appends a person can read
- [ ] The script does not check the rules that `harnice -b` already checks
- [ ] The script prints `Wrote N signal rows.` and `harnice -b` agrees
- [ ] No invented channel types; company ids use the human's `lib_repo`
- [ ] The script is straight-line module-level code, with no helper or nested function
- [ ] `harnice -b` or `python3 /path/to/harnice-cli/src/harnice/__main__.py -b` exited 0 with a row count equal to the number of signals you think the device has from the documentation, and that count is greater than 0, or you cannot run commands and you said so
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
5. How many signal rows the build printed, or that you could not run the build
6. Anything in the source you could not map (pins you skipped, types you need me to add)
7. Whether the signals list depends on configuration, and the cases I named
````

---

## Part family (library SKUs)

Copy the block below into a new agent chat in the **library** repo. Attach the how-to-order PDF (and a drawing or photo if overall length and max diameter are not tabulated). Add one sentence of intent, for example: `Family is Neutrik powerCON TRUE1 chassis connectors. Write into neutrik/.`

Review the catalog count before letting it emit thousands of folders. Run the generator with `--svg-only` first.

````markdown
# Harnice part-family prompt

## Documentation is in the package

The `harnice` command-line package includes the Harnice documentation,
including this prompt. Read those files for file formats, project layout,
and functions. Use that folder when you cannot open a website.

    harnice --docs

That prints the folder. If the `harnice` command is not on PATH:

    python3 /path/to/harnice-cli/src/harnice/__main__.py --docs

A clone of https://github.com/harnice/harnice-cli keeps the same folder at
`src/harnice/docs/`, next to `__main__.py`.

Start with `index.md`. A line `{% include-markdown "some/path.md" %}`
continues in that file, under the same folder.

The same pages are at https://harnice.io/ when you can reach the internet.


Encode a Harnice part family from the attached datasheet / how-to-order page.
Write Python that (1) chooses legal catalog part numbers and (2) generates one
Harnice project folder per SKU.

You are not drawing vendor CAD. You are encoding a how-to-order table plus a
low-fidelity envelope that SVG and STEP both share.


## What I was going for

Harnice should not make you draw ten thousand SKUs.

A catalog is a how-to-order table plus a few geometry envelopes. If you encode
the table as Python, you can:

1. Refuse illegal combinations. A chooser is a gate. If the spec does not sell
   that finish / insert / gender, the function raises. The library is the list
   of things that exist.
2. Pick a real part number from intent. Harness build instructions should say
   "mate this D38999" or "I need a 25-pin crimp D-sub, finish T" and get back a
   filesystem-safe MPN that library_utils.pull() can import.
3. Emit a first-class Harnice project per SKU. Attributes JSON, side-view
   drawing, low-fidelity STEP, revision history. Same project contract as a
   hand-built part.
4. Keep drawings and models honest. These are catalog envelopes, not vendor CAD.
   Tabulated dimensions get a source URL. Guessed interior stations get a
   comment that says so.
5. Put mating and accessory logic next to the catalog. D38999.find_backshell()
   exists so a harness rule can stay six lines long.

The point of a part family is not pretty 3D. It is deterministic selection plus
enough geometry that a drawing and a formboard stay consistent.


## Reference libraries

These three public libraries already did this the hard way. They are the
reference implementations. Keep their intent. Do not copy-paste their
thousand-line prologues.

- https://github.com/harnice/harnice-aerospace-library
  MIL-DTL-38999, Glenair Series 800, MIL-DTL-24308 / 83513, M85049 banding
  backshells, MIL-DTL-27500 cable, ASTM E1129 thermocouple plugs.
  Choosers: find_mating_connector(), find_backshell(), choose_part().

- https://github.com/harnice/harnice-av-library
  Neutrik XLR, etherCON, powerCON, TRS, speakON cable connectors.
  Catalog tables live inside the generator. No separate chooser yet — that is
  a gap. Do not repeat it.

- https://github.com/harnice/harnice-general-library
  NEMA WD-6 plugs, portable power cable, generic ring terminals.
  Choosers: choose_part(), find_mating_connector(), compatible_mates().


## What they all have in common

Every successful family does the same six jobs.

### 1. A closed catalog

Legal SKUs live in tables: finishes, shell styles, insert arrangements, NEMA
configs, Neutrik product lines, UL letter codes. A generator iterates only
those rows. It does not invent a 17-pin D-sub because the math would allow it.

M27500 is the extreme case: the full spec space is huge, so PERMUTATIONS is a
curated subset, then is_legal_configuration() still filters against Table II.

### 2. Parse, format, choose

Connectors that a harness will pick at build time expose a small API:

- parse_* — accept spaces, dashes, slashes, aliases (MS38999 -> D38999, male -> P)
- make_part_number / _format_pn — emit the library PN (filesystem-safe:
  D38999_26FG16SN, M24308_2-3T, OST-RS-M)
- return_divider — same fields, official punctuation when someone wants
  D38999/26FG16SN
- choose_part(...) — "I know the application, give me an MPN that exists"
- find_mating_connector(...) — flip gender / shell style, keep insert, finish,
  key. Overrides for the exceptions.
- find_backshell(...) / accessory helpers — when the family has a paired
  accessory series
- compatible_mates(...) — when mating is not 1:1 (NEMA T-slot 15 A into 20 A)

If a family has no chooser, harness rules fall back to a handwritten lookup
table. That is the Neutrik gap.

### 3. One configuration dict per SKU

Generators do not special-case part numbers in the emit loop. They build a
part_configuration / variant / cfg dict, then:

    make_part_number(cfg) -> compile_*_attributes(cfg) -> svg(cfg) -> step(cfg)

The same dict drives the revision-history description.

### 4. One envelope, two projections

Circular parts revolve (x, radius) stations about +X. Rectangular parts extrude
YZ polygons along +X. The SVG silhouette and the STEP solid come from that
same envelope, and they share a cable-side origin (x=0 at the rear /
cable-entry face, +X toward the mate). If they disagree, the family is wrong.

Iconic extras (Neutrik latch tongue, D38999 key, NEMA blades) are features on
the envelope, not a second model.

### 5. Attributes Harnice already knows how to read

Parts always write:

- tools — recommended tools; pulled onto the instance
- build_notes — use sparingly; only a specific technician action or a required value (torque, etc.)
- csys_children — named frames: 3d-mate (connectors), 3d-connector + connector
  (accessories), flagnote balloons
- contacts — connector cavities: [{"name": "A", "size": "20"}, ...]

Cables write a nested member tree (jacket -> shield -> conductors with
conductor: true) plus appearance. Harnice walks that tree into a conductor
list. Identifiers must be unique across the cable.

Family-specific keys (mass, datasheet, cable_od_mm, voltage) ride along. They
do not replace the keys above.

### 6. A batch driver that writes the library on disk

    {family}/
      {family}.py                 # chooser (import this from harness build instructions)
      {family}_generator.py       # emit SKUs
      {PN}/
        fileio.path("revision history")
        rev{N}/
          fileio.path("attributes")
          fileio.path("drawing")
          fileio.path("model")

The driver calls rev_history.part_family_append(), writes the files, then
builds the project (in-process part.build() on the newer aerospace families;
Build per folder on earlier ones). Progress bars and --step-only /
--svg-only / --no-build exist because regenerating 8,000 cables is a real job.


## What is still messy (do not repeat)

- Chooser and generator are not always split. Neutrik is one file. Always split.
- Harness imports are sys.path.append. There is no installable package layout
  yet. Do not invent a different import story until Harnice grows one.
- SVG primitives, ray-cast flagnotes, and the step_utils loader are copy-pasted
  into every generator.
- Older families picked a unique origin. Do not. Origin is always the cable
  side: x=0 at the rear / cable-entry face (or slightly inboard so accessory
  threads or knurl overlap −X), +X toward the mating or connector face.
  Drawing and STEP share that origin. Mating-face cups do not move it.
  Neutrik still balloons in Cartesian space about the mating face — that is
  a leftover, not a second origin. Name the origin in a comment.
- csys_children polar vs Cartesian. part.py currently ADDS x/y to
  angle/distance. Emit one or the other, never both.
- Some families write a catalog CSV, some do not. Always write one.
- Units mix. Stations for STEP are millimeters. Drawing csys is inches at
  96 px/in. Cable properties are inch strings ("0.064in"). Label every number.


## Goals for the next version

1. Shared part-family kit in Harnice (flagnote rays, SVG helpers, STEP write,
   revision-history row, progress bar, in-process build,
   cache_run_constant_lookups). Until that exists, keep the generator boring
   and local.
2. Two files, always. {family}.py is the chooser. {family}_generator.py is the
   emitter. Harness build instructions import only the chooser.
3. Import without path hacks (future). Today: sys.path.append to the family dir.
4. Chooser is mandatory for any family a harness rule would select.
   choose_part and/or find_mating_connector. Raise on illegal SKUs. Accept
   human aliases.
5. Cable-side origin, always. x=0 at the rear / cable-entry face (knurl end,
   accessory thread, insulator rear). +X toward the mating or connector face.
   Cable, knurl, and accessory threads overlap −X. Drawing and STEP share this
   origin. Pin / mating cups stay at the mating face — they do not move the
   part origin. Document it in a comment. Emit 3d-mate on connectors; emit
   3d-connector and connector on accessories. Emit flagnote-N and
   flagnote-N-leader_dest from the silhouette.
6. Exclusive csys coordinates. Polar OR Cartesian, not both. Polar about the
   origin when a ~3 in circle clears the body (D38999). For long or angled
   parts, shoot rays from the silhouette centroid and store the results as
   cartesian x/y (M85049). Do not invent a second origin at the mating face
   just to place balloons.
7. One geometry source. Stations or prisms compile to SVG and STEP. Cite
   datasheet vs estimate on every station that is not a callout.
8. Only commercially real SKUs. Curate the permutation space. Filter again.
   Prefer "this McMaster / Omega / Neutrik number exists" over a theoretically
   complete matrix.
9. Family catalog CSV at the family root, same columns the chooser understands.
10. Agent-first authoring. This prompt plus a datasheet should be enough to
    generate a family that a human can review.


## OUTPUT FILES (exactly two, plus generated SKUs)

In the family directory of the target library repo:

    {family}.py                 # CHOOSER — no file I/O, importable by harness scripts
    {family}_generator.py       # EMITTER — run to write SKUs

Do not merge them. Do not put harness-time logic in the generator.
Do not import the generator from a harness.

Each SKU folder:

    {PN}/
      fileio.path("revision history")
      rev{REVISION}/
        fileio.path("attributes")
        fileio.path("drawing")                  # parts
        fileio.path("model")                    # parts
        fileio.path("conductor list")           # cables only

Filesystem-safe PNs: replace / with _. Official punctuation is a
return_divider option on the chooser, not the folder name.

Constants:

    REVISION = "1"
    DATE_STARTED = "<today>"
    LIBRARY_REPO = "https://github.com/<org>/<repo>"
    LIBRARY_SUBPATH = "<dir between library root and this family>"
    MANUFACTURER = "<name or 'mil spec' or ''>"

Chooser is imported today via:

    import sys
    sys.path.append(os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH, "{family}"))
    import {family}


## PHASE 1 — CATALOG (do this first, before any SVG)

1. Read the how-to-order / catalog page.
2. List every axis that changes the part number:
   series / slash sheet / shell style, size (shell, insert, AWG, amps),
   gender / contact type, finish / plating / housing color, keyway,
   termination (crimp, solder, pigtail, screw), accessory options
   (entry size, orientation, detent).
3. Write tables of only commercially sold values. If the spec matrix is huge,
   curate a default PERMUTATIONS subset AND keep a legality filter.
4. Cite the source URL in a comment on each table. If a dimension is scaled
   from a drawing rather than tabulated, write estimate: in the comment.
5. Implement:

    iter_part_configurations() -> yields one dict per legal SKU
    make_part_number(cfg) -> filesystem-safe PN
    official_pin(cfg) -> optional official spelling
    description_from_cfg(cfg) -> ALL CAPS catalog sentence

Example iterator:

    def iter_part_configurations():
        for family in FAMILIES:
            for amps in family["amps"]:
                for gender in GENDERS:
                    yield {"spec": family, "amps": amps, "gender": gender}

Stop and list the configuration count + a few sample PNs before drawing.


## PHASE 2 — CHOOSER (`{family}.py`)

Small module. re + dicts. No disk, no Harnice project build.

Required as applicable:

    parse_*(part_number) -> dict of fields
    choose_part(...) -> library PN from application (pins, voltage, type, ...)
    find_mating_connector(part_number, **overrides) -> mate PN
    find_backshell(...) / accessory helper if a paired family exists
    compatible_mates(part_number) if mating is not 1:1
    list_*() for docs and tests

Rules:
- Accept aliases: spaces, dash vs underscore vs slash, male/plug/P,
  MS vs MIL-DTL prefixes.
- Default to the library PN (_ instead of /, OST-RS-M instead of OST-R/S-M).
- return_divider switches punctuation for official PINs that are illegal as
  folder names.
- Default mate: reverse gender, keep insert/finish/key, apply the family's
  shell-style map (26 -> 24). Every default must be overridable.
- Raise ValueError naming the legal set. Never silently coerce.
- Module docstring: one harness-build snippet showing instances_list.modify
  with lib_repo + lib_subpath.

How a harness uses it:

    for instance in instances_list.read():
        if instance.get("item_type") != "harness_connector":
            continue
        device_mpn = instance.get("device_side_connector_mpn") or ""
        if not device_mpn.startswith("D38999"):
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": D38999.find_mating_connector(device_mpn),
                "lib_repo": "https://github.com/harnice/harnice-aerospace-library",
                "lib_subpath": "D38999",
            },
        )

A later loop library_utils.pull()s every connector that has lib_repo set.
The chooser only has to return a PN that exists under lib_subpath.

If this family is a mate or accessory of an existing family, add
find_mating_connector / find_backshell on THAT chooser as well, the way
D38999.find_backshell returns an M85049-... PN.


## PHASE 3 — ATTRIBUTES

compile_part_attributes(cfg) / compile_cable_attributes(cfg).

Parts MUST include:

    tools: list[str]
    build_notes: list[str]
    csys_children: dict
    contacts: list[{"name": <cavity>, "size": <awg|termination>}]   # connectors

Build notes should be used sparingly and written only when a technician must
take a specific action when assembling this part, or when the part requires a
specific value (torque value, etc). Basic assumptions about beginner or
intermediate workmanship knowledge can be made when deciding what should be a
build note.

Use the cavity names from the spec (1..n, A/B/C, L/N/PE, T/R/S).

Cables MUST be a nested member tree:

    each container key holds an object
    conductors have "conductor": true, "properties", "appearance"
    identifier (the conductor key) is unique across the whole cable
    properties use inch strings where dimensional ("0.064in", "16AWG")
    appearance uses base_color / parallelstripe / perpstripe / outline_color

If two conductors would share a color name, namespace the key (pair_1_black).

    {
        "jacket": {
            "properties": {"material": "neoprene", "od": "0.430in", "voltage": "600 V AC"},
            "black": {
                "conductor": True,
                "properties": {"gauge": "16AWG", "od": "0.111in", "material": "copper"},
                "appearance": {"base_color": "black"},
            },
            "white": {
                "conductor": True,
                "properties": {"gauge": "16AWG", "od": "0.111in", "material": "copper"},
                "appearance": {"base_color": "white", "outline_color": "black"},
            },
        }
    }

Optional but preferred: mass + mass_source URL, datasheet URL, mfg, family,
series, voltage, cable_od range, finish name.

Revision history via rev_history.part_family_append(row, path):

    {
        "project_type": "part",          # or "cable"
        "mfg": MANUFACTURER,
        "pn": part_number,
        "rev": REVISION,
        "desc": description_from_cfg(cfg),   # ALL CAPS, catalog voice
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
    }

part_family_append fills datemodified, drawnby, and git_hash_of_harnice_src.
Same rev updates the existing row.

Set state.set_project_type(...) and state.set_rev(...) once at the start of main().


## PHASE 4 — GEOMETRY (one envelope, two projections)

Origin is always the cable side. Name it in a comment: which rear face is
x=0, +X toward the mating / connector face, what overlaps −X.

Recipe:
1. Put x=0 on the cable-side face (rear accessory, knurl end, or
   cable-entry insulator). A small inboard offset is fine so threads or
   knurl overlap −X. Drawing and STEP use this same origin. Mating-face
   cups stay at the face — they do not move x=0.
2. Build the envelope as stations (round) or prisms (rectangular).
3. Add the one or two features a human uses to recognize the part
   (latch, blades, key).
4. Derive the SVG silhouette from that envelope.
5. Derive the STEP from that envelope.
6. Derive flagnote leaders from that silhouette.

Round parts: list of (x_mm, radius_mm) stations, revolve about +X.
Rect parts: list of (x0_mm, x1_mm, yz_polygon_mm), extrude along +X.

SVG:
- 400x400, xmlns, groups {pn}-drawing-contents-start / -end
- 96 px = 1 inch; store +Y up; emit SVG y as -y
- silhouette from the same envelope; knurl = clipped <line>s, not <pattern>
- stroke outer outline last
- you may overlay csys markers for debug; the part build will also draw
  csys_children

STEP via harnice.utils.step_utils:

    write_revolution_step(path, pn, stations)
    write_prism_segments_step(path, pn, segments)
    write_elbow_step(...) for 45/90 backshells

If harnice.utils is not importable, load src/harnice/utils/step_utils.py by
path the way existing families do. Do not vendor a second STEP writer.
If OpenCascade is missing, those helpers fall back to a triangle STEP. Fine.

Do not model threads, knurl as 3D, or contacts as pins unless the family is a
plug whose mating face IS the project (NEMA, TRS).
Do not trace a vendor STEP into a pretty model. Low fidelity that matches the
datasheet overall length and max diameter is the contract.


## PHASE 5 — CSYS

Values for 2D csys are inches and degrees.

Emit EITHER polar {angle, distance, rotation} OR cartesian {x, y, rotation}.
Never both on the same child (part.py currently adds them).

Use polar about the cable-side origin when a ~3 in circle clears the
silhouette (D38999, Mighty Mouse, D-sub):

    "flagnote-1": {"angle": 0, "distance": 3.0, "rotation": 0}
    "flagnote-1-leader_dest": {"angle": 0, "distance": 0.98, "rotation": 0}

For long or angled parts whose origin sits at the knurl / cable-entry end
(M85049), shoot rays from the silhouette centroid and store absolute x/y.
Do not move the part origin to the mating face just to place balloons:

    "leader_center": {"x": 0.8, "y": 0.3, "rotation": 0}
    "flagnote-1": {"x": 4.2, "y": 1.1, "rotation": 0}

Required 2D children:
    flagnote-1 .. flagnote-13 at 0, ±15, ±30, ±45, ±60, ±75, ±90
    flagnote-N-leader_dest on the silhouette (ray from an interior anchor;
    take the farthest intersection)
    leader_center when rays are not about the part origin

When the family mates to a connector, accessory, or cable:

    "3d-mate": {"x": 1.23, "y": 0, "z": 0, "rx": 0, "ry": 0, "rz": 0}   # connectors: mating face
    "3d-connector": { ... }   # accessories: coupling face in 3D
    "connector": {"x": ..., "y": ..., "rotation": 180}   # accessories: coupling face in 2D

3D mates: x, y, z and rx, ry, rz.


## PHASE 6 — EMIT LOOP (`{family}_generator.py`)

    from harnice.lists import rev_history
    from harnice import state, fileio
    import harnice.project_types.part as part   # or cable

    REVISION = "1"
    DATE_STARTED = "<today>"
    LIBRARY_REPO = "https://github.com/you/your-library"
    LIBRARY_SUBPATH = "my_family"

    def main(step_only=False, svg_only=False, build=True):
        state.set_rev(REVISION)
        state.set_project_type("part")
        family_dir = os.path.dirname(os.path.abspath(__file__))
        variants = list(iter_part_configurations())
        for i, cfg in enumerate(variants, start=1):
            pn = make_part_number(cfg)
            part_dir = os.path.join(family_dir, pn)
            rev_dir = os.path.join(part_dir, f"rev{REVISION}")
            os.makedirs(rev_dir, exist_ok=True)
            rev_history.part_family_append(revision_history_row(cfg), ...)
            # write attributes, svg, step
            if build and not (step_only or svg_only):
                build_part(pn, rev_dir)   # in-process; avoid subprocess per SKU
            print(progress_bar(i, len(variants)))

Prefer in-process build (set state, part.generate_structure(), part.build())
over a separate Build per SKU.

Cache fileio.get_git_hash_of_harnice_src and fileio.drawnby once per run.
part_family_append otherwise shells out to git on every SKU.

Driver flags:
    --step-only  --svg-only  --no-build
    plus a filter flag if the catalog is large (--xlr-only, --24-only, ...)

Print a text progress bar. At the family root, write a catalog CSV whose
columns match the chooser fields.


## HARD RULES

- Only SKUs the manufacturer sells.
- Chooser PNs must be a subset of generator PNs.
- SVG and STEP from the same envelope, same cable-side origin.
- Origin is always the cable side. Mating-face cups do not move it.
- No secrets, no scraped paywalled HTML dumps — use the attached datasheet.
- Do not invent Harnice APIs. Read the folder from `harnice --docs` before
  you guess a function. The same pages are at https://harnice.io/ when you
  can reach the internet. Use rev_history.part_family_append, state,
  fileio, step_utils, project_types.part / project_types.cable as they exist.
- Keep the chooser free of drawing code.
- Description voice: ALL CAPS, "CONNECTOR, ..." / "CABLE, ..."


## DONE CRITERIA

- [ ] Chooser parses official and library PNs, rejects illegal ones
- [ ] choose_part / find_mating_connector return PNs that the generator emits
- [ ] Every emitted folder has revision history, attributes, drawing, and model
      (cables: attributes + conductor list)
- [ ] SVG and STEP share an envelope and a cable-side origin
- [ ] contacts or cable identifiers match the spec names
- [ ] lib_repo + lib_subpath on the revision row match the library
- [ ] A harness snippet in the module docstring shows instances_list.modify
- [ ] Datasheet URLs sit on tables and on datasheet / mass_source fields
- [ ] You did not generate SKUs the manufacturer does not sell

Reply with:
1. Configuration count and 5 example library PNs
2. Origin convention (one sentence: cable side, +X toward mate)
3. Paths of the two Python files
4. How a harness script should import and call the chooser
5. Any dimension that is an estimate rather than a callout
````

