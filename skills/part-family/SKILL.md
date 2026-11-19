---
name: part-family
description: >-
  Encode a Harnice part family from a how-to-order datasheet into library
  SKUs: a chooser and one project folder per catalog number. A part or cable
  SKU is a drawing and a model. A device SKU is a device project whose
  build.py writes the signals list. Use when the user asks for a part family,
  catalog SKUs, a how-to-order table turned into a library, or a catalog of
  devices. One device pinout uses the device-signals-list skill. Follow this
  skill when it is the best match. Do not ask which skill to follow. If the
  request is not clear, ask for clarification.
---

# Harnice part-family prompt

Follow this skill when it is the best match for what I asked. Do not ask which skill to follow. If it is not clear what I am asking, ask me to clarify.

Before you follow the rest of this skill, pull the latest `main` from the skills repository, https://github.com/harnice/harnice-cli. Check out `main` in that clone and pull. Read this file again after the pull. If you cannot pull, stop and tell me to pull that repository to the latest `main`. Wait until I have, then read this file again from that `main`.

When you write a path to reference material, write it with respect to the library folder if one is available. Use library locations to establish where you are, then write `(url)/path/file`. Library locations are `repository_locations.csv`. The first column is the library URL. The second column is the local checkout. `url` is the URL of the checkout that contains the file. `path/file` is the path under that checkout. A file outside every checkout keeps the path I gave you.

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


Encode a Harnice part family from the attached datasheet / how-to-order page.
Write Python that (1) chooses legal catalog part numbers and (2) generates one
Harnice project folder per SKU.

A family is parts, cables, or devices. Pick one project type and stay with it.

A part or cable family is a how-to-order table plus a low-fidelity envelope
that SVG and STEP both share. You are not drawing vendor CAD.

A device family is a how-to-order table of devices. Each SKU is a device
project. `build.py` writes the signals list. One pinout for one device is
`skills/device-signals-list/SKILL.md`. A catalog of device part numbers is
this skill. The pinout rules inside each `build.py` are that skill. A body
on those devices is `skills/cad/SKILL.md`, written into each `build.py`.
A missing channel type is `skills/channel-type/SKILL.md`, then come back here.


## What I was going for

Harnice should not make you draw ten thousand SKUs.

A catalog is a how-to-order table. Parts and cables add a few geometry
envelopes. A device catalog is the same table: one device project per part
number, and a body only when I ask for one. If you encode the table as
Python, you can:

1. Refuse illegal combinations. A chooser is a gate. If the spec does not sell
   that finish / insert / gender, the function raises. The library is the list
   of things that exist.
2. Pick a real part number from intent. Harness build instructions should say
   "mate this D38999" or "I need a 25-pin crimp D-sub, finish T" and get back a
   filesystem-safe MPN that library_utils.pull() can import.
3. Emit a first-class Harnice project per SKU. A part gets attributes, a
   side-view drawing, a low-fidelity STEP, and revision history. A cable gets
   attributes, a conductor list, and revision history. A device gets
   attributes, `build.py`, a signals list the build writes, and revision
   history. Same project contract as a hand-built project of that type.
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

None of those libraries is a device family. A device family still does the
six jobs below. It does not copy a connector generator's drawing loop.
The signals list inside each device SKU follows
`skills/device-signals-list/SKILL.md`.


## What they all have in common

Every successful family does the same six jobs.

### 1. A closed catalog

Legal SKUs live in tables: finishes, shell styles, insert arrangements, NEMA
configs, Neutrik product lines, UL letter codes. A generator iterates only
those rows. It does not invent a 17-pin D-sub because the math would allow it.

M27500 is the extreme case: the full spec space is huge, so PERMUTATIONS is a
curated subset, then is_legal_configuration() still filters against Table II.

### 2. One chooser function

A harness picks a part at build time by calling the family's chooser:

- choose_part(...) — "I know the application, give me an MPN that exists"
- find_mating_connector(...) — only when the family has a catalog mate
- find_backshell(...) — only when the family has a paired accessory series
- compatible_mates(...) — only when mating is not 1:1 (NEMA T-slot 15 A into 20 A)

