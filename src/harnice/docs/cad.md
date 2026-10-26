# CAD

A device build writes a solid. A system poses those solids and fastens their mate connectors. Distances in the model are inches. `body.step` and `assembly.step` are millimetres, which is what the viewer reads.

The build writes the solid. The **physical model** page places mate connectors on it, and pastes a picture on a face.

---

## Give a device a body

Call one macro from the device `build.py`. All four live in `library/macros/device_artifacts` on `https://github.com/harnice/harnice-general-library`. Each saves with `fileio.path("body")`, the device's `body.step`, and uses `artifact_id="body-1"`.

`cad`, `physical_body`, `fileio`, and `build_utils` are already in the build namespace. A device `build.py` uses those names as they stand. Import `os` when a path is joined. A macro file may import `harnice.utils.cad`.

### Rectangular box

`width`, `height`, and `depth` are inches. The sketch is a height-by-width rectangle on the `front` plane, centered on the origin. Extrude grows the solid along +Y by `depth`. The face at y = 0 is the surface `front`, which is also the viewer's front face.

```python
import os

images = {
    "front": os.path.join(fileio.dirpath("body_images"), "front.png"),
}
build_utils.run_macro(
    "build_rectangular_physical_model",
    "library/macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    params={"width": 4, "height": 2, "depth": 6},
    images=images,
)
```

This macro writes no mate connectors. Place those on the physical model page, or add them with `cad.mate` in your own script.

### Rack chassis

`u` is the rack height in units. `depth` is inches. The faceplate is the model's front face, y = 0. +Z points up, and +X points to the right when looking at that front. The chassis extends along +Y.

The ears are 19 inches wide and 1/16 inch thick. The chassis behind them is 17 inches wide. A depth shallower than the ear is only that plate. Height is `u × 1.75` inches, starting at z = 0.

Each unit gets a mate connector on the faceplate, centered on that unit. `F1` is the bottom unit, at `[0, 0, 0.875]` for a full unit, with gamma −90 so the mate's +X points out of the front. Those mates have `source` `build`, so the next build places them again.

```python
import os

images = {
    "front": os.path.join(fileio.dirpath("body_images"), "front.png"),
}
build_utils.run_macro(
    "build_rackmount_physical_model",
    "library/macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    params={"u": 2, "depth": 10},
    images=images,
)
```

`images` keys are surface names. `front` is the faceplate, and the viewer paints that y = 0 face under the same name. `back` is the face at y = depth. `bottom` stays the sketch face at z = 0.

### Rack enclosure

`depth` and `units` are separate arguments, not a `params` dict. The front of the rack is the model's front face, y = 0. The shell is 21 inches wide (19 plus 1 inch of wall on each side) and `units × 1.75` tall plus 1 inch of wall on the top and the bottom. It extends along +Y by `depth`. A 17 inch wide opening, exactly `units × 1.75` tall, is cut through that depth. The front and the back are both open.

The opening starts 1 inch above z = 0. `F1` is the center of the bottom unit on the front face, so a full unit puts it at `[0, 0, 1.875]`, with gamma −90 so its +X points out the front and +Z points up. `B1` is the center of that unit on the back, at y = depth, with gamma 90 so its +X points out the back and +Z still points up. Both are `build` mates.

```python
build_utils.run_macro(
    "build_rackmount_enclosure",
    "library/macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    depth=10,
    units=2,
)
```

### An existing STEP file

`build_physical_model_from_step` copies `path_to_step` onto `body.step`. The bytes stay as they are. The copy is not a `cad` model, so this macro attaches no images. A STEP file that already contains Harnice image comments keeps them. You can still paste a face picture on the physical model page.

```python
build_utils.run_macro(
    "build_physical_model_from_step",
    "library/macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    path_to_step="vendor/chassis.step",
)
```

---

## Frames

`cad.new()` starts a model with three datum planes through the origin. A plane's name is its normal. Sketch coordinates are inches along u and v, and u × v is that normal.

| Plane | Normal | u | v |
| --- | --- | --- | --- |
| `top` | `[1, 0, 0]` (+X) | `[0, 1, 0]` (+Y) | `[0, 0, 1]` (+Z) |
| `front` | `[0, 1, 0]` (+Y) | `[0, 0, 1]` (+Z) | `[1, 0, 0]` (+X) |
| `right` | `[0, 0, 1]` (+Z) | `[1, 0, 0]` (+X) | `[0, 1, 0]` (+Y) |

