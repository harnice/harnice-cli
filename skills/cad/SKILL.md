---
name: cad
description: >-
  Write a Harnice device body and arrange those bodies in a system. Use when
  the user asks for a physical model, body.step, a mate connector, a rack
  chassis or enclosure, cad.new, sketch, extrude, or a system assembly.
  A device pinout uses the device-signals-list skill. System build.py uses
  the system-build skill.
---

# Mechanical CAD for Building Physical Models

This file is the procedure for a device solid and for posing those solids
in a system. The page that explains the frames, the macros, and the `cad`
calls is `cad.md` in the documentation folder.

    harnice --docs

That prints the folder. `cad.md` is next to `index.md`. If `harnice` is
not on PATH:

    python3 /path/to/harnice-cli/src/harnice/__main__.py --docs

A clone of https://github.com/harnice/harnice-cli keeps the same folder at
`src/harnice/docs/`. The same pages are at https://harnice.io/ when you
can reach the internet. The CAD page is `cad.md`.

Read `cad.md` before you sketch, before you choose a plane, and before you
edit `physical.json`. Do not invent a function, a plane normal, or a mate
field that page does not name. If you cannot read the page, say so and ask
me to paste it. The table under Pick the body names the shipped
macros. Copy the `run_macro` call from `cad.md`. Read that page before
a custom solid.


## What you are writing

A device body is `fileio.path("body")` (`body.step`). Mate connectors are
`mate_connectors` in `fileio.path("attributes")` (`attributes.json`). A
system arrangement is `fileio.path("physical assembly")` (`physical.json`).
The system page rewrites `fileio.path("assembly")` (`assembly.step`) from
that file.

You do not hand-write `body.step`, `assembly.step`, or `signals.tsv`.
Distances you type are inches.


## Online chatbot or agent

**Online chatbot.** You cannot run the build. Say so. Write the `build.py`
lines, or the `physical.json` object, and tell me to click Build or to
open the physical model page and paste back what it reports.

**Agent on my computer.** Run the device build yourself after you change
`build.py`. From the device revision folder:

    harnice -b

If that command is missing, run
`python3 /path/to/harnice-cli/src/harnice/__main__.py -b` from that same
folder. A traceback is the review. Fix the script and run it again.

Opening the system physical model page is how `assembly.step` is rewritten.
If you change `physical.json`, tell me to open that page. Do not tell me
the assembly STEP is current until that page has been opened.


## Pick the body

Use a shipped macro when the shape is one of these. The calls are the
ones in `cad.md`. `lib_repo` is
`https://github.com/harnice/harnice-general-library`. `lib_subpath` is
`library/macros/device_artifacts`. `artifact_id` is `"body-1"`.

| Shape | Macro | Arguments |
| --- | --- | --- |
| Box | `build_rectangular_physical_model` | `params={"width", "height", "depth"}` inches, optional `images` |
| Rack chassis, ears on one face | `build_rackmount_physical_model` | `params={"u", "depth"}`, optional `images` |
| Rack shell, open front and back | `build_rackmount_enclosure` | `depth`, `units` |
| Vendor STEP file | `build_physical_model_from_step` | `path_to_step` |

One body macro per device. Ask me which shape, and ask for every dimension
I did not give. Do not invent a rack unit count, a depth, or a STEP path.
A blatantly stated size is not a question. Write it in a comment.

`images` maps a surface name to a PNG that already exists. A missing file
makes `attach_png` raise. Omit `images` until I have put the file in
`body_images/`. A path stored in the STEP file cannot contain a space.

The rectangular macro writes no mates. The two rack macros write `U1`
upward, and the enclosure also writes `B1` on the back. Those ids are
`source` `build`. Read `cad.md` for where they sit and which way +X points.

Anything else is a custom solid in the device `build.py`, using `cad`.
Follow the example and the function table in `cad.md`. Then:

1. `cad.new()`, `cad.sketch`, `cad.extrude`. `extrude` distance is greater
   than zero, along the plane normal.
2. `cad.attach_png` only for a file that exists.
3. `cad.save_step(model, fileio.path("body"))`.
4. `cad.mate` for connectors this script owns.
5. `physical_body.load_body` and `cad.keep_gui_mates` before
   `cad.save_mates`, so a pose I set on the page survives the next build.
6. Call `cad.save_mates` only when the model has at least one mate.

`cad.boolean_subtract` cuts rectangular prisms only. Both bodies are
axis-aligned boxes. Name that limit in a comment if you use it.

`cad`, `physical_body`, `fileio`, and `build_utils` are already bound in
`build.py`. Do not write `from harnice import ...` there. A new macro file
may import `harnice.utils.cad`, because that file is the macro.

A signals list is `skills/device-signals-list/SKILL.md`. Do not append
signals from this skill unless I asked for the pinout as well. Once
`attributes.json` contains `mate_connectors`, every signals-list
`connector_id` needs a mate with that id. `keep_gui_mates` is how those
page-placed mates survive a rebuild that also writes `F1`.


## Arrange a system

I place and fasten devices on the system **physical model** page. Do that
in the page when I am at the keyboard.

When I ask you to record an arrangement, edit `physical.json` only. The
shape is in `cad.md`: `placements`, `mates`, `fixed`. `mates[].a` stays.
`mates[].b` moves. `flip` true is face to face. A device is `b` of one
mate. A name in `fixed` is never `b`.

Use mate ids that exist on those devices. Rack units are `F1` at the
front and `B1` at the back. A signals-list connector uses its
`connector_id`. Ask me which connector fastens to which unit when I have
not said.

Do not write `assembly.step`. Tell me to open the system physical model
page so Harnice solves the mates and writes it.


## Done

- [ ] The body is one shipped macro, or a `cad` script that matches `cad.md`
- [ ] Dimensions I did not give were asked, and the ones I gave are in a comment
- [ ] A custom script calls `keep_gui_mates` before `save_mates` when it saves mates
- [ ] `body.step` and `assembly.step` were not written by hand
- [ ] An agent ran the device build after changing `build.py`, or said it could not
- [ ] A `physical.json` edit names real devices and real mate ids, and I was told to open the system physical model page