Library PNs are filesystem-safe: D38999_26FG16SN, M24308_2-3T, OST-RS-M.

If a family has no chooser, harness rules fall back to a handwritten lookup
table. That is the Neutrik gap.

### 3. One configuration dict per SKU

Generators do not special-case part numbers in the emit loop. They build a
part_configuration / variant / cfg dict, then:

    make_part_number(cfg) -> compile_*_attributes(cfg) -> svg(cfg) -> step(cfg)

The same dict drives the revision-history description.

### 4. One envelope, two projections

Parts and cables. A device family skips this section. Its solid, when I ask
for one, is a body in `build.py` (`skills/cad/SKILL.md`).

Circular parts revolve (x, radius) stations about +X. Rectangular parts extrude
YZ polygons along +X. The SVG silhouette and the STEP solid come from that
same envelope, in the frame of the drawing contract (phase 4). If they
disagree, the family is wrong.

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

Devices write `default_refdes`. The device build fills `mate_connectors`
from the signals-list `connector_id`s. Leave that key to the build. Extra
keys (mass, datasheet, family) may ride along.

### 6. A batch driver that writes the library on disk

    {family}/
      {family}.py                 # chooser (harness scripts, or Place device)
      {family}_generator.py       # emit SKUs
      {PN}/
        fileio.path("revision history")
        rev{N}/
          fileio.path("attributes")
          fileio.path("drawing")            # parts
          fileio.path("model")              # parts
          fileio.path("conductor list")     # cables
          fileio.path("build instructions") # devices; the build writes the signals list

The driver calls rev_history.part_family_append(), writes the files, then
builds each SKU with `harnice -b` from that revision folder. Do not use
in-process part.build() / cable.build() / device.build() as the check.
Do not suppress errors from that build: no `check=False`, no swallowed
stderr, no catch-and-continue past a nonzero exit. A failed `harnice -b`
stops the family and the traceback is the review. Progress bars and
--step-only / --svg-only / --no-build exist because regenerating 8,000
cables is a real job. A device family uses --no-build and a filter flag.
It does not grow --step-only or --svg-only.


## What is still messy (do not repeat)

- Chooser and generator are not always split. Neutrik is one file. Always split.
- Older families keep catalog tables in the chooser and again in the
  generator, and grow parse_*, list_*, and return_divider helpers that no
  harness calls. Do not. One source of truth (phase 1), one chooser
  function (phase 2).
- Harness imports are sys.path.append. There is no installable package layout
  yet. Do not invent a different import story until Harnice grows one.
- SVG primitives, ray-cast flagnotes, and the step_utils loader are copy-pasted
  into every generator.
- Older families picked a unique origin. Do not. The origin is the drawing
  contract in phase 4. Neutrik still balloons in Cartesian space about the
  mating face — that is a leftover, not a second origin.
- csys_children polar vs Cartesian. part.py currently ADDS x/y to
  angle/distance. Emit one or the other, never both.
- Some families write a catalog CSV, some do not. Always write one.
- Units mix. Stations for STEP are millimeters. Drawing csys is inches at
  96 px/in. Cable properties are inch strings ("0.064in"). Label every number.


## Goals for the next version

1. Shared part-family kit in Harnice (flagnote rays, SVG helpers, STEP write,
   revision-history row, progress bar, `harnice -b` per SKU,
   cache_run_constant_lookups). Until that exists, keep the generator boring
   and local.
2. Three files, always. {family}.py is the chooser. {family}_generator.py is
   the emitter. {family}.csv is the catalog. Harness build instructions
   import only the chooser. A device chooser is what Place device's MPN
   comes from. Do not import the generator from a harness or a system.
3. Import without path hacks (future). Today: sys.path.append to the family dir.
4. Chooser is mandatory for any family a harness rule or a system placement
   would select. choose_part, and find_mating_connector when the family has a
   mate. Raise on illegal SKUs. Accept human aliases.
5. Cable-side origin, always, for parts and cables: the drawing contract in
   phase 4. Emit 3d-mate on connectors; emit 3d-connector and connector on
   accessories.
   Emit flagnote-N and flagnote-N-leader_dest from the silhouette. A device
   family skips this goal.
