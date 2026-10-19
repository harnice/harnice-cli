# SVG Utilities
---
##Commands
*These functions are already available in build instructions as `svg_utils`. Use them as written.*
??? info "`svg_utils.table(layout_dict, format_dict, columns_list, content_list, path_to_svg, contents_group_name)`"

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
    **Arguments**
    
    - `layout_dict` expects a dictionary describing in which direction the table is built
    - `format_dict` expects a dictionary of named styles (drafting ink) for the table.
    - `columns_list` expects a list containing your column header content, width, and formatting rules.
    - `content_list` expects a list containing what is actually presented on your table.
    - `path_to_svg`: File path the finished SVG table is written to.
    - `contents_group_name`: Id prefix for the SVG groups that wrap the table. The file contains ``{contents_group_name}-contents-start`` and ``{contents_group_name}-contents-end``.
    
    **Returns**
    
    - A string of SVG primatives in xml format intended to look like a table.
    
    ---
    
    **1. Layout**
    
    The SVG origin (0,0) must exist somewhere in your table. Defining this correctly will help later when tables dynamically update with changing inputs.
    
    *example:*
    ```json
    layout = {
        "origin_corner": "top-left",
        "build_direction": "down",
    }
    ```
    Both fields are required.
    **Origin Corner**
    
    The origin is defined to be at one of the four corners of the first row `content[0]`. Valid options:
    
    - `top-left`
    - `top-right`
    - `bottom-left`
    - `bottom-right`
    
    **Build Direction**
    When building a table, you can choose to build rows downwards (below the previous, positive y in svg coords) or upwards (above the previous, negative y in svg coords). The direction property defines this:
    
    - `down` → rows appear below the previous
    - `up` → new rows appear above the previous
    
    ---
    
    **2. Format**
    
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
    
    **Format Arguments**
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
    
    **Style Resolution Order**
    If something is defined at the row level, it takes precedent over some parameter defined at the column level, which takes precedent over a definition in key `globals`, if defined. If something is not defined at all, the above defaults will apply.
    
    **Color Standard**
    
    Colors are style keys (`fill_color`, `stroke_color`, `text_color`). CSS names are hexified at paint. Convert an instance appearance to those keys at the instance, before calling ``table``.
    
    ---
    
    **3. Columns**
    
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
    
    **Column Arguments**
    Each field must have the following required keys:
    
    - `name` *(string)* Used to identify a column when defining contents later. Must be unique.
    - `width` *(number)* Self-explanatory (px)
    
    You may add any formatting key as defined in the formatting section as needed.
    
    Note that the order of the items in the list represents the order in which they will be printed from left to right, regardless of the layout you've chosen for this table.
    
    ---
    
    **4. Content Structure**
    
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
    
    **Importing a Symbol into a Cell**
    
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
    
    **user import logic**
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

??? info "`svg_utils.add_entire_svg_file_contents_to_group(filepath, new_group_name)`"

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

??? info "`svg_utils.find_and_replace_svg_group(source_svg_filepath, source_group_name, destination_svg_filepath, destination_group_name)`"

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

??? info "`svg_utils.draw_styled_path(spline_points, stroke_width_inches, appearance_dict, local_group)`"

    Adds a styled spline path to the local group.
    Call as if you were appending any other element to an svg group.
    
    Spline points are a list of dictionaries with x and y coordinates. [{"x": 0, "y": 0, "tangent": 0}, {"x": 1, "y": 1, "tangent": 0}]
    Plots physical geometry from an engineering appearance dict (conductor, cable,
    segment). Keys: base_color, outline_color, parallelstripe, perpstripe, slash_lines.
    Slash lines: direction, angle, step, color, slash_width_inches.
    
    Do not pass a drafting style (fill_color / stroke_color / text_color).
    
    If ``appearance_dict`` is missing/empty, or if it does not define ``base_color``,
    a rainbow placeholder spline is drawn.

??? info "`svg_utils.draw_filleted_styled_path(points, stroke_width_inches, appearance_dict, local_group)`"

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

??? info "`svg_utils.table(layout_dict, format_dict, columns_list, content_list, path_to_svg, contents_group_name)`"

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
    **Arguments**
    
    - `layout_dict` expects a dictionary describing in which direction the table is built
    - `format_dict` expects a dictionary of named styles (drafting ink) for the table.
    - `columns_list` expects a list containing your column header content, width, and formatting rules.
    - `content_list` expects a list containing what is actually presented on your table.
    - `path_to_svg`: File path the finished SVG table is written to.
    - `contents_group_name`: Id prefix for the SVG groups that wrap the table. The file contains ``{contents_group_name}-contents-start`` and ``{contents_group_name}-contents-end``.
    
    **Returns**
    
    - A string of SVG primatives in xml format intended to look like a table.
    
    ---
    
    **1. Layout**
    
    The SVG origin (0,0) must exist somewhere in your table. Defining this correctly will help later when tables dynamically update with changing inputs.
    
    *example:*
    ```json
    layout = {
        "origin_corner": "top-left",
        "build_direction": "down",
    }
    ```
    Both fields are required.
    **Origin Corner**
    
    The origin is defined to be at one of the four corners of the first row `content[0]`. Valid options:
    
    - `top-left`
    - `top-right`
    - `bottom-left`
    - `bottom-right`
    
    **Build Direction**
    When building a table, you can choose to build rows downwards (below the previous, positive y in svg coords) or upwards (above the previous, negative y in svg coords). The direction property defines this:
    
    - `down` → rows appear below the previous
    - `up` → new rows appear above the previous
    
    ---
    
    **2. Format**
    
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
    
    **Format Arguments**
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
    
    **Style Resolution Order**
    If something is defined at the row level, it takes precedent over some parameter defined at the column level, which takes precedent over a definition in key `globals`, if defined. If something is not defined at all, the above defaults will apply.
    
    **Color Standard**
    
    Colors are style keys (`fill_color`, `stroke_color`, `text_color`). CSS names are hexified at paint. Convert an instance appearance to those keys at the instance, before calling ``table``.
    
    ---
    
    **3. Columns**
    
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
    
    **Column Arguments**
    Each field must have the following required keys:
    
    - `name` *(string)* Used to identify a column when defining contents later. Must be unique.
    - `width` *(number)* Self-explanatory (px)
    
    You may add any formatting key as defined in the formatting section as needed.
    
    Note that the order of the items in the list represents the order in which they will be printed from left to right, regardless of the layout you've chosen for this table.
    
    ---
    
    **4. Content Structure**
    
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
    
    **Importing a Symbol into a Cell**
    
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
    
    **user import logic**
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

??? info "`svg_utils.label_svg(x, y, angle, text, text_color='black', background_color='white', outline='black', font_size=8, font_family='Arial, Helvetica, sans-serif', font_weight='normal')`"

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

??? info "`svg_utils.draw_segments_across_paths(input_instances, input_network_2D, stroke_width, segment_spacing, min_label_segment_length=30.0, label_font_size=8, from_node_id_field=None, to_node_id_field=None, trace_group_opacity=None)`"

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

??? info "`svg_utils.draw_clean_line(from_coords, to_coords, scale=1, from_arrowhead=False, to_arrowhead=True, stroke='black', thickness=1)`"

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

