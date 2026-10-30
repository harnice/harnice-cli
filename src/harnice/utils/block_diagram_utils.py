import math
import re
from io import StringIO
import xml.etree.ElementTree as ET

_SVG_NS_URI = "http://www.w3.org/2000/svg"
_SCHEM_NS_URI = "https://example.com/schema/v1"
ET.register_namespace("", _SVG_NS_URI)
ET.register_namespace("schem", _SCHEM_NS_URI)

_SVG_NS_FALLBACKS = (
    ("schem", "https://example.com/schema/v1"),
    ("inkscape", "http://www.inkscape.org/namespaces/inkscape"),
    ("sodipodi", "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"),
    ("xlink", "http://www.w3.org/1999/xlink"),
    ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ("cc", "http://creativecommons.org/ns#"),
    ("dc", "http://purl.org/dc/elements/1.1/"),
)
_SVG_PREFIX_URIS = dict(_SVG_NS_FALLBACKS)
for _prefix, _uri in _SVG_NS_FALLBACKS:
    ET.register_namespace(_prefix, _uri)

_SVG_DEVICES_PARENT_GROUP_IDS = frozenset({"devices"})

BD_APPLIED_TRACES_GROUP_ID = "applied-traces"
BD_CHANNEL_TRACES_GROUP_ID = "channel_traces"
BD_CIRCUIT_TRACES_GROUP_ID = "circuit_traces"
_BLOCK_DIAGRAM_OVERLAY_HTML_COMMENT_RE = re.compile(
    r"<!--\s*harnice:block-diagram[^>]*-->\s*",
    re.IGNORECASE,
)


def blank_block_diagram_symbol_svg(contents_id):
    """Minimal device block diagram symbol, including a ``{refdes}`` text box."""
    contents_id = (contents_id or "").strip() or "symbol-contents-start"
    if contents_id.endswith("-contents-start"):
        contents_end = contents_id[: -len("-contents-start")] + "-contents-end"
    else:
        contents_end = contents_id + "-contents-end"
    view_box = "0 0 400 400"
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" data-bbox="{view_box}">
  <g id="{contents_id}" class="component device">
    <text class="diagram-primitive" x="8" y="16" font-family="Helvetica" font-size="12pt" font-weight="normal" fill="black" fill-opacity="1" stroke="none" stroke-width="0.2mm" stroke-opacity="1" text-anchor="start" dominant-baseline="alphabetic" data-wrap-width="120" data-text="&quot;{{refdes}}&quot;">{{refdes}}</text>
  </g>
  <g id="{contents_end}"></g>