6. Exclusive csys coordinates, for parts and cables. Polar OR Cartesian, not
   both. Polar about the origin when a ~3 in circle clears the body (D38999).
   For long or angled parts, shoot rays from the silhouette centroid and store
   the results as cartesian x/y (M85049). Do not invent a second origin at the
   mating face just to place balloons. A device family skips this goal.
7. One geometry source, for parts and cables. Stations or prisms compile to
   SVG and STEP. Cite datasheet vs estimate on every station that is not a
   callout. A device body, when I ask for one, follows `skills/cad/SKILL.md`
   inside `build.py`.
8. Only commercially real SKUs. Curate the permutation space. Filter again.
   Prefer "this McMaster / Omega / Neutrik number exists" over a theoretically
   complete matrix.
9. Family catalog CSV at the family root. It is the only file the chooser reads.
10. Agent-first authoring. This prompt plus a datasheet should be enough to
    generate a family that a human can review.


## OUTPUT FILES (three, plus generated SKUs)

In the family directory of the target library repo:

    {family}.py                 # CHOOSER — outward-facing. Harness and system scripts import it. Reads only {family}.csv
    {family}_generator.py       # GENERATOR — library maintenance only. Run by hand to write SKUs. Nothing imports it
    {family}.csv                # CATALOG — one row per SKU, with a library_pn column

Do not merge the chooser and the generator. Do not put harness-time logic
in the generator. Do not import the generator from a harness, a system, or
the chooser. The generator may import the chooser's constants.

Each SKU folder for a part or cable:

    {PN}/
      fileio.path("revision history")
      rev{REVISION}/
        fileio.path("attributes")
        fileio.path("drawing")                  # parts
        fileio.path("model")                    # parts
        fileio.path("conductor list")           # cables only

Each SKU folder for a device:

    {PN}/
      {PN}-revision_history.tsv
      rev{REVISION}/
        build.py                                # you write this; the signals list is the script
        attributes.json                         # default_refdes, plus family keys
        config.yaml                             # only when this SKU has setup that keeps the hardware
        signals.tsv                             # the device build writes this; you do not
        symbol.svg                              # the device build writes this; you do not
        body.step                               # only when I asked for a body; build.py writes it via cad

Filesystem-safe PNs: replace / with _. When a harness needs the official
punctuation, it is an `official_pn` column in the CSV, not the folder name.

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

1. Read the how-to-order / catalog page. For a device family, also read the
   pinout, ICD, or spreadsheet for each hardware variant.
2. List every axis that changes the part number:
   series / slash sheet / shell style, size (shell, insert, AWG, amps),
   gender / contact type, finish / plating / housing color, keyway,
   termination (crimp, solder, pigtail, screw), accessory options
   (entry size, orientation, detent). For a device: connector count, insert,
   range, or any other hardware the catalog sells as a different part number.
3. Write tables of only commercially sold values, in the one source of
   truth below. If the spec matrix is huge, curate a default PERMUTATIONS
   subset AND keep a legality filter.
4. Cite the source on each table: a comment in the generator, or a
   `source` column in the CSV. A file inside a library folder is
   `(url)/path/file`. A page on the web stays a URL. If a dimension is
   scaled from a drawing rather than tabulated, say estimate: in that
   comment, or name the column in that row's `notes` column.
5. In the generator, implement:

    iter_part_configurations() -> yields one dict per legal SKU
    make_part_number(cfg) -> filesystem-safe PN (only when the generator is the source)
    description_from_cfg(cfg) -> ALL CAPS catalog sentence

Example iterator:

    def iter_part_configurations():
        for family in FAMILIES:
            for amps in family["amps"]:
                for gender in GENDERS:
                    yield {"spec": family, "amps": amps, "gender": gender}

A setup that keeps the hardware is one device, and it belongs in that SKU's
`config.yaml`. Gain, a dip switch, and a preset are configurations. A
different connector, or any other hardware change, is a different part
number. If every row would be the same hardware, stop and follow
`skills/device-signals-list/SKILL.md` for that one device.

