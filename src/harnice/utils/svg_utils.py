import os
import re
import math
from harnice import cli
from harnice.utils import appearance


def add_entire_svg_file_contents_to_group(filepath, new_group_name):
    """
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
    Adds a styled spline path to the local group.
    Call as if you were appending any other element to an svg group.

    Spline points are a list of dictionaries with x and y coordinates. [{"x": 0, "y": 0, "tangent": 0}, {"x": 1, "y": 1, "tangent": 0}]
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

    # ---------------------------------------------------------------------
    # --- spline_to_path
    # ---------------------------------------------------------------------
    def spline_to_path(points):
        if len(points) < 2:
            return ""
        path = f"M {points[0]['x']:.3f},{-points[0]['y']:.3f}"
        for i in range(len(points) - 1):
            p0, p1 = points[i], points[i + 1]
            t0, t1 = (
                math.radians(p0.get("tangent", 0)),
                math.radians(p1.get("tangent", 0)),
            )
            d = math.hypot(p1["x"] - p0["x"], p1["y"] - p0["y"])
            ctrl_dist = d * 0.5
            c1x = p0["x"] + math.cos(t0) * ctrl_dist
            c1y = p0["y"] + math.sin(t0) * ctrl_dist
            c2x = p1["x"] - math.cos(t1) * ctrl_dist
            c2y = p1["y"] - math.sin(t1) * ctrl_dist
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
            t0 = math.radians(points[i].get("tangent", 0))
            t1 = math.radians(points[i + 1].get("tangent", 0))
            d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            ctrl_dist = d * 0.5
            c1 = (p0[0] + math.cos(t0) * ctrl_dist, p0[1] + math.sin(t0) * ctrl_dist)
            c2 = (p1[0] - math.cos(t1) * ctrl_dist, p1[1] - math.sin(t1) * ctrl_dist)

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


# Outermost parallel wire sits at ±this angle from the segment axis on a junction circle.
# R = half_width / sin(θ) keeps asin() well-conditioned and matches the old
# ``n * spacing`` vibe (≈ 2× half-width for a full fan).
_TRACE_CIRCLE_FAN_HALF_ANGLE_DEG = 30.0


def _drawn_trace_stroke_px(instance, stroke_width_inches):
    """SVG stroke width actually used for this instance (rainbow placeholder is 0.01 in)."""
    raw = (instance or {}).get("appearance")
    parsed = appearance.parse(raw) if raw else None
    if not parsed or not parsed.get("base_color"):
        return 0.01 * 96
    return float(stroke_width_inches) * 96


def _multi_ch_junction_dot_radius(jid, instances, stroke_width_inches):
    """Dot radius so the circle diameter is 2× the junction traces' stroke width."""
    width = 0.0
    for inst in instances or []:
        if (inst.get("multi_ch_junction_id") or "").strip() != jid:
            continue
        width = max(width, _drawn_trace_stroke_px(inst, stroke_width_inches))
    if width <= 0:
        width = 0.01 * 96
    return width


def _trace_circle_radius_for_half_width(half_width):
    """Junction-circle radius so the outermost offset wire sits at ±30° on the fan."""
    if half_width <= 1e-12:
        return 0.0
    return half_width / math.sin(math.radians(_TRACE_CIRCLE_FAN_HALF_ANGLE_DEG))