`extrude` grows the solid along the plane normal by a distance greater than zero. The sketch stays the face at distance 0. Sketch coordinates can be negative. A rack chassis and a rack enclosure both sit with the faceplate at y = 0 and the body along +Y. The enclosure opening is extruded along +Y through the shell.

The viewer paints six faces. Each picture covers the solid on that side of the bounding box. A rectangular body fills the box. A rack chassis is 19 inches across the ears and 17 inches across the rear panel, so the back picture is 17 inches wide and does not include the ears. Those names are independent of the datum planes, except where a macro stores an image under a viewer name.

| Viewer face | Side of the bounding box |
| --- | --- |
| `front` | minimum Y, normal −Y |
| `back` | maximum Y, normal +Y |
| `right` | maximum X, normal +X |
| `left` | minimum X, normal −X |
| `top` | maximum Z, normal +Z |
| `bottom` | minimum Z, normal −Z |

A rectangular body grows along +Y from y = 0, so its sketch surface `front` is the viewer's front face. A rack chassis faceplate and a rack enclosure faceplate are both y = 0, so that face is the viewer's front.

A mate connector uses the same pose as a harness 3D node: location `[x, y, z]` in inches, and `alpha`, `beta`, `gamma` in degrees. The rotation is `R = Rx(α) · Ry(β) · Rz(γ)`. Angles 0 leave the mate frame aligned with the device frame.

---

## Mate connectors

Mates are stored in `fileio.path("attributes")` (`attributes.json`) under `mate_connectors`. Other keys in that file stay.

```json
{
    "id": "J1",
    "location": [0.0, 0.0, 0.875],
    "alpha": 0,
    "beta": 0,
    "gamma": 0,
    "source": "gui"
}
```

`source` is `build` or `gui`.

- A `build` mate is placed again on the next build. The rack macros write `F1`, `F2`, and the enclosure's `B1`, `B2` this way.
- A `gui` mate keeps the pose saved in `attributes.json`. A `gui` mate with the same id replaces the build mate.
- A mate saved without `source` is `build` when its id is `U` plus digits, and `gui` otherwise.

Once `mate_connectors` is present, every `connector_id` on the signals list needs a mate with that same id. The build fails if one is missing, and tells you to place it on the physical model page. A device with no `mate_connectors` key still builds.

Opening the physical model page writes that key when it is absent, and puts any missing required mate at the origin with `source` `gui`. Those ids stay tied to the signals list. Other mates can be added, renamed, and deleted.

The shipped macros that write mates call `cad.keep_gui_mates` before `cad.save_mates`. That copies saved `gui` mates onto the new model and drops a `build` mate this run did not create. A custom script that calls `cad.save_mates` does the same, or the next build replaces the poses you set on the page.

On the device page, select a mate and drag its triad, or type the numbers. The properties card edits the id, the pose, and `source`. A signals-list connector id cannot be renamed or deleted. **Add mate connector** creates another mate at the origin.

---

## Face pictures

`images` maps a surface uuid to a file, usually under `fileio.dirpath("body_images")`. The path is stored in `body.step` as a comment. A file inside the revision is stored relative to that folder. The path cannot contain a space.

On the physical model page, click a face and paste a screenshot. The PNG is stored under `body_images/` and linked from the STEP file. **Clear image** removes that link. Select two faces to read the distance between them, in inches, when they are parallel, or the angle between them when they are not.

An imported STEP file can take a pasted picture the same way. The import macro itself does not attach one.

---

## A solid that is not one of the macros

Sketch a closed profile, extrude it, save the STEP file, and save mates if this script owns any.

```python
import os

model = cad.new()
cad.sketch(
    model,
    "front",
    "front",
    {
        "a": (-1, -2),
        "b": (1, -2),
        "c": (1, 2),
        "d": (-1, 2),
    },
    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")],
)
cad.extrude(model, "front", 6)
cad.attach_png(
    model,
    "front",
    os.path.join(fileio.dirpath("body_images"), "front.png"),
    0,
)
cad.save_step(model, fileio.path("body"))

cad.mate(model, "J1", [0, 0, 0])
saved = physical_body.load_body(fileio.path("attributes"))
if saved:
    cad.keep_gui_mates(model, saved["mate_connectors"])
cad.save_mates(model, fileio.path("attributes"))
```

`extrude` returns a body. `cad.boolean_subtract(tools, targets)` cuts tool bodies out of target bodies. Both have to be rectangular prisms, axis-aligned boxes. Targets are updated in place. Tools are removed from the model they were extruded onto. A body cannot be both a tool and a target.