Stop and list the configuration count + a few sample PNs before drawing,
and before writing any device `build.py`.

### One source of truth

Every legal SKU, its fields, its part number, and every datasheet number
the family uses live in exactly one file. Pick one, and name it in a
comment at the top of the chooser and the generator:

- `{family}.csv`, when the catalog is a list of rows you could type: eight
  ferrule sizes, a dozen NEMA configurations. You write the CSV by hand,
  `library_pn` column included. The generator reads it.
- `{family}_generator.py`, when the catalog is a product of axes with a
  legality filter: D38999, M27500. The tables live in the generator. The
  generator writes `{family}.csv`, `library_pn` column included.

Either way, the chooser reads `{family}.csv` and nothing else. Never copy a
table, a dimension, or a part-number format into a second file. A catalog
change is one edit, then a rerun of the generator.

### Ask me before drawing

Ask me in that same message when any of these is not plain from what I
gave you. Ask them all at once. Do not pick an answer yourself, and do not
draw until I answer. An answer I give covers every SKU it applies to.

- Where x = 0 is, when the part has no obvious cable-entry face and I did
  not mark or name one.
- Which end is the mating end, and whether the part gets a `3d-mate` at all.
- Whether the part gets `contacts`, when it is not a connector with
  cavities.
- A dimension the drawing needs that the datasheet does not give, such as
  a diameter. Do not measure it off a picture or a scanned drawing unless I
  say to. When I do, mark it `# estimate` and say which sizes came out out
  of order.
- The manufacturer, when the datasheet does not name one.
- Anything else where you would have to guess about the part itself.

A blatantly plain answer is not a question. Write it in a comment.
An online chatbot asks the same questions and waits.


## PHASE 2 — CHOOSER (`{family}.py`)

The chooser is the one file in the family that anything outside the
library imports. Harness and system build scripts call it. Write it for
them: short, plain, and obviously about one function.

    """{Family} chooser. Harness and system build scripts import this file.

    Call choose_part(...) to get a library part number that exists.
    {family}_generator.py is for rewriting the library only. Never import it.

    <one harness-build snippet: instances_list.modify with lib_repo + lib_subpath>
    """
    import csv
    import os

    LIBRARY_REPO = "https://github.com/<org>/<repo>"
    LIBRARY_SUBPATH = "<dir between library root and this family>"


    def choose_part(...):
        ...

Rules:
- `choose_part(...)` is the main function. It comes first, right after the
  constants. It takes what a harness author knows (gauge, pins, gender,
  finish) and returns a `library_pn` from `{family}.csv`.
- It reads `{family}.csv` from its own folder, keeps the rows that match,
  and returns one `library_pn`. It never builds a part number from fields
  and never holds its own copy of the catalog.
- Inline everything. Alias cleanup (spaces, dash vs underscore vs slash,
  `#18`, `18AWG`, male/plug/P, MS vs MIL-DTL), the CSV read, and the
  legality check go inside `choose_part`. A helper stays only when two
  public functions call it.
- Raise ValueError naming the legal values when no row matches. Never
  silently coerce.
- No other public function, unless the family has a catalog mate
  (`find_mating_connector(part_number, **overrides)`), a paired accessory
  (`find_backshell(...)`), or mating that is not 1:1
  (`compatible_mates(part_number)`). Each one is a row lookup in the same
  CSV. No parse_*, list_*, official_pin, or make_part_number here.
- Default mate: reverse gender, keep insert/finish/key, apply the family's
  shell-style map (26 -> 24). Every default must be overridable.

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

A device chooser returns the device PN a system places. It does not flip
gender. Add find_mating_connector only when this device is a catalog mate
of another family. The connectors on the device stay
`device_connector_mpn` on the signals list, and those connector families
keep their own choosers.

How a system uses a device chooser. Place device stores these on the symbol:

    MPN          choose_part(...)
    lib_repo     LIBRARY_REPO
    lib_subpath  LIBRARY_SUBPATH
    rev          REVISION

