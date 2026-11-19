# Parts
Buyable or buildable child item that goes into a harness.


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
fileio.path("drawing")                         |-- drawing.svg
fileio.path("drawing png")                     |-- drawing.png
fileio.path("attributes")                      |-- attributes.json
fileio.path("model")                           |-- model.step
fileio.path("gitignore")                       L-- .gitignore
```

A build writes `.gitignore` in the revision folder. This project type ignores:

- `*.tmp`

Rules already in the file stay.

---

## Drawing frame

`drawing.svg` is a side view in the part's own frame. A harness places the part by its origin and points it along +X.

- The origin `(0, 0)` is the cable-entry face, on the part's axis. Most of a part is in +X, but anything may extend into -X by any amount.
- +X points from the cable toward the mating face. A connector's `3d-mate` sits on that face; a terminal's sits where its stud goes.
- The axis is y = 0. 96 px is 1 inch, and SVG y is -y.
- Everything Harnice reads is inside `<g id="{pn}-drawing-contents-start">`. Nothing in that group has a `transform`.

## Check a drawing

    harnice --check-drawing PATH [PATH ...] [--length 1.28in] [--height 30.5mm] [-o image.png]

Each `PATH` is a `drawing.svg`, a revision folder, or a part number folder. The command checks the drawing against the frame above and the csys children in `attributes.json` next to it. It fails a transform in the drawing group, an origin that is not on the part along X, an axis off y = 0, a shape with zero or negative size, a color an SVG reader cannot use, a `3d-mate` off the part, a flagnote leader off the outline, a balloon on top of the part, and a csys child with both polar and Cartesian values. `--length` and `--height` also check the overall size.

It prints each drawing's size and writes one PNG of up to 12 drawings, failed ones first, with the origin, the axis, and the +X direction marked. It exits 1 when any drawing fails. Part family generators run it on every SKU they write.
