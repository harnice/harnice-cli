import os
import re
import math

from harnice import cli
from harnice.utils import appearance


# Defaults for harness Analyze overlays and system block-diagram traces.
# ``trace_overlay_style`` starts as a copy of this at each build. A script
# writes that object; ``regenerate_trace_overlays`` writes it and redraws.
# Trace thickness is in inches (``draw_styled_path`` multiplies by 96). The
# other lengths are SVG user units in the same space as the network.
TRACE_OVERLAY_STYLE = {
    "label_font_size": 0.5,
    "segment_spacing": 1.5,
    "stroke_width": 0.5 / 96,
    "min_label_segment_length": None,
    "network_segment_stroke_width": 1.8,
    "network_segment_font_size": 11,
    "network_node_radius": 2.2,
    "network_node_font_size": 10,
}

class _TraceOverlayStyle:
    """Live overlay style for the build that is running.

    Harness and system builds reset this to the defaults before the script.
    Read it with ``trace_overlay_style()`` or ``trace_overlay_style.stroke_width``.
    Write it with an attribute, an item, or ``update``. A later conductor or
    cable layout drawing, and the block diagram copied into a PDF, use the
    values still set when they run. The Analyze overlays and the block diagram
    file are drawn again after the script with whatever is left.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Restore every key to the defaults."""
        object.__setattr__(self, "_values", dict(TRACE_OVERLAY_STYLE))

    def _merge(self, base, style):
        """Return ``base`` with ``style`` applied. Does not store it."""
        if not isinstance(style, dict):
            raise TypeError(
                "trace overlay style must be a dict; "
                f"got {type(style).__name__}"
            )
        unknown = [str(key) for key in style if key not in TRACE_OVERLAY_STYLE]
        if unknown:
            known = ", ".join(TRACE_OVERLAY_STYLE)
            raise ValueError(
                "unknown trace overlay style keys: "
                + ", ".join(unknown)
                + f". Keys are: {known}"
            )
        merged = dict(base)
        for key, value in style.items():
            if value is None and key != "min_label_segment_length":
                merged[key] = TRACE_OVERLAY_STYLE[key]
                continue
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                none_ok = " or None" if key == "min_label_segment_length" else ""
                raise TypeError(
                    f"trace overlay style {key} must be a number{none_ok}; "
                    f"got {value!r}"
                )
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"trace overlay style {key} must be a finite number")
            merged[key] = value
        return merged

    def __call__(self, style=None):
        """Copy of the style. A dict changes only the returned copy."""
        if style is None:
            return dict(self._values)
        return self._merge(self._values, style)

    def keys(self):
        return self._values.keys()

    def __getitem__(self, key):
        if key not in TRACE_OVERLAY_STYLE:
            raise KeyError(key)
        return self._values[key]

    def __setitem__(self, key, value):
        self.update({key: value})

    def __getattr__(self, key):
        if key in TRACE_OVERLAY_STYLE:
            return self._values[key]
        raise AttributeError(key)

    def __setattr__(self, key, value):
        if key in TRACE_OVERLAY_STYLE:
            self.update({key: value})
            return
        object.__setattr__(self, key, value)

    def update(self, style):
        """Merge ``style`` into the live values. ``None`` restores a key's default, except ``min_label_segment_length``."""
        object.__setattr__(self, "_values", self._merge(self._values, style))
        return self


# Reset to the defaults at the start of each harness or system build.
trace_overlay_style = _TraceOverlayStyle()


# Placed by the build-instructions ribbon. Keys match TRACE_OVERLAY_STYLE.
REGENERATE_TRACE_OVERLAYS_SNIPPET = """\
svg_utils.regenerate_trace_overlays(
    style={
        # Live style for this build. Assign svg_utils.trace_overlay_style.stroke_width
        # or call .update({...}) to change it without redrawing. A later conductor
        # or cable layout, and the block diagram copied into a PDF, read it then.
        # A key left at its default keeps that sheet's existing number.
        # This call also redraws the overlays now. After the script they are drawn
        # again with whatever is still set.
        "label_font_size": 0.5,  # SVG user units
        "segment_spacing": 1.5,  # gap between parallel traces, network units
        "stroke_width": 0.5 / 96,  # inches
        "min_label_segment_length": None,  # None sizes this from the network span
        # Harness Analyze skeleton. A system block diagram ignores these.
        "network_segment_stroke_width": 1.8,
        "network_segment_font_size": 11,
        "network_node_radius": 2.2,
        "network_node_font_size": 10,
    },
)
"""


def regenerate_trace_overlays(style=None):
    """
    Use this when a harness or system build should regenerate trace overlays now, or change their font size, spacing, and thickness partway through the script.

    Harness builds write the Analyze overlays: the network skeleton, conductor
    traces, and cable traces. System builds replace the block-diagram
    ``applied-traces`` layers. The build draws these again after the script
    finishes, using whatever ``trace_overlay_style`` still holds.

    The same object is what a conductor or cable layout drawing reads, and what
    is drawn onto the block diagram when a PDF copies it. Write it without
    redrawing by assigning ``svg_utils.trace_overlay_style.stroke_width`` or
    calling ``svg_utils.trace_overlay_style.update({...})``. Set the numbers
    before that drawing runs. Write the saved defaults back afterward when the
    GUI should keep them. A key left at its overlay default keeps the sheet
    drawing's existing thickness, spacing, or label size. ``stroke_width`` is
    inches. On those sheets, ``segment_spacing`` and ``label_font_size`` are
    in the drawing's own units (the layout label size is the printed px size).

    Omit ``style`` to regenerate with the style already set. Keys you leave out
    keep their current values. ``None`` restores a key's default, except
    ``min_label_segment_length``, where ``None`` means the length is chosen
    from the network span. The ribbon inserts this call with every key filled
    in. ``dict(svg_utils.trace_overlay_style)`` is the current style;
    ``dict(svg_utils.TRACE_OVERLAY_STYLE)`` is the starting point.

    **Args:**
    - `style` (dict, optional): Overlay settings.
        - `label_font_size`: trace label height in SVG user units. Default ``0.5``.
        - `segment_spacing`: gap between parallel traces, in network units. Default ``1.5``.
        - `stroke_width`: trace thickness in inches. Default ``0.5 / 96``.
        - `min_label_segment_length`: shortest sub-segment that gets a midpoint label, in network units. Default ``None`` (from the network span).
        - `network_segment_stroke_width`: harness Analyze segment stroke, in SVG user units. Default ``1.8``. A system block diagram ignores this.
        - `network_segment_font_size`: harness Analyze segment-id label size. Default ``11``.
        - `network_node_radius`: harness Analyze node marker radius. Default ``2.2``.
        - `network_node_font_size`: harness Analyze node-id label size. Default ``10``.

    **Returns:**
    - `dict`: Paths written. A harness returns ``flattened network svg``,
      ``circuits overlay``, ``cable overlay``, and ``trace overlays``.
      A system returns ``block diagram``.

    **Raises:**
    - `TypeError`: If ``style`` is not a dict, or a value is not a number.
    - `ValueError`: If ``style`` contains an unknown key, or this build is not a harness or system.
    """
    from harnice import state

    if style is not None:
        trace_overlay_style._merge(trace_overlay_style._values, style)
    project_type = getattr(state, "project_type", None)
    if project_type == "harness":
        writer_name = "harness"
    elif project_type == "system":
        writer_name = "system"
    else:
        raise ValueError(
            "svg_utils.regenerate_trace_overlays regenerates harness Analyze overlays "
            "or system block-diagram traces. "
            f"This project type is {project_type!r}."
        )
    if style is not None:
        trace_overlay_style.update(style)
    if writer_name == "harness":
        from harnice.lists import flattened_network

        return flattened_network.write_trace_overlays_svg()
    from harnice import fileio
    from harnice.utils import system_utils

    bd_path = fileio.path("block diagram")
    with open(bd_path, "r", encoding="utf-8") as f:
        original = f.read()
    updated = system_utils.apply_block_diagram_trace_overlays(original)
    if updated != original:
        with open(bd_path, "w", encoding="utf-8") as f:
            f.write(updated)
    return {"block diagram": bd_path}


def add_entire_svg_file_contents_to_group(filepath, new_group_name):
    """
    Use this when a build that is writing an SVG needs the contents of another SVG file wrapped in a new group.

    Wraps the entire contents of an SVG file in a new group element.

    Reads an SVG file, extracts its inner content (everything between `<svg>` tags),
    and wraps it in a new group element with start and end markers. The original
    file is modified in place.

    **Args:**
    - `filepath` (str): Path to the SVG file to modify.
    - `new_group_name` (str): Name to use for the new group element (will create
        `{new_group_name}-contents-start` and `{new_group_name}-contents-end` markers).

    **Raises:**
    - `ValueError`: If the file does not appear to be a valid SVG or has no inner contents.
    """
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                svg_content = file.read()

            match = re.search(r"<svg[^>]*>(.*?)</svg>", svg_content, re.DOTALL)
            if not match:
                raise ValueError(
                    "File does not appear to be a valid SVG or has no inner contents."
                )
            inner_content = match.group(1).strip()

            updated_svg_content = (
                f'<svg xmlns="http://www.w3.org/2000/svg">\n'
                f'  <g id="{new_group_name}-contents-start">\n'
                f"    {inner_content}\n"
                f"  </g>\n"
                f'  <g id="{new_group_name}-contents-end"></g>\n'
                f"</svg>\n"
            )

            with open(filepath, "w", encoding="utf-8") as file:
                file.write(updated_svg_content)

        except Exception as e:
            cli.warn(
                f"could not add contents of {os.path.basename(filepath)} "
                f"to a new group {new_group_name}: {e}"
            )
    else:
        cli.warn(
            f"could not add contents of {os.path.basename(filepath)} "
            "to a new group; file does not exist"
        )