`extrude` names the far face `"{uuid}-end"` and each side `"{uuid}-{start}-{end}"` from the sketch edge. `attach_png` and a later `extrude` use those ids. A surface uuid and a vertex name cannot contain a space or `*/`. The sketch is one closed loop of at least three vertices, and every vertex is on that loop.

`cad.save_mates` raises when the model has no mates. `cad.save_step` raises when the model has no solid.

---

## Functions

These names are on the `cad` module.

| Call | What it does |
| --- | --- |
| `cad.new()` | A model with the three datum planes. |
| `cad.sketch(model, uuid, plane, vertices, edges)` | A surface. `vertices` maps a name to `(u, v)` inches. `edges` is a closed loop of `(start, end)` names. |
| `cad.extrude(model, uuid, distance)` | A solid along that plane's normal. `distance` is inches and greater than zero. Returns a body. |
| `cad.boolean_subtract(tools, targets)` | Cuts tool bodies out of target bodies. Each argument is a body or a list of bodies. Both are rectangular prisms. |
| `cad.attach_png(model, uuid, filepath, orientation)` | Stores an image path and an orientation, in degrees, on a surface. The file has to exist. |
| `cad.save_step(model, path)` | Writes the solids. Image links are comments in that file. |
| `cad.mate(model, uuid, location, alpha=0, beta=0, gamma=0, source="build")` | Adds a mate connector. `location` is `[x, y, z]` inches. |
| `cad.keep_gui_mates(model, saved)` | Copies `gui` mates onto the model. A `gui` mate replaces a `build` mate with the same id. |
| `cad.save_mates(model, path)` | Writes this model's mates into `attributes.json`. |
| `cad.import_step(source, destination)` | Copies a STEP file. The copy is not a model. |

`physical_body.load_body(path)` reads `mate_connectors` from an attributes file. It returns `None` when that key is absent. `physical_body.save_mates(mates, path)` writes the key and leaves other attributes in place.

---

## Arrange devices in a system

Open **physical model** on the system. Every placed device that has `body.step` is one solid. A device with no body is listed and left out of the assembly. Build that device, then come back.

Poses, fasten mates, and grounded devices are stored in `physical.json` (`fileio.path("physical assembly")`). The page rewrites `assembly.step` (`fileio.path("assembly")`) from that file. Edit the page. Leave `assembly.step` to the page. The next time the page opens, it drops a device that no longer has a body, places a new body, solves the mates, and writes the STEP file again.

A new body is placed 24 inches further along +X than the bodies already there.

### Place

Click a device or a mate connector to add it to the selection. Shift-click removes it. Drag a device's triad to move it, or type the pose. **Fix** grounds the selected devices: the pose stays put, and dragging the triad does nothing. **Fix** again releases them.

**Mate** fastens two connectors. Pick one mate connector on each of two devices. The card asks which device moves onto the other. The device that moves is `b` in `physical.json`. The device that stays is `a`. **Face to face** turns the fixed connector's target 180° about its X axis, so the two Z axes point opposite ways and the parts sit face to face. Without that, the moving connector occupies the same frame as the one it fastens to.

A device can be the moving side of one mate. A grounded device cannot be the one that moves. A chain is solved from the grounded device outward: a device moves only after the device it fastens to has been placed. A cycle is rejected. **de-mate** on the card removes the constraint that holds that device.

```json
{
    "placements": {
        "RACK-1": {"x": 0, "y": 0, "z": 0, "alpha": 0, "beta": 0, "gamma": 0},
        "MIC-1": {"x": 0, "y": 0, "z": 0, "alpha": 0, "beta": 0, "gamma": 0}
    },
    "mates": [
        {
            "a": {"device": "RACK-1", "mate": "F1"},
            "b": {"device": "MIC-1", "mate": "J1"},
            "flip": true
        }
    ],
    "fixed": ["RACK-1"]
}
```

`placements` are inches and the same ZYX Euler angles as a device mate. After a fasten, the moving device's placement is the solved pose. The mate is the constraint. The next open solves it again.

The **Context** menu shows a STEP file dropped in the system's `contexts/` folder. That file is a reference in the viewport. It is not a device in the assembly.

Writing `assembly.step` reads each device body through OpenCascade. If OpenCascade fails to load, the page reports that STEP files cannot be read or written. A device `body.step` can still be written without it.

### Route

**Mode: Route** edits this system's available network in the same viewport: select, add a node, add a segment. That network is `available_network.json`. Place mode is the assembly.

A harness whose source system has `assembly.step` can show that assembly while you route the harness. The harness keeps a reference. It does not copy the assembly into the harness folder.