A system build reads a placed device with
system_utils.mpn_of_device_refdes(refdes). The chooser only has to return
a PN that exists under lib_subpath. The module docstring shows that place
block, not instances_list.modify.


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
        "project_type": "part",          # or "cable", or "device"
        "mfg": MANUFACTURER,
        "pn": part_number,
        "rev": REVISION,
        "desc": description_from_cfg(cfg),   # ALL CAPS, catalog voice
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
    }

part_family_append fills datemodified, drawnby, and harnice_version.
Same rev updates the existing row.

Set state.set_project_type(...) and state.set_rev(...) once at the start of main().
A device family sets state.set_project_type("device").

Device attributes:

    {"default_refdes": "U"}

Ask me for the prefix when the documentation does not name one. Description
voice for a device is ALL CAPS, "DEVICE, ...".

Write `config.yaml` only when that SKU has setup that keeps the same
hardware. Field types are `docs/fragments/configurations.md`. Leave the file
out when there is no setup. The device build writes the empty default.

Do not write `signals.tsv`, `symbol.svg`, or `body.step` in this phase.
`build.py` is phase 6, and it follows `skills/device-signals-list/SKILL.md`.


## PHASE 4 — GEOMETRY (parts and cables)

A device family skips phases 4 and 5 and goes to phase 6.

### Drawing contract

Every part drawing and STEP uses this one frame. A harness places the part
by its origin and points it along +X. A drawing that breaks the frame puts
the part in the wrong place, or backwards, on every harness that uses it.

    part frame (mm or in, +Y up)                SVG frame (px, +Y down)
                     +Y                         x_svg =  96 * x_in
                      ^                         y_svg = -96 * y_in
       cable ===[=====|============]> mating face
                ^     O------> +X               O is (0, 0) in both frames
                |     origin: cable-entry face, on the axis
                anything may extend into -X

- x = 0 is where I mark or say it is. When I have not, it is the
  cable-entry face: the rear accessory face, the knurl end, or the
  cable-entry insulator. Most of a part is in +X, but threads, knurl,
  or anything else may extend into -X by any amount. Pin and mating cups
  stay at the mating face. They do not move x = 0.
- +X points from the cable toward the mating face. The mating face is the
  largest x in the drawing. A connector's `3d-mate` x is that same number.
  A terminal's `3d-mate` is where its stud goes.
- The axis is y = 0. A round part is symmetric about it. A latch or a tab
  may stand off one side. The top edge of a body of radius r is SVG y = -r.
- Side view only. The mating face is not drawn face-on.
- No `transform` anywhere inside the `{pn}-drawing-contents` group. No
  translate, rotate, scale, or matrix. Do not center the part on the
  400x400 canvas. Negative coordinates are expected. Harnice reads the
  group, not the canvas.
- Shapes are rect, circle, ellipse, line, polyline, polygon, path, and
  text. Knurl is lines you clip to the body in Python, not a `<pattern>` or
  a clip path. Stroke the outer outline last.
- Fill colors come from a palette dict keyed by role (body, knurl,
  insulator, rim, seal). Only the finish table holds hex values.
- The SVG is 400x400 with xmlns and the groups
  `{pn}-drawing-contents-start` and `{pn}-drawing-contents-end`. The part
  build draws `csys_children` on top. Do not draw them yourself.

### Reference pictures

I may give you a screenshot, a photo, or a vendor drawing of what the
family should look like. It shows the look, not the numbers.

- Take from it which features to draw, the colors, and how much detail.
- Take every dimension from the datasheet. A dimension the datasheet does
  not give is a question for me (Ask me before drawing, phase 1).
- Never copy pixel positions from the picture into the drawing.
- Turn the reference into the drawing frame before you draw. Many vendor
  drawings put the mating face on the left or draw it face-on. Say in one
  line how the reference is oriented and how you turned it: "Reference has
  the mating face on the left; mirrored so the cable is at x = 0."
- A reference that only shows the mating face, face-on, tells you colors and
  features. The side view still comes from the datasheet.
- When I mark the origin on a reference, or say where it is, that is x = 0.
  It wins over the cable-entry face. Do not ask.

Write the origin in one comment before any geometry: "Cable enters at
x = 0 on the left. Mating face at x = L on the right. Key at +Y." Then:

