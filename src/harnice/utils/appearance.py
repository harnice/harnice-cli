import ast
import webcolors

"""
Appearance data specification
=============================

This module defines the engineering appearance dictionary, the style
dictionary, and the canonical color representation.

Physical geometry is plotted from appearance. Drafting ink is painted from
style. Where an instance needs both, build the style dict at that instance
from its parsed appearance (``base_color`` → fill, ``outline_color`` → stroke,
``black_or_white_to_contrast_with_color`` → text).

Color tokens
------------
Color-valued fields accept:

- SVG/CSS Level 1 keyword (see https://www.w3.org/TR/SVG11/types.html#ColorKeywords)
- ``#rgb``
- ``#rrggbb``

``parse(val)`` accepts a ``dict`` or a dictionary-formatted string (instances-list
TSV cannot nest a dict). It runs ``ast.literal_eval`` and walks the result.
Any value that looks like a color becomes lowercase ``#rrggbb``. Non-color
strings (e.g. ``twisted``, ``font_weight``) are passed through unchanged.
Empty or non-dict input returns ``None``.


1. Engineering appearance
-------------------------
Describes the physical identification of a conductor, cable member, or routed
segment. Persistence: instance field ``appearance``; cable ``attributes.json``
conductor records; argument to ``svg_utils.draw_styled_path`` and
``svg_utils.draw_filleted_styled_path``.

    {
        "base_color": <color>,            # insulation / jacket; required to stroke a path
        "outline_color": <color>,         # optional concentric outline
        "parallelstripe": [<color>, ...], # 0..n longitudinal stripes
        "perpstripe": [<color>, ...],     # 0..n transverse bands
        "twisted": None | "RH" | "LH",    # twist sense (project data)
        "slash_lines": {                  # hatch overlay consumed by path drawing
            "direction": "RH" | "LH",     # required for hatch emission
            "angle": <deg>,               # default 20
            "step": <svg-user-units>,     # default 3 × path stroke width
            "color": <color>,             # default black
            "slash_width_inches": <in>,   # omitted → 0.25 svg user units (not inches)
        },
    }

``base_color`` is required for a drawable path. If it is absent, path drawing
substitutes a rainbow placeholder stroke.

``twisted`` and ``slash_lines`` are independent. ``twisted`` is project intent.
``slash_lines`` is the geometry actually emitted by the path drawer. Either,
neither, or both may be present; the drawer does not derive ``slash_lines``
from ``twisted``.

Consumed by path drawers that represent a physical object:
``svg_utils.draw_styled_path``, ``svg_utils.draw_filleted_styled_path``.


2. Style
--------
Describes drafting ink: cell fill, border, and type. Not a physical object.
Persistence: ``svg_utils.table`` format layers (``globals``, named row format,
column definition, cell) and equivalent call sites (``label_svg``,
``draw_clean_line``, xlwt).

    {
        "fill_color": <color>,            # background; default #ffffff
        "stroke_color": <color>,          # border; default #000000
        "text_color": <color>,            # glyphs; default #000000
        # non-color format keys (font_size, font_weight, row_height, …) are
        # ignored by this module and passed through by the table formatter.
    }

Consumed by drafting drawers: ``svg_utils.table``, ``svg_utils.label_svg``,
``svg_utils.draw_clean_line``. If the source is an instance appearance, the
caller builds this dict locally before paint.


Mapping at the instance
-----------------------
There is no global appearance→style converter. At each instance that needs
drafting ink, parse the appearance and build:

    {
        "fill_color":  base_color or outline_color,
        "stroke_color": outline_color or #000000,
        "text_color":  black_or_white_to_contrast_with_color(fill),
    }


Other operations
----------------
``to_rgb(val)``
    Color token or engineering dict → ``(r, g, b)`` in 0..255.
    Engineering color is ``base_color``, else ``outline_color``.
    Empty or unparseable input → ``(0, 0, 0)``.

``black_or_white_to_contrast_with_color(color)``
    Color token or engineering dict → ``#ffffff`` or ``#000000`` per the
    luminance threshold above.
"""

def normalize_color_into_rrggbb(c):
    """Normalize one CSS/SVG color token to ``#rrggbb``. Non-colors pass through."""
    if not isinstance(c, str):
        return c
    s = c.strip()
    if not s:
        return c
    lower = s.lower()
    if lower.startswith("#"):
        if len(lower) == 4:
            return "#" + "".join(ch * 2 for ch in lower[1:])
        return lower
    try:
        return webcolors.name_to_hex(lower)
    except ValueError:
        return c


def parse(val):
    """
    Parse a dict or dict-string, converting color-like values to ``#rrggbb``.

    Runs ``ast.literal_eval`` on strings. Nested dicts and lists are walked.
    Non-color strings are left as-is. Empty or non-dict input returns ``None``.

    **Args:**
    - `val` (dict or str): Dictionary, or a string ``ast.literal_eval`` can read as a dict.

    **Returns:**
    - `dict`: Same keys with colors as ``#rrggbb``, or ``None``.
    """
    if isinstance(val, dict):
        data = val
    else:
        try:
            data = ast.literal_eval(str(val))
        except (ValueError, SyntaxError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
    if not data:
        return None
    result = {}
    for key, value in data.items():
        if isinstance(value, list):
            result[key] = [
                normalize_color_into_rrggbb(item) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, dict):
            result[key] = parse(value)
        elif isinstance(value, str):
            result[key] = normalize_color_into_rrggbb(value)
        else:
            result[key] = value
    return result


def to_rgb(val):
    """
    Return ``(r, g, b)`` in 0–255 from a color name, hex string, or appearance dict.

    Unknown or empty values return ``(0, 0, 0)``. Appearance dicts use
    ``base_color``, then ``outline_color``.

    **Args:**
    - `val` (str or dict): Color name, hex, or appearance dictionary.

    **Returns:**
    - `tuple`: ``(r, g, b)`` each 0–255.
    """
    if val in (None, ""):
        return (0, 0, 0)
    src = parse(val)
    if isinstance(src, dict):
        nested = src.get("appearance")
        if isinstance(nested, dict):
            src = nested
        elif isinstance(src.get("fill_color"), dict):
            src = src["fill_color"]
        token = src.get("base_color") or src.get("outline_color")
    elif isinstance(val, str):
        token = normalize_color_into_rrggbb(val)
    else:
        return (0, 0, 0)
    if not isinstance(token, str) or not token.startswith("#"):
        return (0, 0, 0)
    h = token.strip().lstrip("#")
    try:
        if len(h) >= 6:
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        pass
    return (0, 0, 0)


def black_or_white_to_contrast_with_color(color):
    """
    Return ``#ffffff`` or ``#000000``, whichever has higher WCAG contrast against the color.

    **Args:**
    - `color` (str or dict): Color name, hex, or appearance dictionary.

    **Returns:**
    - `str`: ``#ffffff`` or ``#000000``.
    """
    r, g, b = to_rgb(color)

    def _linearize(channel):
        c = channel / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)
    # Contrast vs white exceeds vs black when luminance is below ~0.179.
    return "#ffffff" if luminance < 0.179 else "#000000"
