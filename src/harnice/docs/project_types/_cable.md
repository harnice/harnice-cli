# Cables

A cable is a COTS or custom physical item, purchased by length, that contains electrical conductors, and are physically installed inside harnesses.

## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")       |-- yourpn/
                                           |-- earlier revs/
fileio.path("revision history")            |-- revhistory.csv
fileio.dirpath("rev_directory")            L-- your rev/
fileio.path("attributes")                      |-- attributes.json
fileio.path("conductor list")                  L-- conductors.tsv
```


---

## Describing the layout

A cable's attributes JSON describes the physical layout by nesting: each key holding an object is a member contained by the object above it, so a jacket holds a shield, which holds a pair, which holds conductors.

Alongside those members, a node may carry:

- `properties` — dimensions and materials such as `od`, `thickness`, `color`, `gauge`, `construction`.
- `appearance` — how the member is identified visually.

    ??? info "Appearance"

        {% include-markdown "commands/_appearance.md" %}

- `conductor: true` — marks the node as a conductor.

Building the cable walks that tree and writes one row per conductor to the conductor list, where `container` and `identifier` are the two innermost names in the path to that conductor. `identifier` (the conductor node's key) must be unique across the cable. If two pairs would both be named `black`, put a namespace in the key (`pair_1_black`, `pair_2_black`). Duplicate identifiers fail the build.

---

## Viewing the layout

Open the cable in the Harnice console and select **cable layout**. The hierarchy is drawn two ways side by side, with the member tree on the right.

**Cross section**, on the left, packs every member inside its container as a circle, sized from its stated `od`, or estimated from its `gauge` when no `od` is given, and painted from its color and stripes. A stated `od` on a container is honored as the true outer dimension whenever the members leave room, so the drawing matches the datasheet. The drawing sizes itself to its pane; there is nothing to zoom or pan. Drag the divider between the drawings to resize them.

**Isometric**, in the middle, extrudes that same packing along the cable and strips it back the way a sample of cable would be, so the construction is exposed. It is a drawing rather than a render — flat shapes arranged to read as solid — so every surface carries the flat paint the cross section gives that member and the cut faces are painted with the cross section itself, and the two views cannot disagree about how a member looks. Members run straight, and each layer is cut one tier further back than the one outside it, so every level of the nesting gets a band of the cable to itself. As a layer opens, the members inside it swing out clear of the cable. Insulation is drawn only when the JSON names it (`base_color` or `insulation material`); a conductor that names a metal and no insulation is that metal for its whole length. If a conductor has neither a color nor a metal, it is painted with the same rainbow placeholder used for traces that have no appearance. A named metal on an insulated conductor is shown at the stripped tip. Where members of a group would still cover each other — the angle never changes, so one in front stays in front — they are trimmed into a staircase, nearest the eye shortest. A member is drawn as a body when it is a conductor (`conductor: true`) or the JSON states a color. Otherwise the cross section shows only a boundary circle with no fill, and the isometric omits it, while still packing and listing the members it holds. Stripes carry over as they are described: `parallelstripe` runs the length of a member, `perpstripe` bands around it. The angle is fixed and the drawing sizes itself to its pane; there is nothing to orbit, zoom or pan.

The tree lists every member with its properties. Click a member in either drawing to highlight it in the other. Everything here is read only: edit the attributes JSON and build the cable to update it.