1. Name the stations. One block of x positions along the axis, before any
   shape, each with its datasheet letter or `# estimate`:

       x_rear   = 0.0                          # origin: cable-entry face
       x_flange = cable_side_mm(v)             # datasheet K
       x_mate   = x_flange + FLANGE_MM + shroud_mm(v)  # datasheet G
       assert x_rear <= x_flange < x_mate

   Every shape, every csys child, and the STEP read these names. `3d-mate`
   x is `x_mate`. Do not work out the same position a second way.
2. Build the envelope as stations (round) or prisms (rectangular), from
   those names.
3. Add the one or two features a human uses to recognize the part
   (latch, blades, key).
4. Derive the SVG silhouette from that envelope. Convert to pixels and flip
   Y in one place in the generator, for example `px(mm)` and a function
   that turns a part-frame box `(x0, x1, y0, y1)` into a `<rect>`. No shape
   does its own conversion or its own minus sign.
5. Derive the STEP from that envelope.
6. Derive flagnote leaders from that silhouette.

Round parts: list of (x_mm, radius_mm) stations, revolve about +X.
Rect parts: list of (x0_mm, x1_mm, yz_polygon_mm), extrude along +X.

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


## PHASE 5 — CSYS (parts and cables)

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
    take the farthest intersection). A ray between two blades or pins
    can end in the air. `harnice --check-drawing` fails a leader that is
    more than 0.05 in off the outline. Move that leader onto the body.
    leader_center when rays are not about the part origin

When the family mates to a connector, accessory, or cable:

    "3d-mate": {"x": 1.23, "y": 0, "z": 0, "rx": 0, "ry": 0, "rz": 0}   # connectors: mating face
    "3d-connector": { ... }   # accessories: coupling face in 3D
    "connector": {"x": ..., "y": ..., "rotation": 180}   # accessories: coupling face in 2D

3D mates: x, y, z and rx, ry, rz.


## PHASE 6 — EMIT LOOP (`{family}_generator.py`)

The generator is for library maintenance only. Start it with a docstring
that says so: "Rewrites this family's SKUs. Run by hand when the catalog
changes. Harness and system scripts never import this file; they import
{family}.py."

Parts and cables:

    import subprocess
    from harnice.lists import rev_history
    from harnice import state, fileio

    REVISION = "1"
    DATE_STARTED = "<today>"
    LIBRARY_REPO = "https://github.com/you/your-library"
    LIBRARY_SUBPATH = "my_family"

    def build_sku(rev_dir):
        # Always harnice -b. Do not call part.build() in-process.
        # Do not suppress errors: check=True, keep stderr, stop on failure.
        subprocess.run(
            ["harnice", "-b"],
            cwd=rev_dir,
            check=True,
        )

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
                build_sku(rev_dir)
            print(progress_bar(i, len(variants)))

Always build each SKU with `harnice -b` from that revision folder.
Do not call part.build() / cable.build() / device.build() in-process as
the check. Do not suppress errors from `harnice -b`: run with
`check=True` (or equivalent), leave stdout and stderr visible, and stop
on a nonzero exit. A traceback is the review. Fix the SKU and rebuild.

If `harnice` is not on PATH:

    python3 /path/to/harnice-cli/src/harnice/__main__.py -b

### Check every drawing (parts)

After the SKUs build, run this from the family folder on every SKU the
generator wrote:

    harnice --check-drawing */rev{REVISION}

Each argument is a part number folder, a revision folder, or a
`drawing.svg`. If `harnice` is not on PATH, run
`python3 /path/to/harnice-cli/src/harnice/__main__.py --check-drawing`
with the same arguments.

It fails a drawing that breaks the drawing contract in phase 4: a
transform in the group, an origin that is not on the part along X, the
axis off y = 0, a shape with zero or negative size, a
color an SVG reader cannot use, `3d-mate` off the part, a flagnote leader off the
outline, a balloon on the part, or polar and Cartesian on one csys child.
It exits 1 when any drawing fails. A failure is a fix in the generator and
a regenerate, the same as a failed `harnice -b`. Do not edit a
`drawing.svg` by hand.

