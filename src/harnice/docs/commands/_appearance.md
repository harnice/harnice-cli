# Appearance Utilities## Appearance Guide

Physical geometry (formboard segments, schematic wires, harness overlays) is plotted from an **engineering appearance** dict:

~~~json
{
    "base_color": "#000000",
    "parallelstripe": ["#000000", "#000000"],
    "perpstripe": ["#000000", "#000000"],
    "twisted": null
}
~~~

The same dict is the optional `channel_default_appearance` cell, and each value inside `signal_default_appearances`, on the channel type's `channel_types.tsv`. See Channel Types. An instance `appearance` that already includes `base_color` is the appearance drawn for that trace.

Drafting ink (tables, wirelists, labels, dimension lines) is painted from a **style** dict: `fill_color`, `stroke_color`, `text_color`. Build that dict at the instance from its parsed appearance.

### Arguments

**Required**
- `base_color`: exactly one value

**Optional**
- `parallelstripe`: 0+ values (list)
- `perpstripe`: 0+ values (list)
- `twisted`: 0–1 value (`null`, `"RH"`, or `"LH"`)
- `outline_color`: 0–1 value

---
##Commands
*These functions are already available in build instructions as `appearance`. Use them as written.*
??? info "`appearance.parse(val)`"

    Parse a dict or dict-string, converting color-like values to ``#rrggbb``.
    
    Runs ``ast.literal_eval`` on strings. Nested dicts and lists are walked.
    Non-color strings are left as-is. Empty or non-dict input returns ``None``.
    
    **Args:**
    - `val` (dict or str): Dictionary, or a string ``ast.literal_eval`` can read as a dict.
    
    **Returns:**
    - `dict`: Same keys with colors as ``#rrggbb``, or ``None``.

??? info "`appearance.to_rgb(val)`"

    Return ``(r, g, b)`` in 0–255 from a color name, hex string, or appearance dict.
    
    Unknown or empty values return ``(0, 0, 0)``. Appearance dicts use
    ``base_color``, then ``outline_color``.
    
    **Args:**
    - `val` (str or dict): Color name, hex, or appearance dictionary.
    
    **Returns:**
    - `tuple`: ``(r, g, b)`` each 0–255.

??? info "`appearance.black_or_white_to_contrast_with_color(color)`"

    Return ``#ffffff`` or ``#000000``, whichever has higher WCAG contrast against the color.
    
    **Args:**
    - `color` (str or dict): Color name, hex, or appearance dictionary.
    
    **Returns:**
    - `str`: ``#ffffff`` or ``#000000``.