def find_and_replace_svg_group(
    source_svg_filepath,
    source_group_name,
    destination_svg_filepath,
    destination_group_name,
):
    """
    Use this when a build that is writing an SVG needs one group's contents copied from another file, replacing that group.

    Copies SVG group content from one file to another, replacing existing group content.

    Extracts the content between group markers in a source SVG file and replaces
    the content between corresponding markers in a destination SVG file. The group
    markers are identified by `{group_name}-contents-start` and `{group_name}-contents-end` IDs.

    **Args:**
    - `source_svg_filepath` (str): Path to the source SVG file containing the group to copy.
    - `source_group_name` (str): Name of the source group to extract content from.
    - `destination_svg_filepath` (str): Path to the destination SVG file to modify.
    - `destination_group_name` (str): Name of the destination group to replace content in.

    **Returns:**
    - `int`: Always returns `1` (success indicator).

    **Raises:**
    - `ValueError`: If any of the required group markers are not found in the source
        or destination files.
    """
    with open(source_svg_filepath, "r", encoding="utf-8") as source_file:
        source_svg_content = source_file.read()
    with open(destination_svg_filepath, "r", encoding="utf-8") as target_file:
        target_svg_content = target_file.read()

    source_start_tag = f'id="{source_group_name}-contents-start"'
    source_end_tag = f'id="{source_group_name}-contents-end"'
    dest_start_tag = f'id="{destination_group_name}-contents-start"'
    dest_end_tag = f'id="{destination_group_name}-contents-end"'

    source_start_index = source_svg_content.find(source_start_tag)
    if source_start_index == -1:
        raise ValueError(
            f"Source start tag <{source_start_tag}> not found in <{source_svg_filepath}>."
        )
    source_start_index = source_svg_content.find(">", source_start_index) + 1

    source_end_index = source_svg_content.find(source_end_tag)
    if source_end_index == -1:
        raise ValueError(
            f"Source end tag <{source_end_tag}> not found in <{source_svg_filepath}>."
        )
    source_end_index = source_svg_content.rfind("<", 0, source_end_index)

    dest_start_index = target_svg_content.find(dest_start_tag)
    if dest_start_index == -1:
        raise ValueError(
            f"Target start tag <{dest_start_tag}> not found in <{destination_svg_filepath}>."
        )
    dest_start_index = target_svg_content.find(">", dest_start_index) + 1

    dest_end_index = target_svg_content.find(dest_end_tag)
    if dest_end_index == -1:
        raise ValueError(
            f"Target end tag <{dest_end_tag}> not found in <{destination_svg_filepath}>."
        )
    dest_end_index = target_svg_content.rfind("<", 0, dest_end_index)

    replacement_group_content = source_svg_content[source_start_index:source_end_index]

    updated_svg_content = (
        target_svg_content[:dest_start_index]
        + replacement_group_content
        + target_svg_content[dest_end_index:]
    )

    with open(destination_svg_filepath, "w", encoding="utf-8") as updated_file:
        updated_file.write(updated_svg_content)

    return 1