Pass `--length` and `--height` (`1.28in` or `32.5mm`) on a SKU whose
datasheet gives overall length and max diameter. A wrong unit shows up
there.

Then look. Run it again on three SKUs: the smallest, one in the middle,
and the largest. A parameter that is fine at one size breaks at another:

    harnice --check-drawing {smallest PN} {middle PN} {largest PN}

It prints the path of one PNG. Open that image. Say, for each part, in one
line each:

- The ORIGIN cross is on the cable-entry face, or where I told you x = 0 is.
- It runs along the +X arrow to the mating face.
- The `3d-mate` dot sits on the mating face, or where the stud goes on a
  terminal.
- The gray leader lines end on the outline. The balloons sit clear of it.
- Nothing sticks out of the body or overlaps where it should not at that
  size.
- When I gave a reference picture: it shows the same features and colors,
  turned into the drawing frame.

Fix what you see, regenerate, and look again. The image shows at most 12
drawings, failed ones first.

An online chatbot cannot run the check. It tells me to run both commands
and paste back what they print. It does not claim the check passed.

Cache fileio.harnice_version and fileio.drawnby once per run.
part_family_append otherwise shells out to git on every SKU.

Driver flags:
    --step-only  --svg-only  --no-build
    plus a filter flag if the catalog is large (--xlr-only, --24-only, ...)

Print a text progress bar. At the family root, write a catalog CSV whose
columns match the chooser fields.

Devices:

    import subprocess
    from harnice.lists import rev_history
    from harnice import state

    def build_device(rev_dir):
        # Always harnice -b. Do not call device.build() in-process.
        # Do not suppress errors: check=True, keep stderr, stop on failure.
        subprocess.run(
            ["harnice", "-b"],
            cwd=rev_dir,
            check=True,
        )

    def main(build=True):
        state.set_rev(REVISION)
        state.set_project_type("device")
        family_dir = os.path.dirname(os.path.abspath(__file__))
        variants = list(iter_part_configurations())
        for i, cfg in enumerate(variants, start=1):
            pn = make_part_number(cfg)
            part_dir = os.path.join(family_dir, pn)
            rev_dir = os.path.join(part_dir, f"rev{REVISION}")
            os.makedirs(rev_dir, exist_ok=True)
            rev_history.part_family_append(revision_history_row(cfg), ...)
            # write attributes.json, build.py, and config.yaml when this SKU has setup
            if build:
                build_device(rev_dir)
            print(progress_bar(i, len(variants)))

Each `build.py` is the signals list for that one SKU. Follow
`skills/device-signals-list/SKILL.md` for the script: straight-line code,
no helper, no class, no `from harnice` import. Bake that SKU's constants
into the file. Cite the pinout in a comment, and write the expected signal
count there. `signals_list.new()` then `signals_list.append`. The device
build writes `signals.tsv` and `symbol.svg`. Do not write those files
yourself.

Ask the engineering questions in that skill before the first `build.py`.
Channel type, chassis ground, and which connector a pin lands on are my
decisions. One answer covers every SKU that follows from it. Do not write
the generator while a question is open. A blatantly obvious mapping is a
comment, the same way that skill says.

A body is in that `build.py` only when I asked for one. The calls are
`skills/cad/SKILL.md`, with dimensions from `cfg`. `cad` is already bound
when the device build runs the script. Do not write `body.step` from the
generator.

`chtype.signals` reads `channel_types.tsv` from the library path in
`repository_locations.csv`. A missing channel type is
`skills/channel-type/SKILL.md`, then come back here.

An agent runs the generator, and every SKU build is `harnice -b` from that
revision folder. Do not suppress errors from those builds. A failed
`harnice -b` is the review: fix that SKU and rebuild. Do not skip the
build, do not catch the failure and keep going, and do not claim success
when the exit code was nonzero. `rev_history.part_family_append` reads
`drawnby.json` the same way a device build does. The drawn-by steps are
under "Run the build" in `skills/device-signals-list/SKILL.md`. After each
device SKU, the build prints `Wrote N signal rows.` N matches the count in
that `build.py` comment, and N is greater than 0. A mismatch is a fix of
that file and a rebuild of that SKU.