def _trace_lateral_offsets(num_on_seg, segment_spacing):
    """Centered lateral offsets for ``num_on_seg`` parallel traces on one segment."""
    return [
        (idx - (num_on_seg / 2) - 0.5) * segment_spacing
        for idx in range(1, num_on_seg + 1)
    ]


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
):
    """
    Maps segment-type instances onto a 2D wire network, offsets parallel paths
    at shared nodes, draws each path and its labels, and returns raw SVG markup.

    Junction geometry:
        - Degree-1 nodes (path endpoints): traces terminate on the line through the
          node perpendicular to the incident segment — no circle.
        - Degree ≥ 2 nodes: traces meet a junction circle. Radius is sized so the
          outermost parallel wire sits at ±30° from the segment axis
          (``R = half_width / sin(30°)``). Overlapping circles are merged into one
          larger circle (centroid center, radius covering member nodes and fan-out);
          segments internal to a merge are skipped so traces do not zigzag.

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

    Returns:
        str: raw SVG markup for all paths and labels (no <svg> wrapper). Each trace is
        wrapped in ``<g id="…" data-harnice-trace-label="…" [opacity="…"]>`` using ``instance_name`` for the
        trace group name attribute.

    Raises:
        ValueError if a required node or path is not found in the network.
    """
    graph = input_network_2D

    # --- Phase 1: BFS path finding ---
    instance_paths = {}

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

    # --- Phase 2: Offset point calculation at each node ---
    # points_to_pass_through[node_id][seg_uuid][inst_name] = {'x': ..., 'y': ... (Y-flipped)}
    #
    # Degree-1 nodes get a flat perpendicular cap. Degree ≥ 2 nodes get junction
    # circles; overlapping circles merge into one so traces stay tangent-clean.
    points_to_pass_through = {}

    # Per-node incident geometry and per-segment trace lists (shared by both styles).
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
        seg_half_width = {}
        any_trace = False
        for seg_uuid in node_segments:
            instances_using_segment = [
                instance.get("instance_name")
                for instance in input_instances
                if seg_uuid
                in instance_paths.get(instance.get("instance_name"), {}).get(
                    "path_segments", []
                )
            ]
            if not instances_using_segment:
                seg_instances[seg_uuid] = []
                seg_half_width[seg_uuid] = 0.0
                continue
            any_trace = True
            instances_using_segment.sort()
            if flip_sort.get(seg_uuid):
                instances_using_segment = instances_using_segment[::-1]
            seg_instances[seg_uuid] = instances_using_segment
            n = len(instances_using_segment)
            seg_half_width[seg_uuid] = (
                ((n - 1) / 2.0) * segment_spacing if n > 0 else 0.0
            )

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
            "seg_half_width": seg_half_width,
            "max_half_width": max(seg_half_width.values()) if seg_half_width else 0.0,
            "degree": len(node_segments),
        }

    # --- Endpoints: flat perpendicular caps (no circle) ---
    for node_id, info in node_incident.items():
        if info["degree"] != 1:
            continue
        seg_uuid = info["segments"][0]
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
            x_pt = info["x"] + center_offset * ux
            y_pt = info["y"] + center_offset * uy
            points_to_pass_through.setdefault(node_id, {}).setdefault(seg_uuid, {})[
                inst_name
            ] = {"x": x_pt, "y": -y_pt}

    # --- Junctions: sized circles, merge overlaps, place on circumference ---
    junction_ids = [
        nid for nid, info in node_incident.items() if info["degree"] >= 2
    ]
    if junction_ids:
        parent = {nid: nid for nid in junction_ids}

        def _find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def _union(a, b):
            ra, rb = _find(a), _find(b)
            if ra == rb:
                return False
            parent[rb] = ra
            return True

        def _cluster_geometry():
            members_by_root = {}
            for nid in junction_ids:
                members_by_root.setdefault(_find(nid), []).append(nid)
            geom = {}
            for root, members in members_by_root.items():
                cx = sum(node_incident[m]["x"] for m in members) / len(members)
                cy = sum(node_incident[m]["y"] for m in members) / len(members)
                extent = max(
                    math.hypot(
                        node_incident[m]["x"] - cx, node_incident[m]["y"] - cy
                    )
                    for m in members
                )
                member_set = set(members)
                half_w = 0.0
                for m in members:
                    for seg_uuid in node_incident[m]["segments"]:
                        other = node_incident[m]["other_node"][seg_uuid]
                        if other in member_set:
                            continue
                        half_w = max(
                            half_w, node_incident[m]["seg_half_width"].get(seg_uuid, 0.0)
                        )
                r_fan = _trace_circle_radius_for_half_width(half_w)
                radius = max(extent, r_fan)
                if half_w > 0:
                    radius = max(radius, half_w * 1.0001)
                geom[root] = {
                    "cx": cx,
                    "cy": cy,
                    "R": radius,
                    "members": members,
                    "member_set": member_set,
                }
            return geom

        changed = True
        while changed:
            changed = False
            geom = _cluster_geometry()
            roots = list(geom.keys())
            for i in range(len(roots)):
                for j in range(i + 1, len(roots)):
                    g1 = geom[roots[i]]
                    g2 = geom[roots[j]]
                    dist = math.hypot(g1["cx"] - g2["cx"], g1["cy"] - g2["cy"])
                    if dist < g1["R"] + g2["R"] - 1e-9:
                        if _union(roots[i], roots[j]):
                            changed = True

        geom = _cluster_geometry()
        node_cluster = {}
        for g in geom.values():
            for m in g["members"]:
                node_cluster[m] = g

        for node_id in junction_ids:
            info = node_incident[node_id]
            cluster = node_cluster[node_id]
            cx, cy, radius = cluster["cx"], cluster["cy"], cluster["R"]
            member_set = cluster["member_set"]

            for seg_uuid in info["segments"]:
                instances_using_segment = info["seg_instances"].get(seg_uuid) or []
                if not instances_using_segment:
                    continue
                other_id = info["other_node"][seg_uuid]
                if other_id in member_set:
                    # Segment lies inside the merged circle — no contact points.
                    continue

                # Face the neighboring junction cluster center when present so
                # adjacent circles stay radially aligned (tangency-preserving).
                if other_id in node_cluster:
                    ox = node_cluster[other_id]["cx"]
                    oy = node_cluster[other_id]["cy"]
                else:
                    other_coords = graph["nodes"][other_id]
                    ox = other_coords["x"]
                    oy = other_coords["y"]
                seg_angle = math.degrees(math.atan2(oy - cy, ox - cx))

                offsets = _trace_lateral_offsets(
                    len(instances_using_segment), segment_spacing
                )
                for inst_name, center_offset in zip(
                    instances_using_segment, offsets
                ):
                    if radius <= 1e-12:
                        delta_angle = 0.0
                        x_pt, y_pt = cx, cy
                    else:
                        ratio = max(-1.0, min(1.0, center_offset / radius))
                        delta_angle = math.degrees(math.asin(ratio))
                        final_angle = seg_angle + delta_angle
                        x_pt = cx + radius * math.cos(math.radians(final_angle))
                        y_pt = cy + radius * math.sin(math.radians(final_angle))

                    points_to_pass_through.setdefault(node_id, {}).setdefault(
                        seg_uuid, {}
                    )[inst_name] = {"x": x_pt, "y": -y_pt}

        inst_by_name = {
            inst.get("instance_name"): inst for inst in input_instances
        }
        junction_dots = []
        seen_dot = set()
        for cluster in geom.values():
            segs_by_jid = {}
            for member in cluster["members"]:
                info = node_incident[member]
                for seg_uuid in info["segments"]:
                    if info["other_node"][seg_uuid] in cluster["member_set"]:
                        continue
                    for inst_name in info["seg_instances"].get(seg_uuid) or []:
                        jid = (
                            (inst_by_name.get(inst_name) or {}).get(
                                "multi_ch_junction_id"
                            )
                            or ""
                        ).strip()
                        if not jid:
                            continue
                        segs_by_jid.setdefault(jid, set()).add(seg_uuid)
            for jid, segs in segs_by_jid.items():
                if len(segs) < 3:
                    continue
                key = (round(cluster["cx"], 5), round(cluster["cy"], 5), jid)
                if key in seen_dot:
                    continue
                seen_dot.add(key)
                junction_dots.append(
                    (cluster["cx"], cluster["cy"], cluster["R"], jid)
                )
    else:
        junction_dots = []

    # --- Phase 3: Assemble point chains, draw paths and labels ---
    svg_elements = []

    for instance in input_instances:
        inst_name = instance.get("instance_name")
        path_info = instance_paths.get(inst_name, {})
        path_segments = path_info.get("path_segments", [])
        path_directions = path_info.get("path_directions", [])

        if not path_segments:
            continue

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

            def tangent_between(p, q):
                dx = q["x"] - p["x"]
                dy = q["y"] - p["y"]
                if abs(dx) < 1e-12 and abs(dy) < 1e-12:
                    return 0.0
                # Negate because Y is flipped when stored in points_to_pass_through
                return (-math.degrees(math.atan2(dy, dx))) % 360.0

            start_id, end_id = ordered_nodes
            geom = [graph["nodes"][start_id]] + midpoints + [graph["nodes"][end_id]]
            tangents = [
                tangent_between(geom[i], geom[i + 1]) for i in range(len(geom) - 1)
            ] or [0.0]
            tangents.append(tangents[-1])

            def append_node_contact(nid, tangent):
                try:
                    pt = points_to_pass_through[nid][seg_uuid][inst_name]
                except KeyError:
                    # Missing on purpose for segments internal to a merged circle.
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
                # Two coincident points so the spline drawer keeps each span
                # straight. One tangent cannot enter and leave a corner.
                point_chain.append(
                    {
                        "x": waypoint["x"],
                        "y": -waypoint["y"],
                        "tangent": tangents[mid_index],
                        "seg_uuid": seg_uuid,
                    }
                )
                point_chain.append(
                    {
                        "x": waypoint["x"],
                        "y": -waypoint["y"],
                        "tangent": tangents[mid_index + 1],
                        "seg_uuid": seg_uuid,
                    }
                )
            append_node_contact(end_id, tangents[len(midpoints)])

        if not point_chain:
            cli.warn(f"empty chain for '{inst_name}'")
            continue

        trace_appearance = instance.get("appearance")
        trace_group = []
        draw_styled_path(point_chain, stroke_width, trace_appearance, trace_group)

        # Endpoint labels (black box, white text) — skipped if field is absent
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
                        text_color="white",
                        background_color="black",
                        outline="black",
                        font_size=label_font_size,
                    )
                )

        # Midpoint labels on long sub-segments (white box, black text) — skipped if field is absent
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
                            text_color="black",
                            background_color="white",
                            outline="black",
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
                r = _multi_ch_junction_dot_radius(jid, input_instances, stroke_width)
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
