import os
import json
import random
import math
import re
from PIL import Image, ImageDraw, ImageFont
from harnice import cli, fileio, state
from harnice.utils import svg_utils


default_desc = "COTS COMPONENT, SIZE, COLOR, etc."

button_color = "#e1e8a2"

gitignore_rules = [
    "*.tmp",
]

def file_structure():
    return {
        "drawing.svg": "drawing",
        "drawing.png": "drawing png",
        "attributes.json": "attributes",
        "model.step": "model",
    }


def generate_structure():
    pass


def build():
    # === ATTRIBUTES JSON DEFAULTS ===
    default_attributes = {
        "tools": [],
        "build_notes": [],
        "csys_children": {
            "accessory-1": {"x": 3, "y": 2, "angle": 0, "rotation": 0},
            "accessory-2": {"x": 2, "y": 3, "angle": 0, "rotation": 0},
            "flagnote-1": {"angle": 0, "distance": 2, "rotation": 0},
            "flagnote-leader-1": {"angle": 0, "distance": 1, "rotation": 0},
            "flagnote-2": {"angle": 15, "distance": 2, "rotation": 0},
            "flagnote-leader-2": {"angle": 15, "distance": 1, "rotation": 0},
            "flagnote-3": {"angle": -15, "distance": 2, "rotation": 0},
            "flagnote-leader-3": {"angle": -15, "distance": 1, "rotation": 0},
            "flagnote-4": {"angle": 30, "distance": 2, "rotation": 0},
            "flagnote-leader-4": {"angle": 30, "distance": 1, "rotation": 0},
            "flagnote-5": {"angle": -30, "distance": 2, "rotation": 0},
            "flagnote-leader-5": {"angle": -30, "distance": 1, "rotation": 0},
            "flagnote-6": {"angle": 45, "distance": 2, "rotation": 0},
            "flagnote-leader-6": {"angle": 45, "distance": 1, "rotation": 0},
            "flagnote-7": {"angle": -45, "distance": 2, "rotation": 0},
            "flagnote-leader-7": {"angle": -45, "distance": 1, "rotation": 0},
            "flagnote-8": {"angle": 60, "distance": 2, "rotation": 0},
            "flagnote-leader-8": {"angle": 60, "distance": 1, "rotation": 0},
            "flagnote-9": {"angle": -60, "distance": 2, "rotation": 0},
            "flagnote-leader-9": {"angle": -60, "distance": 1, "rotation": 0},
            "flagnote-10": {"angle": -75, "distance": 2, "rotation": 0},
            "flagnote-leader-10": {"angle": -75, "distance": 1, "rotation": 0},
            "flagnote-11": {"angle": 75, "distance": 2, "rotation": 0},
            "flagnote-leader-11": {"angle": 75, "distance": 1, "rotation": 0},
            "flagnote-12": {"angle": -90, "distance": 2, "rotation": 0},
            "flagnote-leader-12": {"angle": -90, "distance": 1, "rotation": 0},
            "flagnote-13": {"angle": 90, "distance": 2, "rotation": 0},
            "flagnote-leader-13": {"angle": 90, "distance": 1, "rotation": 0},
            "flagnote-14": {"angle": -105, "distance": 2, "rotation": 0},
            "flagnote-leader-14": {"angle": -105, "distance": 1, "rotation": 0},
            "flagnote-15": {"angle": 105, "distance": 2, "rotation": 0},
            "flagnote-leader-15": {"angle": 105, "distance": 1, "rotation": 0},
            "flagnote-16": {"angle": -120, "distance": 2, "rotation": 0},
            "flagnote-leader-16": {"angle": -120, "distance": 1, "rotation": 0},
        },
    }

    attributes_path = fileio.path("attributes")

    # Load or create attributes.json
    if os.path.exists(attributes_path):
        try:
            with open(attributes_path, "r", encoding="utf-8") as f:
                attrs = json.load(f)
        except Exception as e:
            cli.warn(f"Could not load existing attributes.json: {e}")
            attrs = default_attributes.copy()
    else:
        attrs = default_attributes.copy()
        with open(attributes_path, "w", encoding="utf-8") as f:
            json.dump(attrs, f, indent=4)

    # === SVG SETUP ===
    svg_path = fileio.path("drawing")
    temp_svg_path = svg_path + ".tmp"

    svg_width = 400
    svg_height = 400
    group_name = f"{state.partnumber('pn')}-drawing"

    random_fill = "#{:06X}".format(random.randint(0, 0xFFFFFF))
    fallback_rect = f'    <rect x="0" y="-48" width="96" height="96" fill="{random_fill}" stroke="black" stroke-width="1"/>'

    csys_children = attrs.get("csys_children", {})

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{svg_width}" height="{svg_height}">',
        f'  <g id="{group_name}-contents-start">',
        fallback_rect,
        "  </g>",
        f'  <g id="{group_name}-contents-end">',
        "  </g>",
    ]

    # === Output csys locations ===
    lines.append('  <g id="output csys locations">')

    arrow_len = 24
    dot_radius = 4
    arrow_size = 6

    for csys_name, csys in csys_children.items():
        try:
            x = float(csys.get("x", 0)) * 96
            y = float(csys.get("y", 0)) * 96

            angle_deg = float(csys.get("angle", 0))
            distance_in = float(csys.get("distance", 0))
            angle_rad = math.radians(angle_deg)
            dist_px = distance_in * 96
            x += dist_px * math.cos(angle_rad)
            y += dist_px * math.sin(angle_rad)

            rotation_deg = float(csys.get("rotation", 0))
            rotation_rad = math.radians(rotation_deg)
            cos_r, sin_r = math.cos(rotation_rad), math.sin(rotation_rad)

            dx_x, dy_x = arrow_len * cos_r, arrow_len * sin_r
            dx_y, dy_y = -arrow_len * sin_r, arrow_len * cos_r

            lines.append(f'    <g id="{csys_name}">')
            lines.append(
                f'      <circle cx="{x:.2f}" cy="{-y:.2f}" r="{dot_radius}" fill="black"/>'
            )

            def draw_arrow(x1, y1, dx, dy, color):
                x2, y2 = x1 + dx, y1 + dy
                lines.append(
                    f'      <line x1="{x1:.2f}" y1="{-y1:.2f}" '
                    f'x2="{x2:.2f}" y2="{-y2:.2f}" stroke="{color}" stroke-width="2"/>'
                )
                length = math.hypot(dx, dy)
                if length == 0:
                    return
                ux, uy = dx / length, dy / length
                px, py = -uy, ux
                base_x = x2 - ux * arrow_size
                base_y = y2 - uy * arrow_size
                tip = (x2, y2)
                left = (base_x + px * (arrow_size / 2), base_y + py * (arrow_size / 2))
                right = (base_x - px * (arrow_size / 2), base_y - py * (arrow_size / 2))
                lines.append(
                    f'      <polygon points="{tip[0]:.2f},{-tip[1]:.2f} '
                    f'{left[0]:.2f},{-left[1]:.2f} {right[0]:.2f},{-right[1]:.2f}" fill="{color}"/>'
                )

            draw_arrow(x, y, dx_x, dy_x, "red")
            draw_arrow(x, y, dx_y, dy_y, "green")
            lines.append("    </g>")

        except Exception as e:
            cli.warn(f"Failed to draw csys {csys_name}: {e}")

    lines.append("  </g>")
    lines.append("</svg>")

    with open(temp_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    if os.path.exists(svg_path):
        try:
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_text = f.read()
        except Exception:
            svg_text = ""

        if (
            f"{group_name}-contents-start" not in svg_text
            or f"{group_name}-contents-end" not in svg_text
        ):
            svg_utils.add_entire_svg_file_contents_to_group(svg_path, group_name)

        svg_utils.find_and_replace_svg_group(
            source_svg_filepath=svg_path,
            source_group_name=group_name,
            destination_svg_filepath=temp_svg_path,
            destination_group_name=group_name,
        )

    if os.path.exists(svg_path):
        os.remove(svg_path)
    os.rename(temp_svg_path, svg_path)

    # PNG: the SVG is the truth for graphics, attributes.json for csys.
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_text = f.read()
    inner_svg = drawing_contents(svg_text, group_name)
    if inner_svg is None:
        cli.warn("Could not find contents group in SVG — PNG will only draw csys.")
        inner_svg = ""
    img, _ = render_drawing(drawing_shapes(inner_svg), csys_children)
    img.save(fileio.path("drawing png"), dpi=(1000, 1000))

    print(f"Part file '{state.partnumber('pn')}' updated\n")


def drawing_contents(svg_text, group_name):
    """Text between a drawing's contents-start and contents-end tags, or None.

    Comments and template blocks (pattern, gradient, defs, clipPath, ...) are
    removed. A template is drawn only where a fill points at it, never at its
    own coordinates.
    """
    start_tag = f'<g id="{group_name}-contents-start">'
    end_tag = f'<g id="{group_name}-contents-end">'
    start_idx = svg_text.find(start_tag)
    end_idx = svg_text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return None
    inner = svg_text[start_idx + len(start_tag) : end_idx]
    inner = re.sub(r"<!--.*?-->", "", inner, flags=re.DOTALL)
    return re.sub(
        r"<(defs|pattern|clipPath|mask|symbol|marker|linearGradient|radialGradient"
        r"|filter|style)\b.*?</\1\s*>",
        "",
        inner,
        flags=re.DOTALL,
    )


def drawing_shapes(inner_svg):
    """Shapes of a part drawing in SVG pixels, in document order.

    Each shape is ``(kind, params)``. ``kind`` is ``rect``, ``circle``,
    ``line``, ``polygon``, ``path``, or ``text``. An ellipse, a polyline, and
    a rect or circle with a transform come back as ``polygon`` or ``path``. A
    path's ``subpaths`` are ``(points, closed)`` with curves and arcs sampled
    into points. ``fill`` and ``stroke`` are the written values, or None.
    ``source`` is the start of the tag, for messages.

    Raises ValueError when a number in a tag cannot be read.
    """
    number_pattern = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

    def attr(tag, name, default=None):
        m = re.search(rf'(?<![\w-]){name}\s*=\s*"([^"]*)"', tag)
        if m:
            return m.group(1).strip()
        m = re.search(rf'(?<![\w-])style\s*=\s*"[^"]*(?<![\w-]){name}\s*:\s*([^;"]+)', tag)
        return m.group(1).strip() if m else default

    def num(tag, name, default=0.0):
        value = attr(tag, name)
        if value in (None, ""):
            return default
        try:
            return float(value.removesuffix("px"))
        except ValueError:
            raise ValueError(f"Could not read {name}={value!r} in {tag[:160]}")

    def floats(text, tag):
        found = re.findall(number_pattern, text)
        leftover = re.sub(number_pattern, "", text)
        if re.search(r"[^\s,]", leftover):
            raise ValueError(f"Could not read the numbers {text.strip()!r} in {tag[:160]}")
        return [float(n) for n in found]

    def mat_mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    def parse_transform(transform_str, tag):
        mat = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        for op, args_str in re.findall(
            r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", transform_str or ""
        ):
            nums = floats(args_str, tag)
            op = op.lower()
            m2 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            if op == "matrix" and len(nums) == 6:
                a, b, c, d, e, f = nums
                m2 = [[a, c, e], [b, d, f], [0.0, 0.0, 1.0]]
            elif op == "translate" and nums:
                m2 = [[1.0, 0.0, nums[0]], [0.0, 1.0, nums[1] if len(nums) > 1 else 0.0], [0.0, 0.0, 1.0]]
            elif op == "scale" and nums:
                sy = nums[1] if len(nums) > 1 else nums[0]
                m2 = [[nums[0], 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]]
            elif op == "rotate" and nums:
                rad = math.radians(nums[0])
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                m2 = [[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0], [0.0, 0.0, 1.0]]
                if len(nums) == 3:
                    cx, cy = nums[1], nums[2]
                    m2 = mat_mul(
                        mat_mul([[1, 0, cx], [0, 1, cy], [0, 0, 1]], m2),
                        [[1, 0, -cx], [0, 1, -cy], [0, 0, 1]],
                    )
            elif op == "skewx" and nums:
                m2 = [[1, math.tan(math.radians(nums[0])), 0], [0, 1, 0], [0, 0, 1]]
            elif op == "skewy" and nums:
                m2 = [[1, 0, 0], [math.tan(math.radians(nums[0])), 1, 0], [0, 0, 1]]
            mat = mat_mul(mat, m2)
        return mat

    def path_subpaths(d, tag):
        arity = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
        subpaths = []
        points = []
        x = y = 0.0
        start = (0.0, 0.0)
        prev_cubic = prev_quad = None
        for cmd, arg_text in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
            lower = cmd.lower()
            nums = floats(arg_text, tag)
            if lower == "z":
                if len(points) > 1:
                    subpaths.append((points, True))
                points = []
                x, y = start
                prev_cubic = prev_quad = None
                continue
            n = arity[lower]
            if not nums or len(nums) % n:
                raise ValueError(
                    f"Path command {cmd} takes numbers in groups of {n}, got {arg_text.strip()!r} in {tag[:160]}"
                )
            for k in range(0, len(nums), n):
                a = nums[k : k + n]
                ox, oy = (x, y) if cmd.islower() else (0.0, 0.0)
                if lower == "m" and k == 0:
                    if len(points) > 1:
                        subpaths.append((points, False))
                    x, y = ox + a[0], oy + a[1]
                    start = (x, y)
                    points = [(x, y)]
                    prev_cubic = prev_quad = None
                    continue
                if not points:
                    points = [(x, y)]
                new_cubic = new_quad = None
                if lower in ("m", "l"):
                    x, y = ox + a[0], oy + a[1]
                    points.append((x, y))
                elif lower == "h":
                    x = ox + a[0]
                    points.append((x, y))
                elif lower == "v":
                    y = oy + a[0]
                    points.append((x, y))
                elif lower in ("c", "s"):
                    if lower == "c":
                        c1 = (ox + a[0], oy + a[1])
                        rest = a[2:]
                    else:
                        c1 = (2 * x - prev_cubic[0], 2 * y - prev_cubic[1]) if prev_cubic else (x, y)
                        rest = a
                    c2 = (ox + rest[0], oy + rest[1])
                    end = (ox + rest[2], oy + rest[3])
                    for i in range(1, 17):
                        t = i / 16
                        u = 1 - t
                        points.append((
                            u**3 * x + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * end[0],
                            u**3 * y + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * end[1],
                        ))
                    new_cubic = c2
                    x, y = end
                elif lower in ("q", "t"):
                    if lower == "q":
                        q = (ox + a[0], oy + a[1])
                        end = (ox + a[2], oy + a[3])
                    else:
                        q = (2 * x - prev_quad[0], 2 * y - prev_quad[1]) if prev_quad else (x, y)
                        end = (ox + a[0], oy + a[1])
                    for i in range(1, 17):
                        t = i / 16
                        u = 1 - t
                        points.append((
                            u * u * x + 2 * u * t * q[0] + t * t * end[0],
                            u * u * y + 2 * u * t * q[1] + t * t * end[1],
                        ))
                    new_quad = q
                    x, y = end
                elif lower == "a":
                    # Endpoint to center form, SVG 1.1 appendix F.6.5.
                    rx, ry = abs(a[0]), abs(a[1])
                    phi = math.radians(a[2])
                    large, sweep = a[3] != 0, a[4] != 0
                    end = (ox + a[5], oy + a[6])
                    if rx == 0 or ry == 0 or end == (x, y):
                        points.append(end)
                    else:
                        cos_p, sin_p = math.cos(phi), math.sin(phi)
                        dx, dy = (x - end[0]) / 2, (y - end[1]) / 2
                        x1p = cos_p * dx + sin_p * dy
                        y1p = -sin_p * dx + cos_p * dy
                        scale = x1p**2 / rx**2 + y1p**2 / ry**2
                        if scale > 1:
                            rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
                        top = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
                        bottom = rx * rx * y1p * y1p + ry * ry * x1p * x1p
                        coef = math.sqrt(max(0.0, top / bottom)) if bottom else 0.0
                        if large == sweep:
                            coef = -coef
                        cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
                        cx = cos_p * cxp - sin_p * cyp + (x + end[0]) / 2
                        cy = sin_p * cxp + cos_p * cyp + (y + end[1]) / 2
                        ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
                        vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
                        theta = math.atan2(uy, ux)
                        delta = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
                        if not sweep and delta > 0:
                            delta -= 2 * math.pi
                        elif sweep and delta < 0:
                            delta += 2 * math.pi
                        for i in range(1, 25):
                            t = theta + delta * i / 24
                            points.append((
                                cx + rx * math.cos(t) * cos_p - ry * math.sin(t) * sin_p,
                                cy + rx * math.cos(t) * sin_p + ry * math.sin(t) * cos_p,
                            ))
                    x, y = end
                prev_cubic, prev_quad = new_cubic, new_quad
        if len(points) > 1:
            subpaths.append((points, False))
        return subpaths

    shapes = []
    for m in re.finditer(
        r"<(rect|circle|ellipse|line|polyline|polygon|path)\b[^>]*>|<text\b[^>]*>.*?</text>",
        inner_svg,
        flags=re.DOTALL,
    ):
        tag = m.group(0)
        kind = m.group(1) or "text"
        mat = parse_transform(attr(tag, "transform"), tag)

        def apply(px, py):
            return (
                mat[0][0] * px + mat[0][1] * py + mat[0][2],
                mat[1][0] * px + mat[1][1] * py + mat[1][2],
            )

        has_transform = bool(attr(tag, "transform"))
        params = {
            "fill": attr(tag, "fill"),
            "stroke": attr(tag, "stroke"),
            "sw": num(tag, "stroke-width", 1.0),
            "source": tag[:160],
        }

        if kind == "rect":
            x, y = num(tag, "x"), num(tag, "y")
            w, h = num(tag, "width"), num(tag, "height")
            if has_transform:
                corners = [apply(*p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
                shapes.append(("polygon", {**params, "points": corners}))
            else:
                shapes.append(("rect", {**params, "x": x, "y": y, "w": w, "h": h}))
        elif kind == "circle":
            cx, cy = apply(num(tag, "cx"), num(tag, "cy"))
            shapes.append(("circle", {**params, "cx": cx, "cy": cy, "r": num(tag, "r")}))
        elif kind == "ellipse":
            cx, cy = num(tag, "cx"), num(tag, "cy")
            rx, ry = num(tag, "rx"), num(tag, "ry")
            pts = [
                apply(cx + rx * math.cos(2 * math.pi * i / 48), cy + ry * math.sin(2 * math.pi * i / 48))
                for i in range(48)
            ]
            shapes.append(("path", {**params, "subpaths": [(pts, True)]}))
        elif kind == "line":
            x1, y1 = apply(num(tag, "x1"), num(tag, "y1"))
            x2, y2 = apply(num(tag, "x2"), num(tag, "y2"))
            shapes.append(("line", {**params, "x1": x1, "y1": y1, "x2": x2, "y2": y2}))
        elif kind in ("polygon", "polyline"):
            nums = floats(attr(tag, "points", ""), tag)
            pts = [apply(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if kind == "polygon":
                shapes.append(("polygon", {**params, "points": pts}))
            else:
                shapes.append(("path", {**params, "subpaths": [(pts, False)] if len(pts) > 1 else []}))
        elif kind == "path":
            subpaths = [
                ([apply(*p) for p in pts], closed)
                for pts, closed in path_subpaths(attr(tag, "d", ""), tag)
            ]
            shapes.append(("path", {**params, "subpaths": subpaths}))
        else:
            open_tag = re.match(r"<text\b[^>]*>", tag).group(0)
            x, y = apply(num(open_tag, "x"), num(open_tag, "y"))
            text = re.sub(r"<.*?>", "", tag[len(open_tag) :]).strip()
            shapes.append(("text", {**params, "x": x, "y": y, "text": text}))
    return shapes


def csys_svg_xy(csys):
    """SVG pixel location of one csys child (96 px per inch, SVG y = -y).

    Cartesian ``x``/``y`` win when both are given. Otherwise polar
    ``distance``/``angle`` are used.
    """
    raw_x, raw_y = csys.get("x"), csys.get("y")
    raw_d, raw_a = csys.get("distance"), csys.get("angle")
    if raw_x not in ("", None) and raw_y not in ("", None):
        x_in, y_in = float(raw_x), float(raw_y)
    elif raw_d not in ("", None) and raw_a not in ("", None):
        ang = math.radians(float(raw_a))
        x_in, y_in = float(raw_d) * math.cos(ang), float(raw_d) * math.sin(ang)
    else:
        x_in, y_in = 0.0, 0.0
    return x_in * 96, -y_in * 96


def render_drawing(shapes, csys_children, padding=50, zoom=1.0, label_leaders=True):
    """Draw part drawing shapes and csys markers on a white canvas.

    ``label_leaders`` False leaves the names off csys children whose name
    contains "leader", so balloon names stay readable.

    Returns ``(image, to_png)``. ``to_png(x, y)`` maps SVG pixels to image
    pixels. The canvas fits every shape and csys marker, plus ``padding``.
    """
    arrow_len = 24

    def normalize_color(color, default=None):
        # Turn SVG/CSS color text into something Pillow can draw.
        if color is None:
            return default
        c = str(color).strip()
        if not c:
            return default
        if c.lower() in ("none", "transparent") or c.lower().startswith("url("):
            return None
        m = re.match(r"rgba?\s*\(([^)]+)\)", c, flags=re.IGNORECASE)
        if m:
            nums = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+", m.group(1))]
            if len(nums) in (3, 4):
                alpha = nums[3] if len(nums) == 4 else 1.0
                if alpha > 1.0:
                    alpha = alpha / 255.0
                alpha = max(0.0, min(1.0, alpha))
                # Blend onto white so the image stays RGB.
                rgb = [max(0, min(255, int(round(255 * (1 - alpha) + ch * alpha)))) for ch in nums[:3]]
                return "#{:02X}{:02X}{:02X}".format(*rgb)
        if c.startswith("#") and len(c) == 9:
            return c[:7]
        return c

    def axes_endpoints(csys, base_x, base_y):
        rot = math.radians(float(csys.get("rotation", 0) or 0))
        return (
            (base_x + math.cos(rot) * arrow_len, base_y - math.sin(rot) * arrow_len),
            (base_x - math.sin(rot) * arrow_len, base_y - math.cos(rot) * arrow_len),
        )

    pts = []
    for kind, p in shapes:
        if kind == "rect":
            pts += [(p["x"], p["y"]), (p["x"] + p["w"], p["y"] + p["h"])]
        elif kind == "circle":
            pts += [(p["cx"] - p["r"], p["cy"] - p["r"]), (p["cx"] + p["r"], p["cy"] + p["r"])]
        elif kind == "line":
            pts += [(p["x1"], p["y1"]), (p["x2"], p["y2"])]
        elif kind == "polygon":
            pts += p["points"]
        elif kind == "path":
            for sub_pts, _ in p["subpaths"]:
                pts += sub_pts
        elif kind == "text":
            pts.append((p["x"], p["y"]))
    for csys in csys_children.values():
        bx, by = csys_svg_xy(csys)
        pts.append((bx, by))
        pts += list(axes_endpoints(csys, bx, by))
    pts = [p for p in pts if math.isfinite(p[0]) and math.isfinite(p[1])] or [(0, 0)]

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    def to_png(x, y):
        return ((x - min_x) * zoom + padding, (y - min_y) * zoom + padding)

    img = Image.new(
        "RGB",
        (int((max_x - min_x) * zoom + 2 * padding) + 1, int((max_y - min_y) * zoom + 2 * padding) + 1),
        "white",
    )
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", max(8, round(8 * zoom)))
    except Exception:
        font = ImageFont.load_default()

    def width_of(p):
        return max(1, round(p["sw"] * zoom))

    for kind, p in shapes:
        try:
            if kind == "rect":
                x1, y1 = to_png(p["x"], p["y"])
                x2, y2 = to_png(p["x"] + p["w"], p["y"] + p["h"])
                stroke = normalize_color(p["stroke"])
                draw.rectangle(
                    (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
                    fill=normalize_color(p["fill"]),
                    outline=stroke,
                    width=width_of(p) if stroke else 0,
                )
            elif kind == "circle":
                cx, cy = to_png(p["cx"], p["cy"])
                r = abs(p["r"]) * zoom
                stroke = normalize_color(p["stroke"])
                draw.ellipse(
                    (cx - r, cy - r, cx + r, cy + r),
                    fill=normalize_color(p["fill"]),
                    outline=stroke,
                    width=width_of(p) if stroke else 0,
                )
            elif kind == "line":
                draw.line(
                    (to_png(p["x1"], p["y1"]), to_png(p["x2"], p["y2"])),
                    fill=normalize_color(p["stroke"], "black"),
                    width=width_of(p),
                )
            elif kind in ("polygon", "path"):
                subpaths = [(p["points"], True)] if kind == "polygon" else p["subpaths"]
                fill = normalize_color(p["fill"])
                stroke = normalize_color(p["stroke"])
                for sub_pts, closed in subpaths:
                    png_pts = [to_png(x, y) for x, y in sub_pts]
                    if fill and closed and len(png_pts) >= 3:
                        draw.polygon(png_pts, fill=fill)
                    if stroke and len(png_pts) >= 2:
                        draw.line(png_pts + png_pts[:1] if closed else png_pts, fill=stroke, width=width_of(p))
            elif kind == "text":
                draw.text(to_png(p["x"], p["y"]), p["text"], fill=normalize_color(p["fill"], "black"), font=font)
        except Exception as e:
            cli.warn(f"Failed to draw {p['source']}: {e}")

    dot_radius = 4 * zoom
    for csys_name, csys in csys_children.items():
        bx, by = csys_svg_xy(csys)
        cx, cy = to_png(bx, by)
        draw.ellipse((cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius), fill="black")
        (x_x, y_x), (x_y, y_y) = axes_endpoints(csys, bx, by)
        draw.line(((cx, cy), to_png(x_x, y_x)), fill="red", width=max(2, round(2 * zoom)))
        draw.line(((cx, cy), to_png(x_y, y_y)), fill="green", width=max(2, round(2 * zoom)))
        if label_leaders or "leader" not in csys_name:
            draw.text((cx + 6 * zoom, cy - 6 * zoom), csys_name, fill="blue", font=font)

    return img, to_png


def check_drawings(argv):
    """``harnice --check-drawing PATH [PATH ...]``: check part drawings.

    Agents run this on a part family's output. Each PATH is a drawing.svg,
    a revision folder, or a part number folder (its highest revision).

    A drawing fails when the frame is wrong: a transform in the drawing
    group, the origin off the part along X, the
    centerline off y = 0, a shape with zero or negative size, a color an SVG
    reader cannot use, a mate csys off the mating face, a flagnote leader off
    the outline, or a balloon on top of the part. ``--length`` and
    ``--height`` also check the overall size.

    Every drawing is drawn into one PNG with the origin, the centerline, and
    the +X direction marked, for the agent to look at. Exits 1 when any
    drawing fails.
    """
    import argparse
    import tempfile

    import webcolors

    px_per_in = 96.0
    on_edge_in = 0.03  # a rear edge or 3d-mate this close to x is at x
    leader_slop_in = 0.05  # a leader this close to the outline is on it, stroke included
    allowed_tags = {
        "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path",
        "text", "tspan", "title", "desc",
    }  # fmt: skip

    parser = argparse.ArgumentParser(
        prog="harnice --check-drawing",
        description="Check part drawings: origin, direction, size, colors, and csys.",
    )
    parser.add_argument(
        "paths", nargs="+", help="drawing.svg, a revision folder, or a part number folder"
    )
    parser.add_argument("--length", help="expected overall length along X, like 1.28in or 32.5mm")
    parser.add_argument(
        "--height", help="expected overall height along Y (the max diameter of a round part)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(tempfile.gettempdir(), "harnice-drawing-check.png"),
        help="where to write the check image",
    )
    args = parser.parse_args(argv)

    def inches(text):
        if text is None:
            return None
        m = re.fullmatch(r"\s*(\d*\.?\d+)\s*(in|mm)?\s*", text)
        if not m:
            cli.fatal(f"Could not read '{text}'. Write a number with in or mm, like 1.28in or 32.5mm.")
        value = float(m.group(1))
        return value / 25.4 if m.group(2) == "mm" else value

    expected_length = inches(args.length)
    expected_height = inches(args.height)

    def natural_key(name):
        return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]

    def font(size):
        try:
            return ImageFont.truetype("Arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def check_one(path):
        result = {"name": path, "svg": None, "failures": [], "notes": [], "draw": None}
        failures, notes = result["failures"], result["notes"]

        svg_path = None
        if os.path.isfile(path):
            svg_path = path
        elif os.path.isdir(path):
            if os.path.isfile(os.path.join(path, "drawing.svg")):
                svg_path = os.path.join(path, "drawing.svg")
            else:
                revs = [
                    d
                    for d in os.listdir(path)
                    if re.fullmatch(r"rev\d+", d)
                    and os.path.isfile(os.path.join(path, d, "drawing.svg"))
                ]
                if revs:
                    newest = max(revs, key=lambda d: int(d[3:]))
                    svg_path = os.path.join(path, newest, "drawing.svg")
        if svg_path is None:
            failures.append(f"No drawing.svg at {path}.")
            return result
        result["svg"] = svg_path

        with open(svg_path, "r", encoding="utf-8") as f:
            svg_text = f.read()

        m = re.search(r'<g id="([^"]+)-contents-start">', svg_text)
        if not m:
            failures.append(
                'No <g id="{pn}-drawing-contents-start"> group. The part build reads only '
                "what is inside that group."
            )
            return result
        group_name = m.group(1)
        result["name"] = group_name.removesuffix("-drawing")
        inner = drawing_contents(svg_text, group_name)
        if inner is None:
            failures.append(f'No <g id="{group_name}-contents-end"> group after the start group.')
            return result

        transformed = re.findall(r"<(\w+)\b[^>]*\btransform\s*=", inner)
        if transformed:
            failures.append(
                f"{len(transformed)} element(s) in the drawing group use transform= "
                f"(first: <{transformed[0]}>). A transform moves the origin. Write every "
                "coordinate in the part frame instead: origin at the cable-entry face, "
                "+X toward the mating face, SVG y = -y."
            )
        unknown = sorted(set(re.findall(r"<([a-zA-Z][\w:-]*)", inner)) - allowed_tags)
        if unknown:
            failures.append(
                f"{', '.join('<' + t + '>' for t in unknown)} in the drawing group are not "
                "checked and not drawn in drawing.png. Draw with rect, circle, ellipse, line, "
                "polyline, polygon, path, and text."
            )

        try:
            shapes = drawing_shapes(inner)
        except ValueError as e:
            failures.append(str(e))
            return result

        csys = {}
        attributes_path = os.path.join(os.path.dirname(svg_path), "attributes.json")
        if os.path.isfile(attributes_path):
            try:
                with open(attributes_path, "r", encoding="utf-8") as f:
                    csys = json.load(f).get("csys_children") or {}
            except (json.JSONDecodeError, AttributeError) as e:
                failures.append(f"Could not read {attributes_path}: {e}")
        else:
            notes.append("No attributes.json next to the drawing, so csys was not checked.")
        csys = {k: v for k, v in csys.items() if isinstance(v, dict)}

        # Outline geometry in SVG pixels.
        outline_pts = []
        edges = []
        areas = []
        circles = []
        bad = []
        for kind, p in shapes:
            if kind == "text":
                continue
            if kind == "rect":
                x, y, w, h = p["x"], p["y"], p["w"], p["h"]
                corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                if not (w > 0 and h > 0):
                    bad.append(p["source"])
                    continue
                outline_pts += corners
                edges += list(zip(corners, corners[1:] + corners[:1]))
                areas.append(corners)
            elif kind == "circle":
                cx, cy, r = p["cx"], p["cy"], p["r"]
                if not r > 0:
                    bad.append(p["source"])
                    continue
                outline_pts += [(cx - r, cy - r), (cx + r, cy + r)]
                circles.append((cx, cy, r))
            else:
                if kind == "line":
                    subpaths = [([(p["x1"], p["y1"]), (p["x2"], p["y2"])], False)]
                elif kind == "polygon":
                    subpaths = [(p["points"], True)]
                else:
                    subpaths = p["subpaths"]
                pts = [pt for sub_pts, _ in subpaths for pt in sub_pts]
                finite = all(math.isfinite(v) for pt in pts for v in pt)
                if (
                    not finite
                    or len(pts) < 2
                    or (kind == "polygon" and len(pts) < 3)
                    or (
                        max(x for x, _ in pts) - min(x for x, _ in pts) == 0
                        and max(y for _, y in pts) - min(y for _, y in pts) == 0
                    )
                ):
                    bad.append(p["source"])
                    continue
                outline_pts += pts
                for sub_pts, closed in subpaths:
                    ring = sub_pts + sub_pts[:1] if closed else sub_pts
                    edges += list(zip(ring, ring[1:]))
                    if closed and len(sub_pts) >= 3:
                        areas.append(sub_pts)
        if bad:
            failures.append(
                f"{len(bad)} shape(s) have zero or negative size (first: {bad[0]}). A parameter "
                "probably went to zero or below for this part number."
            )

        def color_ok(value):
            v = value.strip()
            if v.lower() in ("none", "transparent", "currentcolor"):
                return True
            ref = re.fullmatch(r"url\(\s*#([^)\s]+)\s*\)", v)
            if ref:
                return f'id="{ref.group(1)}"' in svg_text
            if re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", v):
                return True
            if re.fullmatch(r"rgba?\(\s*[\d.%\s,]+\)", v):
                return True
            try:
                webcolors.name_to_hex(v)
                return True
            except ValueError:
                return False

        bad_colors = sorted(
            {
                v
                for _, p in shapes
                for v in (p["fill"], p["stroke"])
                if v is not None and not color_ok(v)
            }
        )
        if bad_colors:
            failures.append(
                f"Colors an SVG reader cannot use: {', '.join(repr(c) for c in bad_colors)}. Use "
                "#rrggbb, a CSS color name, none, or url(#id) of a pattern in this file."
            )

        if not outline_pts:
            if not bad:
                failures.append("The drawing group has no shapes.")
            return result
        if (
            len(shapes) == 1
            and shapes[0][0] == "rect"
            and (shapes[0][1]["x"], shapes[0][1]["y"], shapes[0][1]["w"], shapes[0][1]["h"])
            == (0, -48, 96, 96)
        ):
            failures.append("The drawing is still the placeholder box part.py writes before a drawing exists.")

        rear = min(x for x, _ in outline_pts) / px_per_in
        front = max(x for x, _ in outline_pts) / px_per_in
        top = -min(y for _, y in outline_pts) / px_per_in
        bottom = -max(y for _, y in outline_pts) / px_per_in
        length, height = front - rear, top - bottom
        result["size"] = (length, height)
        notes.append(f"rear edge x = {rear:.3f} in, front edge x = {front:.3f} in")
        notes.append(
            f"length {length:.3f} in ({length * 25.4:.2f} mm), "
            f"height {height:.3f} in ({height * 25.4:.2f} mm)"
        )
        if abs(top + bottom) <= 0.01:
            notes.append("symmetric about the centerline (y = 0)")
        else:
            notes.append(
                f"not symmetric about y = 0: top {top:+.3f} in, bottom {bottom:+.3f} in. "
                "Fine for a latch or a tab. Wrong for a plain round part."
            )

        # The origin lies somewhere along the part. A part may sit wholly in -X
        # (a ferrule whose origin is its tip). Direction is checked by 3d-mate.
        if rear > on_edge_in:
            failures.append(
                f"The part starts {rear:.3f} in in front of the origin. Put x = 0 on the "
                "part: the cable-entry face, or where the user said it is."
            )
        elif front < -on_edge_in:
            failures.append(
                f"The part ends {-front:.3f} in behind the origin. Put x = 0 on the part: "
                "the cable-entry face, or where the user said it is."
            )
        if bottom >= -on_edge_in or top <= on_edge_in:
            side = "above" if bottom >= -on_edge_in else "below"
            failures.append(
                f"The part sits entirely {side} y = 0. The centerline runs along y = 0. "
                "Remember SVG y = -y: the top edge of a part of radius r is y = -r."
            )
        if expected_length is not None and abs(length - expected_length) > max(
            0.02, 0.02 * expected_length
        ):
            failures.append(f"Length is {length:.3f} in. Expected {expected_length:.3f} in.")
        if expected_height is not None and abs(height - expected_height) > max(
            0.02, 0.02 * expected_height
        ):
            failures.append(f"Height is {height:.3f} in. Expected {expected_height:.3f} in.")

        both = sorted(
            (
                name
                for name, c in csys.items()
                if any(c.get(k) not in ("", None) for k in ("x", "y"))
                and c.get("distance") not in ("", None)
            ),
            key=natural_key,
        )
        if both:
            failures.append(
                f"{', '.join(both)} give both x/y and distance/angle. part.py adds them "
                "together. Give one or the other."
            )

        # A connector's 3d-mate is its mating face. An accessory's connector and
        # 3d-connector are where the connector's own origin lands, which sits inside
        # the accessory where the threads overlap, so they are not checked here.
        # A connector's 3d-mate is on its mating face (the front edge); a
        # terminal's is where its stud goes. Either way it is on the part,
        # which also catches a part drawn backwards.
        if "3d-mate" in csys:
            mate_x = csys_svg_xy(csys["3d-mate"])[0] / px_per_in
            if not rear - on_edge_in <= mate_x <= front + on_edge_in:
                failures.append(
                    f"3d-mate is at x = {mate_x:.3f} in, off the part (x = {rear:.3f} to "
                    f"{front:.3f} in). Put it on the mating face, or where the stud goes on a "
                    "terminal, from the same station variable the drawing uses."
                )
            elif abs(mate_x - front) <= on_edge_in:
                notes.append(f"3d-mate x = {mate_x:.3f} in, on the front edge")
            else:
                notes.append(f"3d-mate x = {mate_x:.3f} in, on the part")

        def distance_to_outline(px, py):
            best = math.inf
            for (x1, y1), (x2, y2) in edges:
                dx, dy = x2 - x1, y2 - y1
                seg = dx * dx + dy * dy
                t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg))
                best = min(best, math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)))
            for cx, cy, r in circles:
                best = min(best, abs(math.hypot(px - cx, py - cy) - r))
            return best

        def inside_part(px, py):
            for cx, cy, r in circles:
                if math.hypot(px - cx, py - cy) < r:
                    return True
            for ring in areas:
                inside = False
                for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                    if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                        inside = not inside
                if inside:
                    return True
            return False

        off = []
        for name in sorted(csys, key=natural_key):
            if re.fullmatch(r"flagnote-\d+-leader_dest|flagnote-leader-\d+", name):
                d = distance_to_outline(*csys_svg_xy(csys[name])) / px_per_in
                if d > leader_slop_in:
                    off.append(f"{name} ({d:.2f} in off)")
        if off:
            more = f", and {len(off) - 5} more" if len(off) > 5 else ""
            failures.append(
                f"{len(off)} flagnote leader(s) do not land on the outline: "
                f"{', '.join(off[:5])}{more}. Shoot each ray from inside the part and keep "
                "the farthest crossing of the outline."
            )
        on_part = [
            name
            for name in sorted(csys, key=natural_key)
            if re.fullmatch(r"flagnote-\d+", name) and inside_part(*csys_svg_xy(csys[name]))
        ]
        if on_part:
            failures.append(f"{', '.join(on_part)} sit on top of the part. Balloons go outside the outline.")

        result["draw"] = (shapes, csys, bottom, front)
        return result

    results = [check_one(path) for path in args.paths]

    for r in results:
        print(f"{r['name']}  {'FAIL' if r['failures'] else 'PASS'}  {r['svg'] or ''}")
        for note in r["notes"]:
            print(f"  {note}")
        for failure in r["failures"]:
            print(f"  FAIL: {failure}")

    max_panels = 12
    drawn = [r for r in results if r["draw"] and r["failures"]]
    drawn += [r for r in results if r["draw"] and not r["failures"]]
    drawn = drawn[:max_panels]
    panels = []
    for r in drawn:
        # The drawing, then the frame the drawing should follow.
        shapes, csys, bottom, front = r["draw"]
        zoom = 1.5
        img, to_png = render_drawing(shapes, csys, padding=170, zoom=zoom, label_leaders=False)
        draw = ImageDraw.Draw(img)
        label = font(13)
        for name in csys:
            dest = csys.get(f"{name}-leader_dest")
            if re.fullmatch(r"flagnote-\d+", name) and dest:
                draw.line((to_png(*csys_svg_xy(csys[name])), to_png(*csys_svg_xy(dest))), fill="#8A8A8A", width=1)
        ox, oy = to_png(0, 0)
        for x in range(0, img.width, 12):
            draw.line(((x, oy), (x + 6, oy)), fill="#9A9A9A", width=1)
        arrow_y = to_png(0, -bottom * px_per_in)[1] + 26
        tip_x = to_png(max(front, 0.5) * px_per_in, 0)[0]
        draw.line(((ox, oy), (ox, arrow_y)), fill="#C000C0", width=1)
        draw.line(((ox, arrow_y), (tip_x, arrow_y)), fill="#C000C0", width=3)
        draw.polygon(
            [(tip_x + 2, arrow_y), (tip_x - 12, arrow_y - 7), (tip_x - 12, arrow_y + 7)], fill="#C000C0"
        )
        cable_text = "cable side, x = 0"
        draw.text(
            (ox - 8 - draw.textlength(cable_text, font=label), arrow_y - 8),
            cable_text,
            fill="#C000C0",
            font=label,
        )
        draw.text((tip_x + 8, arrow_y - 8), "+X toward mating face", fill="#C000C0", font=label)
        draw.line(((ox - 12, oy), (ox + 12, oy)), fill="#C000C0", width=3)
        draw.line(((ox, oy - 12), (ox, oy + 12)), fill="#C000C0", width=3)
        draw.text((ox - 60, oy - 30), "ORIGIN", fill="#C000C0", font=label)

        title_font, line_font = font(18), font(13)
        panel = Image.new("RGB", (max(img.width, 420), img.height + 52), "white")
        panel.paste(img, (0, 52))
        draw = ImageDraw.Draw(panel)
        status = "FAIL" if r["failures"] else "PASS"
        draw.text((10, 6), r["name"], fill="black", font=title_font)
        draw.text(
            (panel.width - 60, 6), status, fill="#B00020" if r["failures"] else "#107C10", font=title_font
        )
        if "size" in r:
            length, height = r["size"]
            draw.text((10, 30), f"length {length:.3f} in   height {height:.3f} in", fill="#444444", font=line_font)
        draw.rectangle((0, 0, panel.width - 1, panel.height - 1), outline="#CCCCCC")
        if panel.width > 900:
            panel = panel.resize((900, round(panel.height * 900 / panel.width)))
        panels.append(panel)

    if panels:
        columns = min(3, len(panels))
        rows = [panels[i : i + columns] for i in range(0, len(panels), columns)]
        gap = 12
        col_width = max(p.width for p in panels)
        row_heights = [max(p.height for p in row) for row in rows]
        sheet = Image.new(
            "RGB",
            (columns * col_width + (columns + 1) * gap, sum(row_heights) + (len(rows) + 1) * gap),
            "white",
        )
        y = gap
        for row, row_height in zip(rows, row_heights):
            x = gap
            for panel in row:
                sheet.paste(panel, (x, y))
                x += col_width + gap
            y += row_height + gap
        sheet.save(args.output)
        print()
        print(f"Check image: {args.output}")
        if len(drawn) < sum(1 for r in results if r["draw"]):
            print(
                f"It shows {len(drawn)} of {sum(1 for r in results if r['draw'])} drawings, "
                "failed ones first. Pass fewer paths to see the others."
            )
        print(
            "Open it. Confirm each part's origin is at the ORIGIN mark, the part runs along "
            "the +X arrow to the mating face, and its balloons sit clear of the outline."
        )

    failed = sum(1 for r in results if r["failures"])
    if failed:
        print(f"\n{failed} of {len(results)} drawings failed.")
        raise SystemExit(1)
