---
name: part-family
description: >-
  Encode a Harnice part family from a how-to-order datasheet into library
  SKUs: a chooser, attributes, and one project folder per catalog number.
  Use when the user asks for a part family, catalog SKUs, or a how-to-order
  table turned into a library.
---

# Harnice part-family prompt

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