</svg>
'''


def normalize_block_diagram_svg_ns0_elementtree_artifact(svg_text):
    """
    Repair SVG that mixes ``xmlns:ns0`` / ``<ns0:…>`` with unprefixed overlay markup.
    """
    if not svg_text or "xmlns:ns0=" not in svg_text:
        return svg_text
    t = svg_text
    if 'xmlns="http://www.w3.org/2000/svg"' in t[:2500]:
        t = re.sub(
            r'\s+xmlns:ns0="http://www\.w3\.org/2000/svg"',
            "",
            t,
            count=1,
        )
    else:
        t = t.replace(
            'xmlns:ns0="http://www.w3.org/2000/svg"',
            'xmlns="http://www.w3.org/2000/svg"',
            1,
        )
    t = t.replace("<ns0:", "<")
    t = t.replace("</ns0:", "</")
    return t


def _svg_local_tag(tag):
    if tag and tag[0] == "{":
        return tag.split("}", 1)[-1]
    return tag


def _prefixes_used_in_tags(svg_text):
    """Prefixes that appear in element or attribute names."""
    used = set()
    prefix_re = re.compile(r"(?:</?|\s)([A-Za-z_][\w.-]*):")
    for match in re.finditer(r"<[^<>]*>", svg_text):
        tag = match.group(0)
        if tag.startswith("<?") or tag.startswith("<!"):
            continue
        for prefix_match in prefix_re.finditer(tag):
            prefix = prefix_match.group(1)
            if prefix not in ("xmlns", "xml"):
                used.add(prefix)
    return used


def prepare_block_diagram_svg_text(svg_text):
    """Make saved SVG text legal for ElementTree."""
    if not svg_text:
        return svg_text

    def replace_entity(match):
        name = match.group(1)
        if name in ("amp", "lt", "gt", "quot", "apos"):
            return match.group(0)
        return {
            "nbsp": "\u00a0",
            "ndash": "\u2013",
            "mdash": "\u2014",
            "hellip": "\u2026",
            "copy": "\u00a9",
            "reg": "\u00ae",
            "trade": "\u2122",
            "times": "\u00d7",
            "middot": "\u00b7",
        }.get(name, match.group(0))

    def escape_bare_ampersands(text):
        # Leave comments and CDATA alone. ``&`` there is already legal XML.
        entity_re = re.compile(
            r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);|&"
        )
        out = []
        i = 0
        n = len(text)
        while i < n:
            if text.startswith("<!--", i) or text.startswith("<![CDATA[", i):
                end_token = "-->" if text.startswith("<!--", i) else "]]>"
                end = text.find(end_token, i + 4)
                end = n if end < 0 else end + len(end_token)
                out.append(text[i:end])
                i = end
                continue
            if text[i] != "&":
                out.append(text[i])
                i += 1
                continue
            token = entity_re.match(text, i).group(0)
            out.append("&amp;" if token == "&" else token)
            i += len(token)
        return "".join(out)

    def ensure_prefixed_namespaces(text):
        match = re.search(r"<svg\b[^>]*>", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return text
        tag = match.group(0)
        extras = []
        for prefix in sorted(_prefixes_used_in_tags(text)):
            if ("xmlns:%s=" % prefix) in text:
                continue
            uri = _SVG_PREFIX_URIS.get(prefix) or ("https://harnice.io/ns/" + prefix)
            extras.append('xmlns:%s="%s"' % (prefix, uri))
        if not extras:
            return text
        new_tag = tag[:-1] + " " + " ".join(extras) + ">"
        return text[: match.start()] + new_tag + text[match.end() :]

    text = svg_text[1:] if svg_text.startswith("\ufeff") else svg_text
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    text = re.sub(r"&([A-Za-z][A-Za-z0-9]+);", replace_entity, text)
    text = escape_bare_ampersands(text)
    text = normalize_block_diagram_svg_ns0_elementtree_artifact(text)
    return ensure_prefixed_namespaces(text)


def _parse_block_diagram_svg_file(bd_path):
    with open(bd_path, "r", encoding="utf-8") as f:
        text = f.read()
    try:
        return _parse_block_diagram_svg_string(text)
    except ET.ParseError as exc:
        raise ET.ParseError("%s\nin %s" % (exc, bd_path)) from exc


def _parse_block_diagram_svg_string(svg_text):
    def format_parse_error(exc, text):
        message = str(exc)
        match = re.search(r"line (\d+), column (\d+)", message)
        if not match:
            return message
        line_no = int(match.group(1))
        column = int(match.group(2))
        lines = text.splitlines()
        if not (1 <= line_no <= len(lines)):
            return message
        line = lines[line_no - 1]
        start = max(0, column - 70)
        end = min(len(line), column + 70)
        snippet = line[start:end]
        pointer = " " * max(0, column - 1 - start) + "^"
        if start:
            snippet = "…" + snippet
            pointer = " " + pointer
        if end < len(line):
            snippet += "…"
        return "%s\n%s: %s\n%s" % (message, line_no, snippet, pointer)

    def drop_duplicate_attribute(text, exc):
        if "duplicate attribute" not in str(exc):
            return None
        match = re.search(r"line (\d+), column (\d+)", str(exc))
        if not match:
            return None
        line_no = int(match.group(1))
        column = int(match.group(2))
        lines = text.splitlines(keepends=True)
        if not (1 <= line_no <= len(lines)):
            return None
        line = lines[line_no - 1]
        rest = line[column - 1 :]
        attr = re.match(
            r"""\s*([A-Za-z_:][\w:.-]*)\s*=\s*("[^"]*"|'[^']*')""",
            rest,
        )
        if not attr:
            return None
        name = attr.group(1)
        before = line[: column - 1]
        if not re.search(r"(?:^|[\s<])%s\s*=" % re.escape(name), before):
            return None
        lines[line_no - 1] = before + rest[attr.end() :]
        return "".join(lines)

    prepared = prepare_block_diagram_svg_text(svg_text)
    try:
        return ET.parse(StringIO(prepared))
    except ET.ParseError as exc:
        repaired = drop_duplicate_attribute(prepared, exc)
        if repaired and repaired != prepared:
            try:
                return ET.parse(StringIO(repaired))
            except ET.ParseError as again:
                exc = again
                prepared = repaired
        raise ET.ParseError(format_parse_error(exc, prepared)) from exc


def _svg_skip_special_markup(text, pos):
    if text.startswith("<!--", pos):
        end = text.find("-->", pos + 4)
        return len(text) if end < 0 else end + 3
    if text.startswith("<![CDATA[", pos):
        end = text.find("]]>", pos + 9)
        return len(text) if end < 0 else end + 3
    if text.startswith("<?", pos):
        end = text.find("?>", pos + 2)
        return len(text) if end < 0 else end + 2
    return None


def _svg_local_name(raw_name):
    return (raw_name or "").split(":")[-1]


def find_svg_element_span(svg_text, element_id):
    """Return ``(start, open_end, close_start, end)`` for the element with this id.

    ``open_end`` is the index after the opening tag's ``>``. ``close_start`` is
    the ``<`` of the closing tag, or ``None`` when the tag is self-closing.
    ``end`` is exclusive. Returns ``None`` when the id is not found.
    """
    if not svg_text or not element_id:
        return None
    needle_re = re.compile(
        r"""\bid\s*=\s*(["'])""" + re.escape(str(element_id)) + r"\1"
    )
    tag_re = re.compile(r"<(/?)((?:[A-Za-z_][\w.-]*:)?[A-Za-z_][\w.-]*)")
    for match in needle_re.finditer(svg_text):
        attr_i = match.start()
        start = svg_text.rfind("<", 0, attr_i)
        if start < 0 or ">" in svg_text[start:attr_i]:
            continue
        name_m = tag_re.match(svg_text, start)
        if not name_m or name_m.group(1):
            continue
        tag_local = _svg_local_name(name_m.group(2))
        gt = svg_text.find(">", start)
        if gt < 0:
            continue
        open_end = gt + 1
        if svg_text[start:open_end].rstrip().endswith("/>"):
            return (start, open_end, None, open_end)
        depth = 1
        pos = open_end
        while pos < len(svg_text):
            next_lt = svg_text.find("<", pos)
            if next_lt < 0:
                return None
            skipped = _svg_skip_special_markup(svg_text, next_lt)
            if skipped is not None:
                pos = skipped
                continue
            tm = tag_re.match(svg_text, next_lt)
            if not tm:
                pos = next_lt + 1
                continue
            is_close = bool(tm.group(1))
            local = _svg_local_name(tm.group(2))
            ngt = svg_text.find(">", next_lt)
            if ngt < 0:
                return None
            if not is_close and svg_text[next_lt : ngt + 1].rstrip().endswith("/>"):
                pos = ngt + 1
                continue
            if local.lower() != tag_local.lower():
                pos = ngt + 1
                continue
            if is_close:
                depth -= 1
                if depth == 0:
                    return (start, open_end, next_lt, ngt + 1)
                pos = ngt + 1
                continue
            depth += 1
            pos = ngt + 1
        return None
    return None


def replace_svg_element_inner_by_id(svg_text, element_id, new_inner):
    """Replace the children of ``element_id``, keeping its opening and closing tags."""
    span = find_svg_element_span(svg_text, element_id)
    if span is None:
        return None
    start, open_end, close_start, end = span
    if close_start is None:
        open_tag = svg_text[start:end]
        if open_tag.rstrip().endswith("/>"):
            open_tag = open_tag.rstrip()[:-2].rstrip() + ">"
        close_name = _svg_local_name(
            re.match(r"<(/?)((?:[A-Za-z_][\w.-]*:)?[A-Za-z_][\w.-]*)", open_tag).group(2)
        )
        return svg_text[:start] + open_tag + (new_inner or "") + f"</{close_name}>" + svg_text[end:]
    return svg_text[:open_end] + (new_inner or "") + svg_text[close_start:]


def strip_svg_element_by_id(svg_text, element_id):
    """Remove the element with this id. Returns the original text when missing."""
    span = find_svg_element_span(svg_text, element_id)
    if span is None:
        return svg_text
    start, _open_end, _close_start, end = span
    if end < len(svg_text) and svg_text[end] == "\n":
        end += 1
    elif start > 0 and svg_text[start - 1] == "\n":
        start -= 1
    return svg_text[:start] + svg_text[end:]


def insert_after_svg_element_open(svg_text, element_id, markup):
    """Insert ``markup`` immediately after the opening tag of ``element_id``."""
    span = find_svg_element_span(svg_text, element_id)
    if span is None:
        return None
    _start, open_end, close_start, _end = span
    if close_start is None:
        replaced = replace_svg_element_inner_by_id(svg_text, element_id, markup)
        return replaced
    return svg_text[:open_end] + markup + svg_text[open_end:]


def insert_before_svg_element_close(svg_text, element_id, markup):
    """Insert ``markup`` immediately before the closing tag of ``element_id``."""
    span = find_svg_element_span(svg_text, element_id)
    if span is None:
        return None
    _start, _open_end, close_start, _end = span
    if close_start is None:
        return replace_svg_element_inner_by_id(svg_text, element_id, markup)
    return svg_text[:close_start] + markup + svg_text[close_start:]


def add_svg_attribute_by_id(svg_text, element_id, name, value):
    """Add ``name="value"`` to the opening tag of ``element_id`` if missing."""
    span = find_svg_element_span(svg_text, element_id)
    if span is None:
        return None
    start, open_end, _close_start, _end = span
    open_tag = svg_text[start:open_end]
    if re.search(rf"""\b{re.escape(name)}\s*=""", open_tag):
        return svg_text
    insert_at = open_end - 1
    if open_tag.rstrip().endswith("/>"):
        insert_at = start + open_tag.rstrip().rfind("/>")
    padded = f' {name}="{value}"'
    return svg_text[:insert_at] + padded + svg_text[insert_at:]


def add_svg_attribute_by_attr(svg_text, find_attr, find_value, name, value):
    """Add ``name="value"`` to the first element with ``find_attr=find_value``."""
    needle_re = re.compile(
        rf"""\b{re.escape(find_attr)}\s*=\s*(["']){re.escape(str(find_value))}\1"""
    )
    match = needle_re.search(svg_text)
    if not match:
        return None
    start = svg_text.rfind("<", 0, match.start())
    if start < 0 or ">" in svg_text[start : match.start()]:
        return None
    gt = svg_text.find(">", start)
    if gt < 0:
        return None
    open_tag = svg_text[start : gt + 1]
    if re.search(rf"""\b{re.escape(name)}\s*=""", open_tag):
        return svg_text
    insert_at = gt
    if open_tag.rstrip().endswith("/>"):
        insert_at = start + open_tag.rstrip().rfind("/>")
    padded = f' {name}="{value}"'
    return svg_text[:insert_at] + padded + svg_text[insert_at:]


_SVG_NUMERIC_ATTRS = frozenset(
    {
        "cx",
        "cy",
        "r",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "width",
        "height",
        "stroke-width",
        "opacity",
        "font-size",
    }
)


def _normalize_svg_attr_value(key, value):
    if key == "class":
        return " ".join(sorted((value or "").split()))
    if key in _SVG_NUMERIC_ATTRS:
        try:
            return format(float(value), ".6g")
        except (TypeError, ValueError):
            return value
    return value


def svg_subtree_signature(el, ignore_ids=True):
    """Formatting-stable fingerprint of an element tree (optional id ignore)."""
    local = _svg_local_tag(el.tag)
    attrs = []
    for key in sorted(el.attrib):
        if ignore_ids and key == "id":
            continue
        if key.startswith("xmlns") or key == "__line__":
            continue
        attrs.append((key, _normalize_svg_attr_value(key, el.attrib[key])))
    text = (el.text or "").strip()
    kids = tuple(svg_subtree_signature(child, ignore_ids) for child in list(el))
    return (local, tuple(attrs), text, kids)


def svg_children_signature(parent, ignore_ids=True):
    return tuple(svg_subtree_signature(child, ignore_ids) for child in list(parent))


def svg_markup_equivalent(a, b):
    """True when two SVG markup fragments have the same element tree."""
    a = (a or "").strip()
    b = (b or "").strip()
    if a == b:
        return True
    if not a or not b:
        return False
    try:
        ea = ET.fromstring(f"<root>{a}</root>")
        eb = ET.fromstring(f"<root>{b}</root>")
    except ET.ParseError:
        return False
    return svg_subtree_signature(ea) == svg_subtree_signature(eb)


def clone_svg_element(el):
    return ET.fromstring(ET.tostring(el, encoding="unicode"))


def _svg_fragment_preserve_bound_prefixes(fragment):
    """Keep xmlns declarations that a serialized child still needs.

    ElementTree prints ``xmlns:ns1="…"`` and ``ns1:label``. Deleting every
    xmlns and leaving ``ns1:`` makes the next build fail with an unbound prefix.
    """
    if not fragment:
        return fragment
    text = normalize_block_diagram_svg_ns0_elementtree_artifact(fragment)
    xmlns_re = re.compile(r'\sxmlns(?::([A-Za-z_][\w.-]*))?="([^"]*)"')
    prefix_uri = {}
    for match in xmlns_re.finditer(text):
        prefix_uri[match.group(1) or ""] = match.group(2)
    text = xmlns_re.sub("", text)

    uri_prefix = {}
    for prefix, uri in _SVG_NS_FALLBACKS:
        uri_prefix.setdefault(uri, prefix)
    for prefix, uri in list(prefix_uri.items()):
        if not prefix:
            continue
        wanted = uri_prefix.get(uri)
        if not wanted or wanted == prefix:
            continue
        text = text.replace("<%s:" % prefix, "<%s:" % wanted)
        text = text.replace("</%s:" % prefix, "</%s:" % wanted)
        text = text.replace(" %s:" % prefix, " %s:" % wanted)
        prefix_uri[wanted] = uri

    extras = []
    for prefix in sorted(_prefixes_used_in_tags(text)):
        uri = prefix_uri.get(prefix) or _SVG_PREFIX_URIS.get(prefix)
        if not uri:
            uri = "https://harnice.io/ns/" + prefix
        extras.append('xmlns:%s="%s"' % (prefix, uri))
    if not extras:
        return text
    start = re.search(r"<[A-Za-z_][\w.-]*\b", text)
    if not start:
        return text
    return text[: start.end()] + " " + " ".join(extras) + text[start.end() :]


def serialize_svg_element_children(parent):
    """Serialize children without reformatting the rest of a document."""
    return "".join(
        _svg_fragment_preserve_bound_prefixes(ET.tostring(child, encoding="unicode"))
        for child in list(parent)
    )


def copy_matching_svg_ids(dest_parent, src_parent):
    """Copy dest ``id`` values onto matching src elements (pins, labels, geometry)."""

    def match_key(el):
        local = _svg_local_tag(el.tag)
        pin = (el.get("data-pin-name") or "").strip()
        if pin:
            return ("pin", pin)
        if local == "configuration":
            return ("configuration",)
        classes = tuple(sorted((el.get("class") or "").split()))
        geom = tuple(
            (k, _normalize_svg_attr_value(k, el.get(k)))
            for k in (
                "cx",
                "cy",
                "r",
                "x",
                "y",
                "x1",
                "y1",
                "x2",
                "y2",
                "width",
                "height",
                "d",
                "points",
                "transform",
            )
            if el.get(k) is not None
        )
        return ("geom", local, classes, geom)

    dest_by_key = {}
    dups = set()
    for el in dest_parent.iter():
        if el is dest_parent:
            continue
        key = match_key(el)
        if key in dest_by_key:
            dups.add(key)
        else:
            dest_by_key[key] = el
    for key in dups:
        dest_by_key.pop(key, None)
    used = set()
    for el in src_parent.iter():
        if el is src_parent:
            continue
        dest_el = dest_by_key.get(match_key(el))
        if dest_el is None or id(dest_el) in used:
            continue
        dest_id = (dest_el.get("id") or "").strip()
        if dest_id:
            el.set("id", dest_id)
            used.add(id(dest_el))


# Default sheet: 10.5 in wide × 8 in high at 96 SVG user-units per inch.
_BOUNDARY_DEFAULT = {"x": "0", "y": "0", "width": "1008", "height": "768"}

_BOUNDARY_RECT_MARKUP = (
    '<rect id="boundary" class="system-boundary" x="0" y="0" width="1008" '
    'height="768" fill="none" stroke="#000000" stroke-width="1" pointer-events="none"/>'
)


def ensure_system_boundary_rect(svg_text):
    """
    Ensure a bottom-most ``#boundary`` rectangle exists under ``*-contents-start``.

    Default geometry is ``0,0`` → ``1008×768`` (10.5 in × 8 in at 96 dpi), black
    stroke, no fill. Returns the (possibly updated) SVG text. Idempotent when a
    ``rect#boundary`` is already present. Does not rewrite the rest of the file.
    """
    if not svg_text or not str(svg_text).strip():
        return svg_text
    tree = _parse_block_diagram_svg_string(svg_text)
    root = tree.getroot()
    contents_start = None
    for el in root.iter():
        eid = el.get("id") or ""
        if eid.endswith("-contents-start"):
            contents_start = el
            break
    if contents_start is None:
        return svg_text

    contents_id = (contents_start.get("id") or "").strip()
    existing = None
    for child in list(contents_start):
        if _svg_local_tag(child.tag) == "rect" and (child.get("id") or "") == "boundary":
            existing = child
            break

    if existing is not None:
        kids = list(contents_start)
        if kids and kids[0] is existing:
            return svg_text
        span = find_svg_element_span(svg_text, "boundary")
        if span is None or not contents_id:
            return svg_text
        start, _open_end, _close_start, end = span
        rect_xml = svg_text[start:end]
        without = svg_text[:start] + svg_text[end:]
        moved = insert_after_svg_element_open(without, contents_id, rect_xml)
        return without if moved is None else moved

    if not contents_id:
        return svg_text
    inserted = insert_after_svg_element_open(svg_text, contents_id, _BOUNDARY_RECT_MARKUP)
    return svg_text if inserted is None else inserted


def _refdes_from_device_group(g_el):
    rid = (g_el.get("id") or "").strip()
    if rid:
        return rid.strip("?")
    return ""


def _svg_build_parent_map(root):
    return {c: p for p in root.iter() for c in list(p)}


_SVG_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _svg_multiply(m1, m2):
    """Return SVG matrix ``m1 * m2`` with packing ``(a, b, c, d, e, f)``."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,  # a
        b1 * a2 + d1 * b2,  # b
        a1 * c2 + c1 * d2,  # c
        b1 * c2 + d1 * d2,  # d
        a1 * e2 + c1 * f2 + e1,  # e
        b1 * e2 + d1 * f2 + f1,  # f
    )


def _svg_transform_point(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _svg_parse_transform_attr(s):
    """
    Parse an SVG ``transform`` attribute into ``(a, b, c, d, e, f)``.

    Transform lists are applied right-to-left (``translate(tx,ty) rotate(deg)`` rotates
    about the local origin, then translates). Compose left-to-right with post-multiply.
    """
    if not s or not str(s).strip():
        return _SVG_IDENTITY
    m = _SVG_IDENTITY
    for kind, body in re.findall(
        r"(matrix|translate|scale|rotate)\s*\(([^)]+)\)", str(s), flags=re.I
    ):
        nums = [
            float(x)
            for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", body)
        ]
        kind = kind.lower()
        if kind == "matrix" and len(nums) >= 6:
            t = (nums[0], nums[1], nums[2], nums[3], nums[4], nums[5])
        elif kind == "translate":
            tx = nums[0] if nums else 0.0
            ty = nums[1] if len(nums) > 1 else 0.0
            t = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif kind == "scale":
            sx = nums[0] if nums else 1.0
            sy = nums[1] if len(nums) > 1 else sx
            t = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif kind == "rotate":
            ang = math.radians(nums[0])
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            if len(nums) >= 3:
                # SVG: rotate(a,cx,cy) ≡ translate(cx,cy) rotate(a) translate(-cx,-cy)
                cx, cy = nums[1], nums[2]
                t0 = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
                t1 = (1.0, 0.0, 0.0, 1.0, cx, cy)
                t2 = (1.0, 0.0, 0.0, 1.0, -cx, -cy)
                t = _svg_multiply(t1, _svg_multiply(t0, t2))
            else:
                t = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        else:
            continue
        m = _svg_multiply(m, t)
    return m


def _svg_world_point_for_element(el, lx, ly, parent_map):
    m = _SVG_IDENTITY
    cur = el
    while cur is not None and _svg_local_tag(cur.tag) != "svg":
        tf = cur.get("transform")
        if tf:
            m = _svg_multiply(_svg_parse_transform_attr(tf), m)
        cur = parent_map.get(cur)
    return _svg_transform_point(m, lx, ly)


def _svg_wire_coord_key(x, y):
    return f"{round(float(x))},{round(float(y))}"


def _svg_dist_point_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx * dx + dy * dy < 1e-18:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    qx, qy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - qx, py - qy)


def _svg_is_harness_wire_line(el):
    if _svg_local_tag(el.tag) != "line":
        return False
    cls = (el.get("class") or "").split()
    return "wire" in cls and "harness-wire" in cls and (el.get("id") or "").strip()


def _svg_is_device_harness_connector_circle(el, parent_map=None):
    if _svg_local_tag(el.tag) != "circle":
        return False
    cls = el.get("class") or ""
    if "mating connector" in cls:
        return False
    if "connector" not in cls.split():
        return False
    if parent_map is not None:
        node = el
        while node is not None:
            if "system-diagram-primitive" in (node.get("class") or "").split():
                return False
            node = parent_map.get(node)
    return True


def _svg_device_connector_circles(root, parent_map=None):
    """Device connector circles (not mating, not nested subsystem artwork)."""
    if parent_map is None:
        parent_map = _svg_build_parent_map(root)
    return [
        el
        for el in root.iter()
        if _svg_is_device_harness_connector_circle(el, parent_map)
    ]


# Symbol-editor IDs (see ensureElementId): unique DOM keys, not connector names.
_EDITOR_GENERATED_ELEMENT_ID_RE = re.compile(r"^sde-\d+-[A-Za-z0-9]+$")


def _is_editor_generated_element_id(cid):
    return bool(cid) and bool(_EDITOR_GENERATED_ELEMENT_ID_RE.match(str(cid).strip()))


def device_connector_identity(el):
    """Signals-list connector name for a symbol pin.

    ``data-pin-name`` is canonical. ``id`` is only a fallback when it is a real
    connector name, not a symbol-editor ``sde-…`` key.
    """
    pin = (el.get("data-pin-name") or "").strip()
    if pin:
        return pin
    cid = (el.get("id") or "").strip()
    if cid and not _is_editor_generated_element_id(cid):
        return cid
    return ""


def apply_missing_device_connector_ids(circles):
    """Fill a missing ``data-pin-name`` from a real connector ``id``, or the reverse.

    Editor-generated ``sde-…`` ids are not copied onto ``data-pin-name``.
    Returns True if any circle was changed.
    """
    changed = False
    for el in circles:
        pin = (el.get("data-pin-name") or "").strip()
        cid = (el.get("id") or "").strip()
        if pin and not cid:
            el.set("id", pin)
            changed = True
        elif cid and not pin and not _is_editor_generated_element_id(cid):
            el.set("data-pin-name", cid)
            changed = True
    return changed


def device_connector_id_errors(circles, required_ids=None):
    """Human-readable errors for symbol pins vs signals-list ``connector_id``.

    Pin identity is ``data-pin-name`` (see ``device_connector_identity``).
    Names must be unique within the device and match ``required_ids`` when given.
    """
    required = {str(x).strip() for x in (required_ids or []) if str(x).strip()}
    errors = []
    seen = set()
    have = []
    for el in circles:
        identity = device_connector_identity(el)
        if not identity:
            errors.append("connector has no data-pin-name")
            continue
        if identity in seen:
            errors.append(f"duplicate connector id {identity!r} within device")
        seen.add(identity)
        have.append(identity)
    have_set = set(have)
    if required:
        missing = required - have_set
        extra = have_set - required
        if missing:
            errors.append(
                "signals list connector(s) missing from symbol: "
                + ", ".join(sorted(missing))
            )
        if extra:
            errors.append(
                "symbol connector(s) not in signals list: "
                + ", ".join(sorted(extra))
            )
    return errors


def _svg_placed_component_root_g_for_descendant(el, parent_map):
    while el is not None:
        par = parent_map.get(el)
        if par is not None and (par.get("id") or "") in _SVG_DEVICES_PARENT_GROUP_IDS:
            return el
        el = par
    return None


def _build_harness_network_graph_from_block_diagram(root, parent_map):
    """
    Build a ``draw_segments_across_paths`` graph from harness ``<line>`` elements and
    device harness connector circles.
    """
    harness_lines = []
    for el in root.iter():
        if not _svg_is_harness_wire_line(el):
            continue
        wid = el.get("id").strip()
        (wx1, wy1) = _svg_world_point_for_element(
            el, float(el.get("x1", 0)), float(el.get("y1", 0)), parent_map
        )
        (wx2, wy2) = _svg_world_point_for_element(
            el, float(el.get("x2", 0)), float(el.get("y2", 0)), parent_map
        )
        harness_lines.append(
            {"id": wid, "wx1": wx1, "wy1": wy1, "wx2": wx2, "wy2": wy2}
        )

    device_connectors = []
    for el in root.iter():
        if not _svg_is_device_harness_connector_circle(el, parent_map):
            continue
        try:
            cx = float(el.get("cx", 0))
            cy = float(el.get("cy", 0))
        except (TypeError, ValueError):
            continue
        wx, wy = _svg_world_point_for_element(el, cx, cy, parent_map)
        pin_name = device_connector_identity(el)
        root_g = _svg_placed_component_root_g_for_descendant(el, parent_map)
        refdes = _refdes_from_device_group(root_g) if root_g is not None else ""
        device_connectors.append(
            {"wx": wx, "wy": wy, "device_refdes": refdes, "device_connector": pin_name}
        )

    mate_tol = 6.0

    def nearest_device_connector(wx, wy):
        best = None
        best_d = float("inf")
        for c in device_connectors:
            d = ((wx - c["wx"]) ** 2 + (wy - c["wy"]) ** 2) ** 0.5
            if d <= mate_tol and d < best_d:
                best_d = d
                best = c
        return best

    nodes = {}
    segments = {}
    location_to_node = {}
    junction_counter = 0

    def node_for_world_point(wx, wy):
        nonlocal junction_counter
        match = nearest_device_connector(wx, wy)
        if match and match.get("device_refdes") and match.get("device_connector"):
            nid = f"{match['device_refdes']}.{match['device_connector']}"
            if nid not in nodes:
                nodes[nid] = {
                    "x": round(float(match["wx"]), 5),
                    "y": round(float(match["wy"]), 5),
                }
            return nid
        loc_key = _svg_wire_coord_key(wx, wy)
        if loc_key not in location_to_node:
            jid = f"wirejunction-{junction_counter}"
            junction_counter += 1
            location_to_node[loc_key] = jid
            nodes[jid] = {"x": round(float(wx), 5), "y": round(float(wy), 5)}
        return location_to_node[loc_key]

    for h in harness_lines:
        wx1, wy1, wx2, wy2 = h["wx1"], h["wy1"], h["wx2"], h["wy2"]
        if abs(wx1 - wx2) < 1e-9 and abs(wy1 - wy2) < 1e-9:
            continue
        na = node_for_world_point(wx1, wy1)
        nb = node_for_world_point(wx2, wy2)
        segments[h["id"]] = {"node_at_end_a": na, "node_at_end_b": nb}

    return {"nodes": nodes, "segments": segments}


def strip_all_block_diagram_derived_trace_layers(svg_text):
    t = _BLOCK_DIAGRAM_OVERLAY_HTML_COMMENT_RE.sub("", svg_text)
    return strip_svg_element_by_id(t, BD_APPLIED_TRACES_GROUP_ID)


def _indent_block_diagram_trace_inner_markup(markup, inner_spaces):
    if not (markup or "").strip():
        return ""
    base = int(inner_spaces or 0)
    fragment = str(markup).strip()
    wrapped = f"<root>{fragment}</root>"
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        return "\n".join(
            (" " * base) + ln.strip() for ln in fragment.splitlines() if ln.strip()
        )
    try:
        ET.indent(root, space="  ")
    except Exception:
        pass

    out = []
    for child in list(root):
        serialized = ET.tostring(child, encoding="unicode")
        for ln in serialized.splitlines():
            s = ln.rstrip()
            if s:
                out.append((" " * base) + s)
    return "\n".join(out)


def _applied_traces_block(channel_inner_markup, circuit_inner_markup):
    ch_raw = (channel_inner_markup or "").strip()
    cir_raw = (circuit_inner_markup or "").strip()
    if not ch_raw and not cir_raw:
        return ""

    ch_body = (
        _indent_block_diagram_trace_inner_markup(channel_inner_markup or "", 4)
        if ch_raw
        else ""
    )
    cir_body = (
        _indent_block_diagram_trace_inner_markup(circuit_inner_markup or "", 4)
        if cir_raw
        else ""
    )

    inner_lines = [
        f'<g id="{BD_APPLIED_TRACES_GROUP_ID}" data-harnice-derived="1">',
        f'  <g id="{BD_CHANNEL_TRACES_GROUP_ID}">',
    ]
    if ch_body:
        inner_lines.extend(ch_body.split("\n"))
    inner_lines.append("  </g>")
    inner_lines.append(f'  <g id="{BD_CIRCUIT_TRACES_GROUP_ID}">')
    if cir_body:
        inner_lines.extend(cir_body.split("\n"))
    inner_lines.append("  </g>")
    inner_lines.append("</g>")
    block_core = "\n".join(inner_lines) + "\n"

    outer_lines = []
    for line in block_core.rstrip("\n").split("\n"):
        outer_lines.append(("  " + line) if line.strip() else "")
    return "\n".join(outer_lines) + "\n"


def replace_block_diagram_applied_traces(svg_text, channel_inner_markup, circuit_inner_markup):
    block = _applied_traces_block(channel_inner_markup, circuit_inner_markup)
    existing = find_svg_element_span(svg_text, BD_APPLIED_TRACES_GROUP_ID)
    if existing is not None:
        old_outer = svg_text[existing[0] : existing[3]]
        if block and svg_markup_equivalent(old_outer, block.strip()):
            return svg_text
        if not block:
            return strip_svg_element_by_id(svg_text, BD_APPLIED_TRACES_GROUP_ID)
        return svg_text[: existing[0]] + block + svg_text[existing[3] :]

    if not block:
        return svg_text

    m = re.search(
        r"</(?:[A-Za-z_][\w.\-]*:)?svg>\s*$",
        svg_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        raise ValueError("SVG text has no closing </svg> tag.")
    pos = m.start()
    return svg_text[:pos] + block + svg_text[pos:]