An online chatbot writes the chooser, the generator, and the CSV when the
CSV is the source, and tells me to run the generator. It does not claim a
build exited 0.

Driver flags for a device family: `--no-build`, plus a filter when the
catalog is large. No `--step-only`. No `--svg-only`.


## HARD RULES

- Only SKUs the manufacturer sells.
- Chooser PNs must be a subset of generator PNs.
- Parts and cables: SVG and STEP from the same envelope, same cable-side origin.
- Parts and cables: origin is always the cable side. Mating-face cups do not move it.
- Parts: no transform in the drawing group. `harnice --check-drawing` passes on every SKU.
- A device family does not write drawing.svg, model.step, signals.tsv, symbol.svg, or body.step by hand.
- A catalog axis is a part number. A setup that keeps the hardware is config.yaml on that one device.
- Always build each emitted SKU with `harnice -b` from that revision folder.
  Do not use in-process part.build() / cable.build() / device.build() as the
  check. Do not suppress errors from that build.
- No secrets, no scraped paywalled HTML dumps — use the attached datasheet.
- Do not invent Harnice APIs. Read the folder from `harnice --docs` before
  you guess a function. The same pages are at https://harnice.io/ when you
  can reach the internet. Use rev_history.part_family_append, state,
  fileio, step_utils, project_types.part / project_types.cable /
  project_types.device as they exist.
- Keep the chooser free of drawing code, signals-list appends, and its own
  copy of the catalog.
- One source of truth: every table, dimension, and part-number format lives
  in `{family}.csv` or in `{family}_generator.py`, never both.
- Description voice: ALL CAPS, "CONNECTOR, ..." / "CABLE, ..." / "DEVICE, ..."


## DONE CRITERIA

- [ ] The chooser's first function is choose_part. It reads only {family}.csv, rejects illegal input with the legal values, and has no other public function unless the family has a mate or an accessory
- [ ] Every table, dimension, and part-number format lives in one file: {family}.csv or {family}_generator.py
- [ ] choose_part returns PNs that the generator emits. find_mating_connector does too, when this family has one
- [ ] Every part folder has revision history, attributes, drawing, and model
- [ ] Every cable folder has revision history, attributes, and a conductor list
- [ ] Every device folder has revision history, attributes, and build.py. The build wrote signals.tsv and symbol.svg. config.yaml is present only when that SKU has setup. body.step is present only when I asked for a body
- [ ] Parts and cables: SVG and STEP share an envelope and a cable-side origin
- [ ] Parts: `harnice --check-drawing */rev{REVISION}` exited 0, and you opened the image for the smallest, middle, and largest SKU and said what you saw
- [ ] contacts or cable identifiers match the spec names. A device's connector_id and cavity names match the pinout
- [ ] lib_repo + lib_subpath on the revision row match the library
- [ ] A part or cable chooser docstring shows instances_list.modify. A device chooser docstring shows MPN, lib_repo, lib_subpath, and rev for Place device
- [ ] Datasheet URLs sit on tables and on datasheet / mass_source fields
- [ ] You did not generate SKUs the manufacturer does not sell
- [ ] A device family asked the signals-list questions before writing build.py, and each build printed a signal-row count that matches that file's comment
- [ ] An agent built every emitted SKU with `harnice -b` (or `python3 /path/to/harnice-cli/src/harnice/__main__.py -b`) from that revision folder, did not use in-process part/cable/device.build() as the check, and did not suppress errors from those builds. An online chatbot told me to run the generator and did not invent exit codes

Reply with:
1. Configuration count and 5 example library PNs
2. Parts and cables: origin convention (one sentence: cable side, +X toward mate). Parts: the `--check-drawing` result and your one line per SKU from the image. Devices: the signal-row count for each of those five PNs
3. Paths of the chooser, the generator, and the catalog CSV, as `(url)/path/file` when they sit in a library folder, and which one is the source of truth
4. How a harness script should import and call the chooser, or, for a device, the Place device fields
5. Parts and cables: any dimension that is an estimate rather than a callout. Devices: whether a body was written, and any pinout assumption you recorded in a comment