def draw_styled_path(spline_points, stroke_width_inches, appearance_dict, local_group):
    """
    Use this when a build that is writing an SVG needs a styled spline added to the current group.

    Adds a styled spline path to the local group.
    Call as if you were appending any other element to an svg group.

    Spline points are a list of dictionaries with x and y coordinates. [{"x": 0, "y": 0, "tangent": 0}, {"x": 1, "y": 1, "tangent": 0}]
    A span whose travel tangents stay within 12° of each other, or both lean off
    the same side of the chord, is drawn as that chord. A real corner or U-turn
    (tangents on opposite sides of the chord, bend above 12°) keeps a half-chord
    handle along each tangent.
    Plots physical geometry from an engineering appearance dict (conductor, cable,
    segment). Keys: base_color, outline_color, parallelstripe, perpstripe, slash_lines.
    Slash lines: direction, angle, step, color, slash_width_inches.

    Do not pass a drafting style (fill_color / stroke_color / text_color).

    If ``appearance_dict`` is missing/empty, or if it does not define ``base_color``,
    a rainbow placeholder spline is drawn.
    """

    parsed_appearance = appearance.parse(appearance_dict) if appearance_dict else None
    if not parsed_appearance or not parsed_appearance.get("base_color"):
        appearance_dict = appearance.parse(
            "{'base_color':'red', 'perpstripe':['orange','yellow','green','blue','purple']}"
        )
        stroke_width_inches = 0.01
    else:
        appearance_dict = parsed_appearance

    def cubic_controls(p0, p1):
        # A shallow bend, or tangents that both lean off the same side of the
        # chord, is the straight chord. A corner or U-turn keeps a half-chord
        # handle. A tangent facing back along the chord gets no handle.
        x0 = p0["x"]
        y0 = p0["y"]
        x1 = p1["x"]
        y1 = p1["y"]
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return x0, y0, x1, y1
        t0 = math.radians(p0.get("tangent", 0.0) or 0.0)
        t1 = math.radians(p1.get("tangent", 0.0) or 0.0)
        chord = math.atan2(dy, dx)
        d0 = (t0 - chord + math.pi) % (2.0 * math.pi) - math.pi
        d1 = (t1 - chord + math.pi) % (2.0 * math.pi) - math.pi
        turn = abs((t0 - t1 + math.pi) % (2.0 * math.pi) - math.pi)
        if d0 * d1 > 0.0 or turn <= math.radians(_TRACE_STRAIGHT_TURN_DEG):
            return (x0 + dx * 0.5, y0 + dy * 0.5, x1 - dx * 0.5, y1 - dy * 0.5)
        ctrl0 = 0.0 if math.cos(d0) < -1e-6 else dist * 0.5
        ctrl1 = 0.0 if math.cos(d1) < -1e-6 else dist * 0.5
        return (
            x0 + math.cos(t0) * ctrl0,
            y0 + math.sin(t0) * ctrl0,
            x1 - math.cos(t1) * ctrl1,
            y1 - math.sin(t1) * ctrl1,
        )

    # ---------------------------------------------------------------------
    # --- spline_to_path
    # ---------------------------------------------------------------------
    def spline_to_path(points):
        if len(points) < 2:
            return ""
        path = f"M {points[0]['x']:.3f},{-points[0]['y']:.3f}"
        for i in range(len(points) - 1):
            p0, p1 = points[i], points[i + 1]
            c1x, c1y, c2x, c2y = cubic_controls(p0, p1)
            path += f" C {c1x:.3f},{-c1y:.3f} {c2x:.3f},{-c2y:.3f} {p1['x']:.3f},{-p1['y']:.3f}"
        return path

    # ---------------------------------------------------------------------
    # --- draw consistent slanted hatches (twisted wire)
    # ---------------------------------------------------------------------
    def draw_slash_lines(points, slash_lines_dict):
        if slash_lines_dict.get("direction") in ("RH", "LH"):
            if slash_lines_dict.get("angle") is not None:
                angle_slant = slash_lines_dict.get("angle")
            else:
                angle_slant = 20
            if slash_lines_dict.get("step") is not None:
                step_dist = slash_lines_dict.get("step")
            else:
                step_dist = stroke_width * 3
            if slash_lines_dict.get("color") is not None:
                color_line = slash_lines_dict.get("color")
            else:
                color_line = "black"
            if slash_lines_dict.get("color") is not None:
                color_line = slash_lines_dict.get("color")
            else:
                color_line = "black"
            if slash_lines_dict.get("slash_width_inches") is not None:
                slash_width = slash_lines_dict.get("slash_width_inches") * 96
            else:
                slash_width = 0.25

        line_elements = []

        def bezier_eval(p0, c1, c2, p1, t):
            mt = 1 - t
            x = (
                (mt**3) * p0[0]
                + 3 * (mt**2) * t * c1[0]
                + 3 * mt * (t**2) * c2[0]
                + (t**3) * p1[0]
            )
            y = (
                (mt**3) * p0[1]
                + 3 * (mt**2) * t * c1[1]
                + 3 * mt * (t**2) * c2[1]
                + (t**3) * p1[1]
            )
            dx = (
                3 * (mt**2) * (c1[0] - p0[0])
                + 6 * mt * t * (c2[0] - c1[0])
                + 3 * (t**2) * (p1[0] - c2[0])
            )
            dy = (
                3 * (mt**2) * (c1[1] - p0[1])
                + 6 * mt * t * (c2[1] - c1[1])
                + 3 * (t**2) * (p1[1] - c2[1])
            )
            return {"x": x, "y": y, "tangent": math.degrees(math.atan2(dy, dx))}

        def bezier_length(p0, c1, c2, p1, samples=80):
            prev = bezier_eval(p0, c1, c2, p1, 0)
            L = 0.0
            for i in range(1, samples + 1):
                t = i / samples
                pt = bezier_eval(p0, c1, c2, p1, t)
                L += math.hypot(pt["x"] - prev["x"], pt["y"] - prev["y"])
                prev = pt
            return L

        # -------------------------------------------------------------
        # Iterate through Bézier segments
        for i in range(len(points) - 1):
            p0 = (points[i]["x"], points[i]["y"])
            p1 = (points[i + 1]["x"], points[i + 1]["y"])
            c1x, c1y, c2x, c2y = cubic_controls(points[i], points[i + 1])
            c1 = (c1x, c1y)
            c2 = (c2x, c2y)

            L = bezier_length(p0, c1, c2, p1)
            num_steps = max(1, int(L / step_dist))
            step_dist_actual = L / num_steps  # uniform spacing

            for z in range(num_steps + 1):
                # ------------------------------------------------------------------
                # 1. Evaluate point along Bézier curve
                # ------------------------------------------------------------------
                t_norm = min(1.0, (z * step_dist_actual) / L)
                P = bezier_eval(p0, c1, c2, p1, t_norm)

                # Centerpoint on spline
                center = (P["x"], P["y"])

                # ------------------------------------------------------------------
                # 2. Tangent and hatch angle computation
                # ------------------------------------------------------------------
                # Tangent direction of the spline at this point (radians)
                tangent_angle = math.radians(P["tangent"])

                # LH vs RH determines whether we add or subtract the slant
                if slash_lines_dict.get("direction") == "LH":
                    line_angle = tangent_angle + math.radians(angle_slant)
                else:  # "RH"
                    line_angle = tangent_angle - math.radians(angle_slant)

                # ------------------------------------------------------------------
                # 3. Compute hatch line geometry
                # ------------------------------------------------------------------
                # Shorter lines at steep slant; normalize by cos(slant)
                line_length = stroke_width / math.sin(math.radians(angle_slant))

                # Vector along hatch direction
                dx = math.cos(line_angle) * (line_length / 2)
                dy = math.sin(line_angle) * (line_length / 2)

                # Line endpoints
                x1 = center[0] - dx
                y1 = center[1] - dy
                x2 = center[0] + dx
                y2 = center[1] + dy

                # ------------------------------------------------------------------
                # 4. Append SVG element
                # ------------------------------------------------------------------
                line_elements.append(
                    f'<line x1="{x1:.2f}" y1="{-y1:.2f}" '
                    f'x2="{x2:.2f}" y2="{-y2:.2f}" '
                    f'stroke="{color_line}" stroke-width="{slash_width}" />'
                )

        local_group.extend(line_elements)

    # ---------------------------------------------------------------------
    # --- Main body rendering
    # ---------------------------------------------------------------------
    base_color = appearance_dict.get("base_color", "white")
    outline_color = appearance_dict.get("outline_color")
    path_d = spline_to_path(spline_points)

    # outline path
    stroke_width = stroke_width_inches * 96
    if outline_color:
        local_group.append(
            f'<path d="{path_d}" stroke="{outline_color}" stroke-width="{stroke_width}" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        stroke_width = stroke_width - 0.5

    # base path
    local_group.append(
        f'<path d="{path_d}" stroke="{base_color}" stroke-width="{stroke_width}" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # ---------------------------------------------------------------------
    # --- Add pattern overlays
    # ---------------------------------------------------------------------
    if appearance_dict.get("parallelstripe"):
        stripes = appearance_dict["parallelstripe"]
        num = len(stripes)
        stripe_thickness = stroke_width / 3
        usable = max(stroke_width - stripe_thickness, 0)
        if num == 1:
            offsets = [usable / 4]
        else:
            step = usable / (num - 1)
            offsets = [-usable / 2 + i * step for i in range(num)]

        def offset_spline(points, distance):
            if not distance:
                return points
            out = []
            for p in points:
                t = math.radians(p.get("tangent", 0))
                out.append(
                    {
                        **p,
                        "x": p["x"] - math.sin(t) * distance,
                        "y": p["y"] + math.cos(t) * distance,
                    }
                )
            return out

        for color, distance in zip(stripes, offsets):
            local_group.append(
                f'<path d="{spline_to_path(offset_spline(spline_points, distance))}" '
                f'stroke="{color}" stroke-width="{stripe_thickness}" fill="none" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )

    if appearance_dict.get("perpstripe"):
        stripes = appearance_dict["perpstripe"]
        num = len(stripes)
        pattern_length = 30
        dash = pattern_length / (num + 1)
        gap = pattern_length - dash
        offset = 0
        for color in stripes:
            offset += dash
            local_group.append(
                f'<path d="{path_d}" stroke="{color}" stroke-width="{stroke_width}" '
                f'stroke-dasharray="{dash},{gap}" stroke-dashoffset="{offset}" '
                f'fill="none" />'
            )

    # --- Slash lines ---
    if appearance_dict.get("slash_lines") is not None:
        slash_lines_dict = appearance_dict.get("slash_lines")
        draw_slash_lines(spline_points, slash_lines_dict)


def draw_filleted_styled_path(
    points, stroke_width_inches, appearance_dict, local_group
):
    """
    Use this when a build that is writing an SVG needs a path through corner points with a fillet at each interior corner.

    Draws a path through a list of corner points, inserting a circular fillet
    at each interior point, and appends a single SVG <path> element to
    local_group.

    Each point carries its own fillet radius.  At every interior corner the
    straight segments are trimmed back by R * tan(alpha / 2) and a cubic
    Bezier arc approximation of that radius is inserted, where alpha is the
    turn angle at that corner.  First and last points are endpoints — no
    fillet is applied there.

    The setback is clamped to half the shorter adjacent segment so fillets
    never overlap each other regardless of how tight the geometry is.

    Args:
        points:              list of {"x": float, "y": float, "radius": float}
                             Corner positions in SVG pixel coordinates.
                             "radius" is ignored for the first and last points.
        stroke_width_inches: Stroke width in inches (multiplied by 96 for px).
        appearance_dict:     Engineering appearance; at least {"base_color": <css-color>}.
        local_group:         List to which the SVG <path> element is appended.
    """
    if len(points) < 2:
        return

    parsed_appearance = appearance.parse(appearance_dict) if appearance_dict else None
    stroke_width_px = stroke_width_inches * 96
    color = (parsed_appearance or {}).get("base_color") or "#000000"
    n = len(points)

    # Precompute fillet geometry for every interior point.
    # Each entry is either None (no fillet) or
    # (fillet_start, fillet_end, ctrl_dist, v_in, v_out).
    fillets = [None] * n
    for i in range(1, n - 1):
        p_prev, p_curr, p_next = points[i - 1], points[i], points[i + 1]
        R = p_curr.get("radius", 0.0)

        dx_in = p_curr["x"] - p_prev["x"]
        dy_in = p_curr["y"] - p_prev["y"]
        len_in = math.hypot(dx_in, dy_in)

        dx_out = p_next["x"] - p_curr["x"]
        dy_out = p_next["y"] - p_curr["y"]
        len_out = math.hypot(dx_out, dy_out)

        if len_in < 1e-9 or len_out < 1e-9 or R <= 0:
            continue

        v_in = (dx_in / len_in, dy_in / len_in)
        v_out = (dx_out / len_out, dy_out / len_out)

        dot = max(-1.0, min(1.0, v_in[0] * v_out[0] + v_in[1] * v_out[1]))
        alpha = math.acos(dot)

        if alpha < math.radians(1.0):
            continue

        setback = min(R * math.tan(alpha / 2.0), len_in / 2.0, len_out / 2.0)
        actual_alpha = 2.0 * math.atan2(setback, R)
        ctrl_dist = (4.0 / 3.0) * R * math.tan(actual_alpha / 4.0)

        fs = {
            "x": p_curr["x"] - v_in[0] * setback,
            "y": p_curr["y"] - v_in[1] * setback,
        }
        fe = {
            "x": p_curr["x"] + v_out[0] * setback,
            "y": p_curr["y"] + v_out[1] * setback,
        }

        fillets[i] = (fs, fe, ctrl_dist, v_in, v_out)

    # Build the SVG path d-string.
    # Current pen position after each step is either fillet_end[i] (when a
    # fillet was drawn) or the raw point (when there was none).
    d = f"M {points[0]['x']:.3f},{-points[0]['y']:.3f}"

    for i in range(1, n):
        fillet = fillets[i] if i < n - 1 else None

        if fillet is None:
            p = points[i]
            d += f" L {p['x']:.3f},{-p['y']:.3f}"
        else:
            fs, fe, ctrl_dist, v_in, v_out = fillet

            # Straight segment up to the fillet start.
            d += f" L {fs['x']:.3f},{-fs['y']:.3f}"

            # Cubic Bezier arc through the corner.
            c1x = fs["x"] + v_in[0] * ctrl_dist
            c1y = fs["y"] + v_in[1] * ctrl_dist
            c2x = fe["x"] - v_out[0] * ctrl_dist
            c2y = fe["y"] - v_out[1] * ctrl_dist
            d += (
                f" C {c1x:.3f},{-c1y:.3f}"
                f" {c2x:.3f},{-c2y:.3f}"
                f" {fe['x']:.3f},{-fe['y']:.3f}"
            )

    local_group.append(
        f'<path d="{d}" fill="none" stroke="{color}"'
        f' stroke-width="{stroke_width_px:.3f}"'
        f' stroke-linecap="round" stroke-linejoin="round"/>'
    )


def table(
    layout_dict,
    format_dict,
    columns_list,
    content_list,
    path_to_svg,
    contents_group_name,
):
    """
    Use this when a build that is writing an SVG needs a table.

    This function is called when the user needs to build a general SVG table.
    ```python
    svg_utils.table(
        layout_dict,
        format_dict,
        columns_list,
        content_list,
        path_to_caller,
        svg_name
    )
    ```
    ### Arguments

    - `layout_dict` expects a dictionary describing in which direction the table is built
    - `format_dict` expects a dictionary of named styles (drafting ink) for the table.
    - `columns_list` expects a list containing your column header content, width, and formatting rules.
    - `content_list` expects a list containing what is actually presented on your table.
    - `path_to_svg`: File path the finished SVG table is written to.
    - `contents_group_name`: Id prefix for the SVG groups that wrap the table. The file contains ``{contents_group_name}-contents-start`` and ``{contents_group_name}-contents-end``.

    ### Returns

    - A string of SVG primatives in xml format intended to look like a table.

    ---

    ## 1. Layout

    The SVG origin (0,0) must exist somewhere in your table. Defining this correctly will help later when tables dynamically update with changing inputs.

    *example:*
    ```json
    layout = {
        "origin_corner": "top-left",
        "build_direction": "down",
    }
    ```
    Both fields are required.
    ### Origin Corner

    The origin is defined to be at one of the four corners of the first row `content[0]`. Valid options:

    - `top-left`
    - `top-right`
    - `bottom-left`
    - `bottom-right`

    ### Build Direction
    When building a table, you can choose to build rows downwards (below the previous, positive y in svg coords) or upwards (above the previous, negative y in svg coords). The direction property defines this:

    - `down` → rows appear below the previous
    - `up` → new rows appear above the previous

    ---

    ## 2. Format

    The format dictionary defines the style of the table (drafting ink).

    Any number of style keys can be defined and named with an identifier that is called when printing that row. This allows you to have rows that whose style can be varied dynamically with the table contents.

    *example:*
    ```json
    format_dict={
        "globals": {
            "font_size": 11,
            "row_height": 20,
        },
        "header": {
            "font_weight":"B",
            "fill_color": "lightgray",
        },
        "row_with_bubble": {
            "row_height": 40,
        },
    }
    ```

    The only reserved key is `globals` which can optionally be used to define fallbacks for any row that does not have a style explicitly called out.

    ### Format Arguments
    Any of the following keys can be defined in any of the format dictionaries.

    - `font_size` *(number, default=12)* Default font size (px) for all text
    - `font_family` *(string, default=helvetica)* Default font family (e.g., "Arial", "Helvetica")
    - `font_weight`*(`BIU`, default=None)* Add each character for bold, italic, or underline
    - `row_height` *(number, default=18)* Self-explanatory (px)
    - `padding` *(number, default=3)* Default text inset from border if not center or middle justified
    - `line_spacing` *(number, default=14)* Vertical spacing between multi-line text entries
    - `justify` *(`left` | `center` | `right`, default=center)* Default horizontal alignment
    - `valign` *(`top` | `middle` | `bottom`, default=center)* Default vertical alignment
    - `fill_color` *(default=white)* Cell background. Style color token (`#rrggbb` or CSS name).
    - `stroke_color` *(default=black)* Border line color (style)
    - `stroke_width` *(number, default=1)* Border width
    - `text_color` *(default=black)* Glyph color (style)

    ### Style Resolution Order
    If something is defined at the row level, it takes precedent over some parameter defined at the column level, which takes precedent over a definition in key `globals`, if defined. If something is not defined at all, the above defaults will apply.

    ### Color Standard

    Colors are style keys (`fill_color`, `stroke_color`, `text_color`). CSS names are hexified at paint. Convert an instance appearance to those keys at the instance, before calling ``table``.

    ---

    ## 3. Columns

    The column argument is a list of dictionaries containing definition of how many columns there are, the order in which they exist, how to reference them, and any applicable formatting.

    *ex:*
    ```json
    columns_list=[
        {
            "name": "rev"
            "width": 60,
            "justify": "center"
        },
        {
            "name": "updated"
            "width": 260,
        },
            "name": "status"
            "width": 120,
            "fill_color": "yellow",
        }
    ]
    ```

    ### Column Arguments
    Each field must have the following required keys:

    - `name` *(string)* Used to identify a column when defining contents later. Must be unique.
    - `width` *(number)* Self-explanatory (px)

    You may add any formatting key as defined in the formatting section as needed.

    Note that the order of the items in the list represents the order in which they will be printed from left to right, regardless of the layout you've chosen for this table.

    ---

    ## 4. Content Structure

    The table content will be referenced from information stored in this argument. It is a list (rows) of dictionaries (columns).

    ```json
    content_list = [
        {
            "format_key": "header"
            "columns": {
                "rev": "REV",
                "updated": "UPDATED",
                "status": "STATUS",
            }
        },
        {
            "columns": {
                "rev": "1",
                "updated": "12/6/25",
                "status": "requires review",
            }
        },
        {
            "columns": {
                "rev": "2",
                "updated": ["12/6/25", "update incomplete"],
            }
        },
        {
            "format_key": "row_with_bubble",
            "columns": {
                "rev": {
                    "instance_name": "rev3-bubble",
                    "item_type": "flagnote"
                },
                "updated": "12/6/25",
                "status": "clear"
            }
        }
    ]
    ```

    Content (the root argument) is a list. Each entry of the root list is representative of a row's worth of data.

    Each entry of that list must contain the dictionary `columns` and may contain dictionary `format_key`.

    `format_key` may only contain one value which corresponds to the name of a key in the format dictionary. It selects the style of that row. If it is not defined, the format of that row will fall back to globals and defaults. Custom formatting of individual cells is not supported.

    `columns` is a dictionary that contains the actual content you want to appear in each column. The name of each key at this level must match one of the keys in the `columns` argument. It is agnostic to order, and by leaving a key out, simply nothing will appear in that cell. Existing formatting (cell fill and border) will still apply.

    The value of each column key may take one of the following forms:

    - string or number → single-line text, prints directly
    - list[str] → multi-line text where the 0th element prints highest within the cell. Use format key `line_spacing` as needed.
    - dict → custom

    ### Importing a Symbol into a Cell

    If you add a dictionary to one of the content cells, content start/end groups will be written into your svg. This will allow the user to generate and/or import symbols into the table using their own logic, without regard for placement into the table.

    ```python
    #from your macro or wherever you're building the table from...
    example_symbol = {
        "lib_repo": instance.get("lib_repo"),
        "item_type": "flagnote",
        "mpn": instance.get("mpn"),
        "instance_name": f"bubble{build_note_number}",
        "note_text": build_note_number,
    }
    symbols_to_build=[example_symbol]

    svg_utils.table(
        layout_dict,
        format_dict,
        columns_list,
        content_list,
        os.dirname(path_to_table_svg),
        artifact_id
    )

    # user import logic
    for symbol in symbols_to_build:
        path_to_symbol = #...
        library_utils.pull(
            symbol,
            update_instances_list=False,
            destination_directory=path_to_symbol,
        )

        svg_utils.find_and_replace_svg_group(
            os.path.join(path_to_symbol, f"{symbol.get('instance_name')}-drawing.svg"),
            symbol.get("instance_name"),
            path_to_table_svg,
            symbol.get("instance_name")
        )
    """

    # --- Default Style Values (Local to the table() function) ---
    DEFAULTS = {
        "font_size": 12,
        "font_family": "helvetica",
        "font_weight": None,
        "row_height": 0.16 * 96,
        "padding": 3,
        "line_spacing": 14,
        "justify": "center",
        "valign": "middle",
        "fill_color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 1,
        "text_color": "#000000",
    }

    # --- Helper functions ---

    def _validate_layout(layout):
        """Validates the layout dictionary."""
        valid_corners = {"top-left", "top-right", "bottom-left", "bottom-right"}
        valid_directions = {"down", "up"}
        corner = layout.get("origin_corner")
        direction = layout.get("build_direction")
        if corner not in valid_corners:
            raise ValueError(
                f"Invalid origin_corner: {corner}. Must be one of {valid_corners}."
            )
        if direction not in valid_directions:
            raise ValueError(
                f"Invalid build_direction: {direction}. Must be one of {valid_directions}."
            )
        return layout

    def _validate_columns(columns_list):
        """Validates the columns list, ensuring 'name' and 'width' are present."""
        if not columns_list:
            raise ValueError("columns_list cannot be empty.")
        names = set()
        for col in columns_list:
            if "name" not in col or "width" not in col:
                raise ValueError("Each column must have 'name' and 'width' keys.")
            if col["name"] in names:
                raise ValueError(f"Duplicate column name: {col['name']}.")
            names.add(col["name"])
        return columns_list

    _COLOR_KEYS = ("fill_color", "stroke_color", "text_color")

    def _apply_format_layer(style, layer):
        """Merge one format layer into cell style. Color keys are hexified; other DEFAULTS keys copy through."""
        if not layer:
            return
        for k in _COLOR_KEYS:
            raw = layer.get(k)
            if isinstance(raw, str) and raw:
                style[k] = appearance.normalize_color_into_rrggbb(raw)
        style.update(
            {k: v for k, v in layer.items() if k in DEFAULTS and k not in _COLOR_KEYS}
        )

    def _resolve_style(row_format_key, col_data, format_dict, columns_list):
        """Resolves the final style for a cell."""
        style = DEFAULTS.copy()
        _apply_format_layer(style, format_dict.get("globals", {}))
        col_name = col_data.get("name")
        column_def = next((c for c in columns_list if c["name"] == col_name), {})
        _apply_format_layer(style, column_def)
        _apply_format_layer(style, format_dict.get(row_format_key))
        return style

    def _generate_symbol_placeholder(instance_name, bubble_x, bubble_y):
        """Generates the SVG group structure placeholder."""
        svg_lines = []
        svg_lines.append(
            f'<g id="{instance_name}" transform="translate({bubble_x},{bubble_y})">'
        )
        svg_lines.append(f'  <g id="{instance_name}-contents-start">')
        svg_lines.append("  </g>")
        svg_lines.append(f'  <g id="{instance_name}-contents-end"/>')
        svg_lines.append("</g>")
        return "\n".join(svg_lines)

    def _draw_cell_content(
        x, y, width, height, content, style, columns_list, format_dict
    ):
        """Generates the SVG for the cell's content (text or symbol)."""
        svg_primitives = []
        instances_to_copy_in = []

        if isinstance(content, dict) and "instance_name" in content:
            instance_name = content["instance_name"]
            item_type = content.get("item_type")

            align_x = (
                width / 2
                if style["justify"] == "center"
                else (
                    width - style["padding"]
                    if style["justify"] == "right"
                    else style["padding"]
                )
            )
            align_y = (
                height / 2
                if style["valign"] == "middle"
                else (
                    height - style["padding"]
                    if style["valign"] == "bottom"
                    else style["padding"]
                )
            )

            symbol_xml = _generate_symbol_placeholder(
                instance_name=instance_name, bubble_x=x + align_x, bubble_y=y + align_y
            )
            instances_to_copy_in.append(
                {"item_type": item_type, "instance_name": instance_name}
            )
            svg_primitives.append(symbol_xml)

        else:
            text_lines = (
                [str(content)]
                if isinstance(content, (str, int, float))
                else [str(line) for line in content]
                if isinstance(content, list)
                else []
            )
            if not text_lines:
                return "", []

            x_pos = x
            text_anchor = "start"
            if style["justify"] == "center":
                x_pos += width / 2
                text_anchor = "middle"
            elif style["justify"] == "right":
                x_pos += width - style["padding"]
                text_anchor = "end"
            elif style["justify"] == "left":
                x_pos += style["padding"]
                text_anchor = "start"

            num_lines = len(text_lines)
            total_text_height = (num_lines - 1) * style["line_spacing"] + style[
                "font_size"
            ]
            y_start = y
            if style["valign"] == "middle":
                y_start += (height - total_text_height) / 2
            elif style["valign"] == "bottom":
                y_start += height - total_text_height - style["padding"]
            elif style["valign"] == "top":
                y_start += style["padding"]
            y_pos = y_start + style["font_size"] * 0.8

            text_style = {
                "font-size": f"{style['font_size']}px",
                "font-family": style["font_family"],
                "fill": style["text_color"],
                "text-anchor": text_anchor,
            }
            if style["font_weight"]:
                if "B" in style["font_weight"]:
                    text_style["font-weight"] = "bold"
                if "I" in style["font_weight"]:
                    text_style["font-style"] = "italic"
                if "U" in style["font_weight"]:
                    text_style["text-decoration"] = "underline"
            style_str = "; ".join(f"{k}: {v}" for k, v in text_style.items())

            for i, line in enumerate(text_lines):
                current_y = y_pos + i * style["line_spacing"]
                svg_primitives.append(
                    f'<text x="{x_pos}" y="{current_y}" style="{style_str}">{line}</text>'
                )

        return "\n".join(svg_primitives), instances_to_copy_in

    def _draw_cell_rect(x, y, width, height, style):
        """Generates the SVG for the cell's background and border."""
        rect_style = {
            "fill": style["fill_color"],
            "stroke": style["stroke_color"],
            "stroke-width": style["stroke_width"],
        }
        style_str = "; ".join(f"{k}: {v}" for k, v in rect_style.items())
        return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" style="{style_str}" />'

    # ====================================================================
    # MAIN FUNCTION LOGIC START
    # ====================================================================

    # 1. INITIAL VALIDATION (and state definition)
    layout = _validate_layout(layout_dict)
    columns = _validate_columns(columns_list)
    total_width = sum(col["width"] for col in columns)

    # ... (Setup for BUILD_SVG LOGIC remains unchanged) ...
    svg_rows = []
    col_x_starts = [0]
    current_x = 0
    for col in columns[:-1]:
        current_x += col["width"]
        col_x_starts.append(current_x)

    row_heights = [
        _resolve_style(row.get("format_key"), {}, format_dict, columns).get(
            "row_height", DEFAULTS["row_height"]
        )
        for row in content_list
    ]
    total_table_height = sum(row_heights)
    row_height_0 = row_heights[0]

    current_y_offset = 0
    instances_to_copy_in = []

    # 3. BUILD ROW BY ROW

    # reverse content list if building upwards so the first row stays on top but is now printed last
    if layout["build_direction"] == "up":
        content_list = list(reversed(content_list))

    for row_index, row_data in enumerate(content_list):
        row_key = row_data.get("format_key")
        row_height = row_heights[row_index]
        row_svg = []

        if layout["build_direction"] == "down":
            cell_y_start = current_y_offset
            current_y_offset += row_height
        elif layout["build_direction"] == "up":
            current_y_offset -= row_height
            cell_y_start = current_y_offset

        for col_index, col_def in enumerate(columns):
            col_name = col_def["name"]
            col_width = col_def["width"]
            cell_content = row_data.get("columns", {}).get(col_name)
            cell_style = _resolve_style(row_key, col_def, format_dict, columns)
            cell_x_start = col_x_starts[col_index]

            rect_svg = _draw_cell_rect(
                cell_x_start, cell_y_start, col_width, row_height, cell_style
            )
            row_svg.append(rect_svg)

            if cell_content is not None:
                content_svg, instances = _draw_cell_content(
                    cell_x_start,
                    cell_y_start,
                    col_width,
                    row_height,
                    cell_content,
                    cell_style,
                    columns,
                    format_dict,
                )
                row_svg.append(content_svg)
                instances_to_copy_in.extend(instances)

        svg_rows.append("\n".join(row_svg))

    # 4. FINAL TRANSFORM CALCULATION
    tx = 0
    ty = 0

    if layout["origin_corner"] in ("top-right", "bottom-right"):
        tx = -total_width

    if layout["build_direction"] == "down":
        if layout["origin_corner"] in ("bottom-left", "bottom-right"):
            ty = -row_height_0
    elif layout["build_direction"] == "up":
        if layout["origin_corner"] in ("top-left", "top-right"):
            ty = total_table_height

    table_contents = "\n".join(svg_rows)

    # 5. WRAP, SAVE, AND INJECT
    group_output = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
  <g id="{contents_group_name}-contents-start">
    <g id="translate" transform="translate({tx}, {ty})">
{table_contents}
    </g>
  </g>
  <g id="{contents_group_name}-contents-end"/>
</svg>"""

    # Save the master SVG file
    with open(path_to_svg, "w") as f:
        f.write(group_output.strip())


def normalize_angle_deg(deg):
    """Normalize degrees into ``[0, 360)``."""
    a = float(deg or 0) % 360
    if a < 0:
        a += 360
    return a


# Project convention for vertical SVG text: read bottom→top (glyph baseline on the RIGHT).
# Wire labels use ``rotate(-angle)``; device groups use parent ``rotate(+worldDeg)``. Those
# opposite signs need dual upright ranges so both land on the same visual convention:
#   - upright_wire_label_angle: prefer 90° when vertical (for rotate(-angle))
#   - text_world_orientation_needs_upright_flip: prefer 270° when vertical (for rotate(+deg))


def upright_wire_label_angle(angle):
    """
    Normalize a wire-tangent angle for labels drawn with ``rotate(-angle)``.

    Keeps text left-to-right on near-horizontal wires and bottom-to-top
    (baseline right) on vertical wires. Flips the open interval that would
    otherwise read top-to-bottom or upside-down.
    """
    a = normalize_angle_deg(angle)
    # Inclusive 270 so exact verticals prefer 90° → rotate(-90) → baseline right.
    if 90 < a <= 270:
        a = (a + 180) % 360
    return a


def text_world_orientation_needs_upright_flip(world_deg):
    """
    True when text under parent ``rotate(+worldDeg)`` would read upside-down
    or top-to-bottom. Callers then apply ``rotate(180)`` about the text anchor.

    Prefer LTR (≈0°) or bottom-to-top (≈270° / baseline right) when vertical.
    Dual of :func:`upright_wire_label_angle` (see comment above that helper).
    """
    a = normalize_angle_deg(world_deg)
    return 90 <= a < 270


def escape_svg_text(text):
    """Escape characters that would break XML when interpolated into SVG markup."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def label_svg(
    x,
    y,
    angle,
    text,
    text_color="black",
    background_color="white",
    outline="black",
    font_size=8,
    font_family="Arial, Helvetica, sans-serif",
    font_weight="normal",
):
    """
    Use this when a build that is writing an SVG needs a text label in a box, aligned to a wire.

    Generate an SVG label: text in a rectangular box, aligned to a wire tangent.

    Args:
        x: X position in SVG **user units** (same space as path geometry)
        y: Y position in SVG **user units**
        angle: Wire tangent angle in degrees; text is rendered parallel to wire
            via ``rotate(-angle)`` after :func:`upright_wire_label_angle`
            (vertical text reads bottom→top, baseline on the right)
        text: Label content (drafting ink, not a physical object)
        text_color: Style text color (CSS name or hex)
        background_color: Style fill for the box
        outline: Style stroke for the box
        font_size: Single control in SVG **user units**: nominal text height, rectangle height
            ``≈ font_size + 2×margin``, width from content + padding, with ``margin = 0.32×font_size``.
            Passed as ``font-size`` on ``<text>`` (presentation attribute), not CSS ``style``.
        font_family: CSS font-family string
        font_weight: CSS font-weight string

    Returns:
        SVG string for the label group element
    """
    text_str = str(text) if text is not None else ""
    if not text_str.strip():
        text_str = "?"

    text_escaped = escape_svg_text(text_str)
    y_svg = -y

    angle = upright_wire_label_angle(angle)

    background_color = appearance.normalize_color_into_rrggbb(background_color)
    text_color = appearance.normalize_color_into_rrggbb(text_color)
    outline = appearance.normalize_color_into_rrggbb(outline)

    # One length ``font_size`` (user units) sets nominal text height; margin and box follow.
    s = float(font_size)
    margin = s * 0.32
    est_char_w = s * 0.55
    content_w = len(text_str) * est_char_w
    width = max(s * 1.25, content_w + 2.0 * margin)
    height = s + 2.0 * margin
    rect_x = -width / 2
    rect_y = -height / 2

    stroke_color = (
        outline if appearance.to_rgb(background_color) != (0, 0, 0) else background_color
    )
    stroke_width = max(0.03, min(0.2, s * 0.012))

    # font-size must be a presentation attribute (SVG user units). A unitless font-size inside
    # the CSS ``style`` string is invalid in HTML/CSS and UAs ignore it → ~16px screen text that
    # does not scale with viewBox, so changing label_font_size in Python had no visible effect.
    return f"""
<g transform="translate({x:.3f},{y_svg:.3f}) rotate({-angle:.3f})">
  <rect x="{rect_x:.3f}" y="{rect_y:.3f}"
        width="{width:.3f}" height="{height:.3f}"
        fill="{background_color}" stroke="{stroke_color}" stroke-width="{stroke_width}"/>
  <text x="0" y="0" text-anchor="middle" font-size="{font_size:.4f}"
        style="fill:{text_color};dominant-baseline:middle;font-weight:{font_weight};font-family:{font_family}">{text_escaped}</text>
</g>
""".strip()


def _svg_xml_attr_escape(val):
    """Escape ``&``, ``<``, ``"`` for double-quoted XML/SVG attributes."""
    return (
        str(val)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
    )


def _trace_group_open_tag(instance, group_opacity=None):
    """
    Opening ``<g>`` for one routed trace: unique ``id``, ``data-harnice-trace-label`` from
    ``instance_name``. Optional ``opacity`` (e.g. ``1`` for fully visible in the file).
    """
    inst_name = str(instance.get("instance_name") or "trace")
    group_id = re.sub(r"[^A-Za-z0-9_.-]", "_", f"harnice_trace_{inst_name}")
    if not group_id:
        group_id = "harnice_trace"
    if group_id[0].isdigit():
        group_id = "_" + group_id
    group_id = group_id[:240]
    esc = _svg_xml_attr_escape(inst_name)
    op_attr = ""
    if group_opacity is not None:
        op_attr = f' opacity="{group_opacity}"'
    return f'<g id="{group_id}" data-harnice-trace-label="{esc}"{op_attr}>'


# A spline span this straight is drawn as the chord (about a 1:5 slope).
_TRACE_STRAIGHT_TURN_DEG = 12.0


def _channel_type_default_appearance(item, channel_type, signal):
    """Appearance from channel_types.tsv for a channel trace or a signal trace."""
    try:
        from harnice.project_types import chtype

        if item == "circuit":
            by_sig = chtype.signal_default_appearances(channel_type)
            spec = by_sig.get(signal) if signal else None
            return spec if isinstance(spec, dict) else None
        if item in ("channel", "harness-channel"):
            return chtype.channel_default_appearance(channel_type)
    except Exception:
        return None
    return None


def _resolved_trace_appearance(instance, cache):
    """Instance appearance, else the channel-type default for this trace.

    A circuit uses ``signal_default_appearances`` for its signal. A channel
    trace uses ``channel_default_appearance``. An instance appearance that
    already has ``base_color`` wins.
    """
    raw = (instance or {}).get("appearance")
    parsed = appearance.parse(raw) if raw else None
    if isinstance(parsed, dict) and parsed.get("base_color"):
        return parsed
    item = str((instance or {}).get("item_type") or "").strip()
    channel_type = (
        (instance or {}).get("this_channel_from_channel_type")
        or (instance or {}).get("this_channel_to_channel_type")
        or ""
    )
    channel_type = str(channel_type).strip()
    if not channel_type:
        return parsed
    signal = str((instance or {}).get("signal_of_channel_type") or "").strip()
    key = (item, channel_type, signal if item == "circuit" else "")
    if key not in cache:
        cache[key] = _channel_type_default_appearance(item, channel_type, signal)
    hit = cache[key]
    if isinstance(hit, dict) and hit.get("base_color"):
        return hit
    return parsed


def _label_square_colors(parsed, text_color, background_color, outline):
    """Paint a trace label square from an appearance, or keep the given defaults."""
    if not isinstance(parsed, dict):
        return text_color, background_color, outline
    fill = parsed.get("base_color") or parsed.get("outline_color")
    if not isinstance(fill, str) or not fill.strip():
        return text_color, background_color, outline
    ink = appearance.black_or_white_to_contrast_with_color(fill)
    stroke = parsed.get("outline_color") or "#000000"
    return ink, fill, stroke


def _drawn_trace_stroke_px(instance, stroke_width_inches, appearance_cache=None):
    """SVG stroke width actually used for this instance (rainbow placeholder is 0.01 in)."""
    parsed = _resolved_trace_appearance(
        instance, appearance_cache if appearance_cache is not None else {}
    )
    if not parsed or not parsed.get("base_color"):
        return 0.01 * 96
    return float(stroke_width_inches) * 96


def _multi_ch_junction_dot_radius(jid, instances, stroke_width_inches, appearance_cache=None):
    """Dot radius so the circle diameter is 2× the junction traces' stroke width."""
    width = 0.0
    for inst in instances or []:
        if (inst.get("multi_ch_junction_id") or "").strip() != jid:
            continue
        width = max(width, _drawn_trace_stroke_px(inst, stroke_width_inches, appearance_cache))
    if width <= 0:
        width = 0.01 * 96
    return width


def _trace_lateral_offsets(num_on_seg, segment_spacing):
    """Centered lateral offsets for ``num_on_seg`` parallel traces on one segment."""
    return [
        (idx - (num_on_seg / 2) - 0.5) * segment_spacing
        for idx in range(1, num_on_seg + 1)
    ]


def _trace_span_tangent(p, q):
    """Travel direction in the same degrees ``draw_styled_path`` uses.

    Graph Y grows downward. The stored point chain flips Y, so the angle is negated.
    """
    dx = q["x"] - p["x"]
    dy = q["y"] - p["y"]
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return 0.0
    return (-math.degrees(math.atan2(dy, dx))) % 360.0


def _trace_endpoint_contact(point, departs):
    """Path-chain point (Y already flipped) → contact in graph/SVG user units."""
    return {
        "x": point["x"],
        "y": -point["y"],
        "tangent": point.get("tangent", 0.0),
        "departs": departs,
    }


def _is_wire_junction_node(node_id):
    return str(node_id).startswith("wirejunction-")


def _node_is_self_hop_free(node_id, connector_node_ids):
    """A loopback may turn around on a wire junction or a non-connector harness node.

    Block diagrams name the free ends ``wirejunction-``. A harness stub such as
    ``far`` is free when the caller passes the connector-node ids, so the walk
    still stops at the next connector.
    """
    if _is_wire_junction_node(node_id):
        return True
    if connector_node_ids:
        return node_id not in connector_node_ids
    return False


def _free_node_distance(graph, origin_id, node_id):
    """Euclidean distance from ``origin_id`` to ``node_id``, or ``inf`` if unknown."""
    nodes = graph.get("nodes") or {}
    origin = nodes.get(origin_id) or {}
    node = nodes.get(node_id) or {}
    try:
        return math.hypot(
            float(node["x"]) - float(origin["x"]),
            float(node["y"]) - float(origin["y"]),
        )
    except (KeyError, TypeError, ValueError):
        return float("inf")


def _self_hop_outbound(graph, node_id, connector_node_ids=None):
    """One segment from a connector to the nearest free wire end.

    The loop turns on the free node reached in the fewest segments. Every
    free neighbor is one hop, so that is the adjacent wire junction (or
    harness node outside ``connector_node_ids``) closest to ``node_id``.
    The walk stops before another connector. Returns ``(segments,
    directions)`` toward that end, or ``None`` when the connector has no
    free stub.
    """
    neighbors = []
    for seg_uuid, info in (graph.get("segments") or {}).items():
        a = info.get("node_at_end_a")
        b = info.get("node_at_end_b")
        if not a or not b or a == b:
            continue
        a_free = _node_is_self_hop_free(a, connector_node_ids)
        b_free = _node_is_self_hop_free(b, connector_node_ids)
        if a == node_id and b_free:
            neighbors.append((b, seg_uuid, "a_to_b"))
        elif b == node_id and a_free:
            neighbors.append((a, seg_uuid, "b_to_a"))
    if not neighbors:
        return None

    def rank(item):
        nxt, seg, _direction = item
        return (_free_node_distance(graph, node_id, nxt), str(nxt), str(seg))

    _nxt, seg, direction = min(neighbors, key=rank)
    return [seg], [direction]


def _self_hop_fallback_direction(graph, node_id):
    """Unit vector into the largest gap between wires already on this node."""
    node = graph["nodes"][node_id]
    angles = []
    for info in (graph.get("segments") or {}).values():
        a = info.get("node_at_end_a")
        b = info.get("node_at_end_b")
        if a == node_id:
            other = b
        elif b == node_id:
            other = a
        else:
            continue
        if not other or other == node_id or other not in graph["nodes"]:
            continue
        other_xy = graph["nodes"][other]
        angles.append(
            math.atan2(other_xy["y"] - node["y"], other_xy["x"] - node["x"])
        )
    if not angles:
        return (1.0, 0.0)
    angles.sort()
    best_gap = -1.0
    best_mid = 0.0
    for i, angle in enumerate(angles):
        nxt = angles[(i + 1) % len(angles)]
        gap = (nxt - angle) % (2.0 * math.pi)
        if gap > best_gap:
            best_gap = gap
            best_mid = angle + gap / 2.0
    return (math.cos(best_mid), math.sin(best_mid))


def _self_hop_local_point_chain(graph, node_id, segment_spacing):
    """Short out-and-back when the connector has no free harness stub.

    Two contacts sit on the connector, ``segment_spacing`` apart, and the U
    leaves them along the open side of the node.
    """
    node = graph["nodes"][node_id]
    ux, uy = _self_hop_fallback_direction(graph, node_id)
    px, py = -uy, ux
    half = float(segment_spacing) / 2.0
    length = max(8.0, 4.0 * float(segment_spacing))
    ox, oy = float(node["x"]), float(node["y"])
    out_tangent = _trace_span_tangent({"x": 0.0, "y": 0.0}, {"x": ux, "y": uy})
    back_tangent = (out_tangent + 180.0) % 360.0

    def pt(gx, gy, tangent):
        return {"x": gx, "y": -gy, "tangent": tangent}

    sx, sy = ox + px * half, oy + py * half
    ex, ey = ox - px * half, oy - py * half
    return [
        pt(sx, sy, out_tangent),
        pt(sx + ux * length, sy + uy * length, out_tangent),
        pt(ex + ux * length, ey + uy * length, back_tangent),
        pt(ex, ey, back_tangent),
    ]


def _reverse_trace_chain(chain):
    """Same points, opposite travel, so a lane can be the outbound leg."""
    flipped = []
    for point in reversed(chain):
        flipped.append(
            {
                **point,
                "tangent": (point.get("tangent", 0.0) + 180.0) % 360.0,
            }
        )
    return flipped


def _peer_face_for_self_hop(instances, endpoint_contacts, hop_instance, channel_id, node_id):
    """``(other_node_id, contact)`` where ``channel_id`` already landed on this device's other face."""
    if not endpoint_contacts or not channel_id:
        return None
    group = (hop_instance.get("channel_group") or "").strip()
    refdes = str(node_id).split(".", 1)[0]
    prefix = refdes + "."
    for inst in instances:
        if inst is hop_instance:
            continue
        if group and (inst.get("channel_group") or "").strip() != group:
            continue
        bag = endpoint_contacts.get(inst.get("instance_name")) or {}
        from_conn = (
            f"{(inst.get('this_harness_from_device_refdes') or '').strip()}."
            f"{(inst.get('this_harness_from_device_connector_name') or '').strip()}"
        )
        to_conn = (
            f"{(inst.get('this_harness_to_device_refdes') or '').strip()}."
            f"{(inst.get('this_harness_to_device_connector_name') or '').strip()}"
        )
        for nid, contact in bag.items():
            if nid in ("__self_hop__", node_id):
                continue
            if not isinstance(contact, dict) or "x" not in contact:
                continue
            if not str(nid).startswith(prefix):
                continue
            if nid == from_conn:
                end_channel = (inst.get("this_harness_from_device_channel_id") or "").strip()
            elif nid == to_conn:
                end_channel = (inst.get("this_harness_to_device_channel_id") or "").strip()
            else:
                continue
            if end_channel == channel_id:
                return nid, contact
    return None


def _orient_self_hop_chains(out_chain, back_chain, node_xy, other_node_xy, other_contact):
    """Put the outbound leg on the same side of the disconnect as the other face's contact."""
    if not out_chain or not back_chain or not other_contact or not other_node_xy:
        return out_chain + back_chain
    vx = other_node_xy[0] - node_xy[0]
    vy = other_node_xy[1] - node_xy[1]
    if abs(vx) < 1e-9 and abs(vy) < 1e-9:
        return out_chain + back_chain
    px, py = -vy, vx

    def side(x, y):
        return (x - node_xy[0]) * px + (y - node_xy[1]) * py

    out_pt = out_chain[0]
    out_side = side(out_pt["x"], -out_pt["y"])
    other_side = side(other_contact["x"], other_contact["y"])
    if out_side * other_side >= 0:
        return out_chain + back_chain
    return _reverse_trace_chain(back_chain) + _reverse_trace_chain(out_chain)


def _assemble_trace_point_chain(
    graph,
    points_to_pass_through,
    path_segments,
    path_directions,
    inst_name,
    lane_offsets=None,
):
    """Offset point chain for one already-routed path, in ``draw_styled_path`` space."""
    point_chain = []
    for seg_uuid, direction in zip(path_segments, path_directions):
        seg_info = graph["segments"][seg_uuid]
        node_a_id = seg_info["node_at_end_a"]
        node_b_id = seg_info["node_at_end_b"]
        waypoints = list(seg_info.get("waypoints") or [])
        if direction == "a_to_b":
            ordered_nodes = [node_a_id, node_b_id]
            midpoints = waypoints
        else:
            ordered_nodes = [node_b_id, node_a_id]
            midpoints = list(reversed(waypoints))

        start_id, end_id = ordered_nodes
        geom = [graph["nodes"][start_id]] + midpoints + [graph["nodes"][end_id]]
        tangents = [
            _trace_span_tangent(geom[i], geom[i + 1]) for i in range(len(geom) - 1)
        ] or [0.0]
        tangents.append(tangents[-1])
        offset = 0.0
        if lane_offsets is not None:
            offset = lane_offsets.get(seg_uuid, {}).get(inst_name, 0.0)
            if direction != "a_to_b":
                offset = -offset

        def append_node_contact(nid, tangent):
            try:
                pt = points_to_pass_through[nid][seg_uuid][inst_name]
            except KeyError:
                return
            point_chain.append(
                {
                    "x": pt["x"],
                    "y": pt["y"],
                    "tangent": tangent,
                    "seg_uuid": seg_uuid,
                }
            )

        append_node_contact(start_id, tangents[0])
        for mid_index, waypoint in enumerate(midpoints):
            # Same lateral offset as the node contacts, so a polyline stays a
            # parallel lane instead of diving onto the harness centerline.
            # Two points keep each span straight through a corner.
            for span_i, tangent in (
                (mid_index, tangents[mid_index]),
                (mid_index + 1, tangents[mid_index + 1]),
            ):
                p0 = geom[span_i]
                p1 = geom[min(span_i + 1, len(geom) - 1)]
                away = math.atan2(p1["y"] - p0["y"], p1["x"] - p0["x"])
                ox = offset * math.cos(away + math.pi / 2.0)
                oy = offset * math.sin(away + math.pi / 2.0)
                point_chain.append(
                    {
                        "x": waypoint["x"] + ox,
                        "y": -(waypoint["y"] + oy),
                        "tangent": tangent,
                        "seg_uuid": seg_uuid,
                    }
                )
        append_node_contact(end_id, tangents[len(midpoints)])
    return point_chain


def draw_segments_across_paths(
    input_instances,
    input_network_2D,
    stroke_width,
    segment_spacing,
    min_label_segment_length=30.0,
    label_font_size=8,
    from_node_id_field=None,
    to_node_id_field=None,
    trace_group_opacity=None,
    endpoint_contacts=None,
    connector_node_ids=None,
):
    """
    Use this when a build that is writing an SVG needs segment instances drawn along a 2D wire network, with parallel paths offset.

    Maps segment-type instances onto a 2D wire network, offsets parallel paths
    at shared nodes, draws each path and its labels, and returns raw SVG markup.

    Junction geometry:
        - Every node contact sits on the line through the node perpendicular to
          its incident segment, at a fixed multiple of ``segment_spacing``. The
          same offset is applied to interior waypoints, so each lane stays
          parallel to its harness segment at constant spacing.
        - At a bend or T, the path steps from one segment's offset contact to the
          next; a shallow spline span (tangents within 12°, or both leaning off
          the same side of the chord) is drawn as that chord so the corner does
          not bow off the harness.

    Args:
        input_instances: list of instance dicts, each with:
            - instance_name: str
            - from/to node fields (see from_node_id_field / to_node_id_field below)
            - (optional) appearance: dict or str passed to ``draw_styled_path``.
              If it is missing/empty or omits ``base_color``, the rainbow placeholder is drawn.
            - (optional) print_name: str  label at the midpoint of each long sub-segment; omit to draw no midpoint labels
            - (optional) print_name_at_end_a: str  label at the start of the path; omit to draw no start label
            - (optional) print_name_at_end_b: str  label at the end of the path; omit to draw no end label
        input_network_2D: dict with:
            - 'nodes': {node_id: {'x': float, 'y': float}}  (coordinates in inches)
            - 'segments': {seg_uuid: {'node_at_end_a': node_id, 'node_at_end_b': node_id,
              'waypoints': optional [{'x', 'y'}, ...] interior stations from A to B}}
        stroke_width: inches, passed to ``draw_styled_path`` as ``stroke_width_inches`` (×96 for SVG stroke-width)
        segment_spacing: lateral spread between parallel wires at shared nodes (in input units)
        min_label_segment_length: minimum sub-segment length to render a midpoint label (in input units)
        label_font_size: SVG **user units** for ``label_svg`` (same space as node x/y). Block diagram
            callers should pass inches×96 so text scales like stroke (e.g. ``0.5 * 96`` with ``stroke_width=0.5``).
        from_node_id_field: instance field whose value is the full from-node ID.
            If None, falls back to:
            f"{this_harness_from_device_refdes}.{this_harness_from_device_connector_name}"
        to_node_id_field: instance field whose value is the full to-node ID.
            If None, falls back to:
            f"{this_harness_to_device_refdes}.{this_harness_to_device_connector_name}"
        trace_group_opacity: optional opacity for each trace ``<g>`` (e.g. ``1`` for fully
            opaque on save). Omitted when ``None`` (default: no ``opacity`` attribute).
        endpoint_contacts: optional dict filled with each instance's path-end positions
            in SVG user units (the same point as its end label):
            ``{instance_name: {node_id: {"x", "y", "tangent", "departs"}}}``.
            ``tangent`` is the direction of travel in the same degrees ``draw_styled_path``
            uses. ``departs`` is true at the path start and false at the path end.
        connector_node_ids: optional set of harness connector-node ids. A same-node
            trace turns around on nodes outside that set (the generated ``far``
            stub) as well as on ``wirejunction-`` nodes, so two loopbacks on one
            connector take separate lanes. With the set omitted, only
            ``wirejunction-`` nodes are free ends.
            A trace whose ends are the same node is drawn out one segment to the
            nearest free end — fewest hops from that connector, then the closest
            node — and back on the next lane (a short local U when that connector
            has no stub). Both contacts are kept: the node entry is the outbound
            contact, and ``__self_hop__`` holds ``start`` (from-channel) and
            ``end`` (to-channel).

    Returns:
        str: raw SVG markup for all paths and labels (no <svg> wrapper). Each trace is
        wrapped in ``<g id="…" data-harnice-trace-label="…" [opacity="…"]>`` using ``instance_name`` for the
        trace group name attribute.

    Raises:
        ValueError if a required node or path is not found in the network.
    """
    graph = input_network_2D
    appearance_cache = {}

    # --- Phase 1: BFS path finding ---
    instance_paths = {}
    # Same-node hops are drawn as an out-and-back. The two lanes are extra paths
    # so the offsetter spaces them; they are not drawn as their own traces.
    self_hops = {}
    extra_lane_names = []

    for instance in input_instances:
        inst_name = instance.get("instance_name")

        if from_node_id_field is not None:
            from_node_id = instance.get(from_node_id_field)
        elif instance.get("from_node_id"):
            from_node_id = instance.get("from_node_id")
        else:
            from_node_id = (
                f"{instance.get('this_harness_from_device_refdes')}"
                f".{instance.get('this_harness_from_device_connector_name')}"
            )

        if to_node_id_field is not None:
            to_node_id = instance.get(to_node_id_field)
        elif instance.get("to_node_id"):
            to_node_id = instance.get("to_node_id")
        else:
            to_node_id = (
                f"{instance.get('this_harness_to_device_refdes')}"
                f".{instance.get('this_harness_to_device_connector_name')}"
            )

        if from_node_id not in graph["nodes"]:
            raise ValueError(
                f"From node '{from_node_id}' not found in graph for '{inst_name}'"
            )
        if to_node_id not in graph["nodes"]:
            raise ValueError(
                f"To node '{to_node_id}' not found in graph for '{inst_name}'"
            )

        if from_node_id == to_node_id:
            outbound = _self_hop_outbound(
                graph, from_node_id, connector_node_ids=connector_node_ids
            )
            plan = {
                "node": from_node_id,
                "from_channel": (
                    instance.get("this_harness_from_device_channel_id") or ""
                ).strip(),
                "to_channel": (
                    instance.get("this_harness_to_device_channel_id") or ""
                ).strip(),
                "synthetic": outbound is None,
            }
            if outbound:
                out_segs, out_dirs = outbound
                out_name = f"{inst_name}#loop-out"
                back_name = f"{inst_name}#loop-back"
                instance_paths[out_name] = {
                    "path_segments": out_segs,
                    "path_directions": out_dirs,
                }
                instance_paths[back_name] = {
                    "path_segments": list(reversed(out_segs)),
                    "path_directions": [
                        "b_to_a" if direction == "a_to_b" else "a_to_b"
                        for direction in reversed(out_dirs)
                    ],
                }
                extra_lane_names.extend((out_name, back_name))
                plan["out_name"] = out_name
                plan["back_name"] = back_name
            self_hops[inst_name] = plan
            instance_paths[inst_name] = {
                "path_segments": [],
                "path_directions": [],
            }
            continue

        queue = [(from_node_id, [])]
        visited = {from_node_id}
        found_path = False
        path_segments = []
        path_directions = []

        while queue and not found_path:
            current_node, current_path = queue.pop(0)

            if current_node == to_node_id:
                path_segments = [seg for seg, _ in current_path]
                path_directions = [d for _, d in current_path]
                found_path = True
                break

            for seg_uuid, seg_info in graph["segments"].items():
                node_a = seg_info["node_at_end_a"]
                node_b = seg_info["node_at_end_b"]
                next_node = None
                direction = None

                if node_a == current_node and node_b not in visited:
                    next_node = node_b
                    direction = "a_to_b"
                elif node_b == current_node and node_a not in visited:
                    next_node = node_a
                    direction = "b_to_a"

                if next_node:
                    visited.add(next_node)
                    queue.append((next_node, current_path + [(seg_uuid, direction)]))

        if not found_path:
            raise ValueError(
                f"No path found for '{inst_name}': {from_node_id} → {to_node_id}"
            )

        instance_paths[inst_name] = {
            "path_segments": path_segments,
            "path_directions": path_directions,
        }

    # --- Phase 2: constant lateral offsets at every node ---
    # points_to_pass_through[node_id][seg_uuid][inst_name] = {'x': ..., 'y': ... (Y-flipped)}
    # lane_offsets[seg_uuid][inst_name] = signed offset used for waypoints too.
    points_to_pass_through = {}
    lane_offsets = {}
    node_incident = {}
    for node_id, node_coords in graph["nodes"].items():
        node_segments = []
        node_segment_angles = []
        flip_sort = {}
        other_node_of_seg = {}

        for seg_uuid, seg_info in graph["segments"].items():
            node_a = seg_info["node_at_end_a"]
            node_b = seg_info["node_at_end_b"]

            if node_a == node_id:
                other_id = node_b
                flip_sort[seg_uuid] = False
            elif node_b == node_id:
                other_id = node_a
                flip_sort[seg_uuid] = True
            else:
                continue

            waypoints = seg_info.get("waypoints") or []
            if node_id == node_a and waypoints:
                other = waypoints[0]
            elif node_id == node_b and waypoints:
                other = waypoints[-1]
            else:
                other = graph["nodes"][other_id]
            dx = other["x"] - node_coords["x"]
            dy = other["y"] - node_coords["y"]
            node_segments.append(seg_uuid)
            node_segment_angles.append(math.degrees(math.atan2(dy, dx)))
            other_node_of_seg[seg_uuid] = other_id

        if not node_segments:
            continue

        seg_instances = {}
        any_trace = False
        for seg_uuid in node_segments:
            instances_using_segment = []
            for instance in input_instances:
                name = instance.get("instance_name")
                if seg_uuid in instance_paths.get(name, {}).get("path_segments", []):
                    instances_using_segment.append(name)
            for name in extra_lane_names:
                if seg_uuid in instance_paths.get(name, {}).get("path_segments", []):
                    instances_using_segment.append(name)
            if not instances_using_segment:
                seg_instances[seg_uuid] = []
                continue
            any_trace = True
            instances_using_segment.sort()
            if flip_sort.get(seg_uuid):
                instances_using_segment = instances_using_segment[::-1]
            seg_instances[seg_uuid] = instances_using_segment

        if not any_trace:
            continue

        node_incident[node_id] = {
            "x": node_coords["x"],
            "y": node_coords["y"],
            "segments": node_segments,
            "angles": dict(zip(node_segments, node_segment_angles)),
            "flip_sort": flip_sort,
            "other_node": other_node_of_seg,
            "seg_instances": seg_instances,
            "degree": len(node_segments),
        }

    for node_id, info in node_incident.items():
        for seg_uuid in info["segments"]:
            instances_using_segment = info["seg_instances"].get(seg_uuid) or []
            if not instances_using_segment:
                continue
            seg_angle = info["angles"][seg_uuid]
            perp = math.radians(seg_angle + 90.0)
            ux, uy = math.cos(perp), math.sin(perp)
            offsets = _trace_lateral_offsets(
                len(instances_using_segment), segment_spacing
            )
            for inst_name, center_offset in zip(instances_using_segment, offsets):
                # End-a order is the a_to_b lane; b_to_a travel negates it.
                if not info["flip_sort"].get(seg_uuid):
                    lane_offsets.setdefault(seg_uuid, {})[inst_name] = center_offset
                x_pt = info["x"] + center_offset * ux
                y_pt = info["y"] + center_offset * uy
                points_to_pass_through.setdefault(node_id, {}).setdefault(
                    seg_uuid, {}
                )[inst_name] = {"x": x_pt, "y": -y_pt}

    inst_by_name = {inst.get("instance_name"): inst for inst in input_instances}
    junction_dots = []
    seen_dot = set()
    for node_id, info in node_incident.items():
        if info["degree"] < 3:
            continue
        segs_by_jid = {}
        for seg_uuid in info["segments"]:
            for inst_name in info["seg_instances"].get(seg_uuid) or []:
                jid = (
                    (inst_by_name.get(inst_name) or {}).get("multi_ch_junction_id")
                    or ""
                ).strip()
                if not jid:
                    continue
                segs_by_jid.setdefault(jid, set()).add(seg_uuid)
        for jid, segs in segs_by_jid.items():
            if len(segs) < 3:
                continue
            key = (round(info["x"], 5), round(info["y"], 5), jid)
            if key in seen_dot:
                continue
            seen_dot.add(key)
            junction_dots.append((info["x"], info["y"], 0.0, jid))

    # --- Phase 3: Assemble point chains, draw paths and labels ---
    svg_elements = []

    # Ordinary hops first so a same-connector loop can sit on the same side
    # of the disconnect as the contact already landed on the other face.
    draw_order = [
        inst for inst in input_instances if inst.get("instance_name") not in self_hops
    ] + [
        inst for inst in input_instances if inst.get("instance_name") in self_hops
    ]
    for instance in draw_order:
        inst_name = instance.get("instance_name")
        path_info = instance_paths.get(inst_name, {})
        path_segments = path_info.get("path_segments", [])
        path_directions = path_info.get("path_directions", [])

        hop = self_hops.get(inst_name)
        if hop is not None:
            if hop.get("synthetic"):
                point_chain = _self_hop_local_point_chain(
                    graph, hop["node"], segment_spacing
                )
            else:
                out_info = instance_paths.get(hop["out_name"], {})
                back_info = instance_paths.get(hop["back_name"], {})
                out_chain = _assemble_trace_point_chain(
                    graph,
                    points_to_pass_through,
                    out_info.get("path_segments", []),
                    out_info.get("path_directions", []),
                    hop["out_name"],
                    lane_offsets,
                )
                back_chain = _assemble_trace_point_chain(
                    graph,
                    points_to_pass_through,
                    back_info.get("path_segments", []),
                    back_info.get("path_directions", []),
                    hop["back_name"],
                    lane_offsets,
                )
                if out_chain and back_chain:
                    # Joining the lanes with their own tangents is the U at the
                    # free end: outbound keeps going, the return comes back.
                    peer = _peer_face_for_self_hop(
                        input_instances,
                        endpoint_contacts,
                        instance,
                        hop.get("from_channel") or "",
                        hop["node"],
                    )
                    if peer and peer[0] in graph["nodes"]:
                        node_xy = graph["nodes"][hop["node"]]
                        other_xy = graph["nodes"][peer[0]]
                        point_chain = _orient_self_hop_chains(
                            out_chain,
                            back_chain,
                            (node_xy["x"], node_xy["y"]),
                            (other_xy["x"], other_xy["y"]),
                            peer[1],
                        )
                    else:
                        point_chain = out_chain + back_chain
                else:
                    point_chain = _self_hop_local_point_chain(
                        graph, hop["node"], segment_spacing
                    )
        else:
            if not path_segments:
                continue
            point_chain = _assemble_trace_point_chain(
                graph,
                points_to_pass_through,
                path_segments,
                path_directions,
                inst_name,
                lane_offsets,
            )

        if not point_chain:
            cli.warn(f"empty chain for '{inst_name}'")
            continue

        if endpoint_contacts is not None and hop is not None:
            contacts = endpoint_contacts.setdefault(inst_name, {})
            start = _trace_endpoint_contact(point_chain[0], True)
            end = _trace_endpoint_contact(point_chain[-1], False)
            contacts[hop["node"]] = start
            contacts["__self_hop__"] = {
                "node": hop["node"],
                "from_channel": hop.get("from_channel") or "",
                "to_channel": hop.get("to_channel") or "",
                "start": start,
                "end": end,
            }
        elif endpoint_contacts is not None:
            contacts = endpoint_contacts.setdefault(inst_name, {})
            for which, seg_uuid, direction, point, departs in (
                ("start", path_segments[0], path_directions[0], point_chain[0], True),
                ("end", path_segments[-1], path_directions[-1], point_chain[-1], False),
            ):
                info = graph["segments"][seg_uuid]
                node_a = info["node_at_end_a"]
                node_b = info["node_at_end_b"]
                if direction == "a_to_b":
                    node_id = node_a if which == "start" else node_b
                else:
                    node_id = node_b if which == "start" else node_a
                contacts[node_id] = {
                    "x": point["x"],
                    "y": -point["y"],
                    "tangent": point.get("tangent", 0.0),
                    "departs": departs,
                }

        trace_appearance = _resolved_trace_appearance(instance, appearance_cache)
        trace_group = []
        draw_styled_path(point_chain, stroke_width, trace_appearance, trace_group)

        end_ink, end_fill, end_outline = _label_square_colors(
            trace_appearance, "white", "black", "black"
        )
        mid_ink, mid_fill, mid_outline = _label_square_colors(
            trace_appearance, "black", "white", "black"
        )

        # Endpoint labels — skipped if field is absent
        for point, text in zip(
            [point_chain[0], point_chain[-1]],
            [instance.get("print_name_at_end_a"), instance.get("print_name_at_end_b")],
        ):
            if text:
                trace_group.append(
                    label_svg(
                        point["x"],
                        point["y"],
                        point["tangent"],
                        text,
                        text_color=end_ink,
                        background_color=end_fill,
                        outline=end_outline,
                        font_size=label_font_size,
                    )
                )

        # Midpoint labels on long sub-segments — skipped if field is absent
        print_name = instance.get("print_name")
        if print_name:
            for i in range(len(point_chain) - 1):
                pt_a = point_chain[i]
                pt_b = point_chain[i + 1]
                if pt_a.get("seg_uuid") != pt_b.get("seg_uuid"):
                    continue
                dx = pt_b["x"] - pt_a["x"]
                dy = pt_b["y"] - pt_a["y"]
                if math.sqrt(dx * dx + dy * dy) >= min_label_segment_length:
                    trace_group.append(
                        label_svg(
                            (pt_a["x"] + pt_b["x"]) / 2,
                            (pt_a["y"] + pt_b["y"]) / 2,
                            pt_a["tangent"],
                            print_name,
                            text_color=mid_ink,
                            background_color=mid_fill,
                            outline=mid_outline,
                            font_size=label_font_size,
                        )
                    )

        svg_elements.append(
            _trace_group_open_tag(instance, trace_group_opacity)
            + "\n"
            + "\n".join(trace_group)
            + "\n</g>"
        )

    if junction_dots:
        dots_by_jid = {}
        for cx, cy, radius, jid in junction_dots:
            dots_by_jid.setdefault(jid, []).append((cx, cy, radius))
        dot_parts = ['<g id="multi-ch-junction-dots" pointer-events="none">']
        for jid, dots in dots_by_jid.items():
            esc_jid = _svg_xml_attr_escape(jid)
            esc_label = _svg_xml_attr_escape(f"multi-ch-junction-{jid}-dot")
            dot_parts.append(
                f'<g data-harnice-trace-label="{esc_label}" '
                f'data-harnice-junction="{esc_jid}" opacity="1">'
            )
            for cx, cy, _cluster_r in dots:
                r = _multi_ch_junction_dot_radius(
                    jid, input_instances, stroke_width, appearance_cache
                )
                sw = max(r * 0.12, 0.04)
                nchar = max(len(jid), 1)
                font = min(r * 1.05, (r * 1.7) / (nchar * 0.55))
                text_escaped = escape_svg_text(jid)
                dot_parts.append(
                    f'<circle class="multi-ch-junction-dot" '
                    f'data-harnice-junction="{esc_jid}" '
                    f'cx="{cx}" cy="{cy}" r="{r:.4f}" fill="#3a6ea5" stroke="black" '
                    f'stroke-width="{sw:.4f}"/>'
                )
                dot_parts.append(
                    f'<text class="multi-ch-junction-dot-label" '
                    f'data-harnice-junction="{esc_jid}" '
                    f'x="{cx}" y="{cy}" text-anchor="middle" font-size="{font:.4f}" '
                    f'style="fill:#ffffff;dominant-baseline:middle;font-weight:normal;'
                    f'font-family:Arial, Helvetica, sans-serif">{text_escaped}</text>'
                )
            dot_parts.append("</g>")
        dot_parts.append("</g>")
        svg_elements.append("\n".join(dot_parts))

    return "\n".join(svg_elements)


def draw_clean_line(
    from_coords,
    to_coords,
    scale=1,
    from_arrowhead=False,
    to_arrowhead=True,
    stroke="black",
    thickness=1,
):
    """
    Use this when a build that is writing an SVG needs a line between two instance locations.

    Generates SVG markup for a line connecting two instance locations, with optional arrowheads.

    Coordinates are given in inches and converted to pixels (96 dpi) with Y-axis
    flipped for the SVG coordinate system.

    Args:
        from_coords (tuple): Starting (x, y) in inches.
        to_coords (tuple): Ending (x, y) in inches.
        scale (float): Scale factor for arrowhead size and line thickness. Defaults to 1.
        from_arrowhead (bool): If True, draw an arrowhead at the start. Defaults to False.
        to_arrowhead (bool): If True, draw an arrowhead at the end. Defaults to True.
        stroke (str): Style color token for the line. Defaults to "black".
        thickness (float): Line thickness in pixels before scaling. Defaults to 1.

    Returns:
        str: SVG markup string, or empty string if coordinates are identical.
    """
    stroke = appearance.normalize_color_into_rrggbb(stroke)
    fx, fy = from_coords[0] * 96, from_coords[1] * -96
    tx, ty = to_coords[0] * 96, to_coords[1] * -96

    dx = tx - fx
    dy = ty - fy
    line_len = math.hypot(dx, dy)

    if line_len == 0:
        return ""

    ux = dx / line_len
    uy = dy / line_len

    arrow_len = 8 / scale
    arrow_wid = 6 / scale

    svg_parts = [
        f'<line x1="{fx}" y1="{fy}" x2="{tx}" y2="{ty}" '
        f'stroke="{stroke}" stroke-width="{thickness / scale}"/>'
    ]

    def arrowhead(px, py, ux, uy):
        perp_x = -uy
        perp_y = ux
        p1x = px - ux * arrow_len + perp_x * (arrow_wid / 2)
        p1y = py - uy * arrow_len + perp_y * (arrow_wid / 2)
        p2x = px - ux * arrow_len - perp_x * (arrow_wid / 2)
        p2y = py - uy * arrow_len - perp_y * (arrow_wid / 2)
        return f'<polygon points="{px},{py} {p1x},{p1y} {p2x},{p2y}" fill="{stroke}"/>'

    if from_arrowhead:
        svg_parts.append(arrowhead(tx, ty, ux, uy))

    if to_arrowhead:
        svg_parts.append(arrowhead(fx, fy, -ux, -uy))

    return "".join(svg_parts)
