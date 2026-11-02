"""System subsystem_symbol macros: build-instruction discovery, SVG I/O, primitives."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from harnice import cli, fileio, state
from harnice.utils import block_diagram_utils

MACRO_MPN = "subsystem_symbol"
DEFAULT_SCALE = 0.1

# Same checkboxes as the block-diagram sheet. True draws the layer.
DIAGRAM_SHOW_FLAGS = (
    "show_boundary",
    "show_devices",
    "show_subsystems",
    "show_harnesses",
    "show_mating_connectors",
    "show_external_interface_flags",
    "show_harness_labels",
    "show_channel_traces",
    "show_circuit_traces",
)


def _literal(node):
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _literal(node.operand)
        if isinstance(v, (int, float)):
            return -v
    return None


def _call_func_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def parse_subsystem_symbol_calls(source: str) -> list[dict]:
    """Return ``[{artifact_id, scale}, ...]`` in source order from ``run_macro`` calls."""
    if not source or not str(source).strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    seen = set()

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if _call_func_name(node.func) == "run_macro":
                args = list(node.args)
                keywords = {k.arg: k.value for k in node.keywords if k.arg}
                mpn = _literal(args[0]) if args else _literal(
                    keywords.get("macro_part_number")
                )
                if mpn == MACRO_MPN:
                    artifact_id = None
                    if "artifact_id" in keywords:
                        artifact_id = _literal(keywords["artifact_id"])
                    elif len(args) >= 4:
                        artifact_id = _literal(args[3])
                    artifact_id = str(artifact_id or "").strip()
                    if artifact_id and artifact_id not in seen:
                        scale, explicit = DEFAULT_SCALE, False
                        if "scale" in keywords:
                            parsed = _literal(keywords["scale"])
                            if isinstance(parsed, (int, float)) and not isinstance(
                                parsed, bool
                            ):
                                scale, explicit = float(parsed), True
                        seen.add(artifact_id)
                        out.append(
                            {
                                "artifact_id": artifact_id,
                                "scale": scale,
                                "scale_explicit": explicit,
                            }
                        )
            self.generic_visit(node)

    _Visitor().visit(tree)
    return out


def is_subsystem_symbol_instance(
    item_type: str, instance_name: str, inst_dir: str | None = None
) -> bool:
    if (item_type or "").strip().lower() != "macro":
        return False
    if inst_dir and os.path.isfile(os.path.join(inst_dir, "subsystem_symbol.py")):
        return True
    name = (instance_name or "").strip()
    return any(c.get("artifact_id") == name for c in list_artifacts())


def list_artifacts() -> list[dict]:
    """Artifacts declared by ``subsystem_symbol`` ``run_macro`` calls in build instructions."""
    path = None
    try:
        path = fileio.path("build instructions")
    except Exception:
        path = None
    source = ""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            source = f.read()
    return parse_subsystem_symbol_calls(source)


def _build_instruction_calls_in_dir(root: str) -> list[dict]:
    if not root or not os.path.isdir(root):
        return []
    try:
        names = os.listdir(root)
    except OSError:
        return []
    for name in names:
        if name == "build.py":
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as f:
                    return parse_subsystem_symbol_calls(f.read())
            except OSError:
                return []
    return []


def find_system_symbol_svg_paths(root: str) -> dict[str, str]:
    """Map ``artifact_id`` → SVG path under a system project type or library revision folder."""
    found: dict[str, str] = {}
    if not root or not os.path.isdir(root):
        return found
    for dirpath, _dirnames, filenames in os.walk(root):
        parts = Path(dirpath).parts
        try:
            mi = parts.index("macro")
            artifact_id = parts[mi + 1]
        except (ValueError, IndexError):
            continue
        if not artifact_id:
            continue
        for name in filenames:
            if name == "symbol.svg":
                found[artifact_id] = os.path.join(dirpath, name)
                break
    return found


def list_system_symbols_in_directory(root: str) -> list[dict]:
    """Symbols available on a pulled or library system: ``[{artifact_id, scale, path}, ...]``.

    ``path`` is an absolute SVG path when the file exists (typically under
    ``instance_data/macro/{artifact_id}/`` in the library revision).
    """
    calls = _build_instruction_calls_in_dir(root)
    if not calls:
        lib_used = os.path.join(root, fileio.LIBRARY_USED_DIR)
        if os.path.isdir(lib_used):
            try:
                for rev in sorted(os.listdir(lib_used)):
                    rev_dir = os.path.join(lib_used, rev)
                    if os.path.isdir(rev_dir):
                        calls = _build_instruction_calls_in_dir(rev_dir)
                        if calls:
                            break
            except OSError:
                calls = []
    svgs = find_system_symbol_svg_paths(root)
    seen = set()
    out = []
    for call in calls:
        aid = str(call.get("artifact_id") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(
            {
                "artifact_id": aid,
                "scale": call.get("scale", DEFAULT_SCALE),
                "path": svgs.get(aid),
            }
        )
    for aid in sorted(svgs):
        if aid in seen:
            continue
        out.append({"artifact_id": aid, "scale": DEFAULT_SCALE, "path": svgs[aid]})
    return out


def _base_directory(artifact_id: str) -> str:
    return os.path.join("instance_data", "macro", artifact_id)


def _structure(artifact_id: str) -> dict:
    return {
        "symbol.svg": "subsystem symbol",
        "params.json": "params",
    }


def symbol_svg_path(artifact_id: str) -> str:
    return fileio.path(
        "subsystem symbol",
        structure_dict=_structure(artifact_id),
        base_directory=_base_directory(artifact_id),
    )


def params_path(artifact_id: str) -> str:
    return fileio.path(
        "params",
        structure_dict=_structure(artifact_id),
        base_directory=_base_directory(artifact_id),
    )


def contents_start_id(artifact_id: str) -> str:
    return f"{state.partnumber('pn-rev')}-{artifact_id}-contents-start"


def blank_symbol_svg(artifact_id: str) -> str:
    start_id = contents_start_id(artifact_id)
    end_id = start_id.replace("-contents-start", "-contents-end")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">\n'
        f'  <g id="{start_id}" class="component device"></g>\n'
        f'  <g id="{end_id}"></g>\n'
        "</svg>\n"
    )


def unique_connector_ids_from_icd() -> list[str]:
    """Unique ``connector_id`` values from the system ICD, sorted."""
    try:
        rows = fileio.read_tsv("icd")
    except (FileNotFoundError, TypeError, OSError):
        return []
    seen = set()
    ids = []
    for row in rows:
        connector_id = (row.get("connector_id") or "").strip()
        if not connector_id or connector_id in seen:
            continue
        seen.add(connector_id)
        ids.append(connector_id)
    return sorted(ids)


def _xml_attr(value: str) -> str:
    return xml_escape(str(value), {"\"": "&quot;", "'": "&apos;"})


def _contents_element(root, artifact_id: str):
    start_id = contents_start_id(artifact_id)
    for el in root.iter():
        if (el.get("id") or "").strip() == start_id:
            return el
    for el in root.iter():
        eid = (el.get("id") or "").strip()
        if eid.endswith("-contents-start"):
            return el
    return None


def _is_under_system_diagram_primitive(el, parent_map) -> bool:
    cur = el
    while cur is not None:
        classes = (cur.get("class") or "").split()
        if "system-diagram-primitive" in classes:
            return True
        cur = parent_map.get(cur)
    return False


def _top_level_connector_circles(contents):
    parent_map = {c: p for p in contents.iter() for c in list(p)}
    parent_map[contents] = None
    out = []
    for el in contents.iter():
        if block_diagram_utils._svg_local_tag(el.tag) != "circle":
            continue
        if "connector" not in (el.get("class") or "").split():
            continue
        if _is_under_system_diagram_primitive(el, parent_map):
            continue
        out.append(el)
    return out


def _existing_pin_state(svg_text: str, artifact_id: str) -> tuple[set[str], float]:
    names: set[str] = set()
    last_y = 20.0
    try:
        tree = block_diagram_utils._parse_block_diagram_svg_string(svg_text)
    except Exception:
        return names, last_y
    contents = _contents_element(tree.getroot(), artifact_id)
    if contents is None:
        return names, last_y
    for circle in _top_level_connector_circles(contents):
        name = block_diagram_utils.device_connector_identity(circle)
        if name:
            names.add(name)
        try:
            last_y = max(last_y, float(circle.get("cy") or 0))
        except (TypeError, ValueError):
            pass
    return names, last_y


def _insert_pins_into_svg(svg_text: str, artifact_id: str, pin_lines: list[str]) -> str:
    contents_id = contents_start_id(artifact_id)
    start_pattern = f'id="{contents_id}"'
    idx = svg_text.find(start_pattern)
    if idx == -1:
        m = re.search(r'id="([^"]*-contents-start)"', svg_text)
        if not m:
            raise ValueError("Block diagram symbol SVG has no contents-start group")
        start_pattern = f'id="{m.group(1)}"'
        idx = svg_text.find(start_pattern)
    gt_pos = svg_text.find(">", idx)
    slash_gt = svg_text.find("/>", idx)
    pin_block = "\n  " + "\n    ".join(pin_lines) + "\n  "
    if slash_gt != -1 and slash_gt < gt_pos:
        return (
            svg_text[:slash_gt]
            + ">\n  "
            + pin_block
            + "</g>"
            + svg_text[slash_gt + 2 :]
        )
    insert_pos = gt_pos + 1
    return svg_text[:insert_pos] + pin_block + svg_text[insert_pos:]


def sync_connector_pins(artifact_id: str, *, only_if_none: bool = False) -> None:
    """Append one pin per unique ICD connector that is not already on the symbol.

    The ICD is written after build instructions, so a macro run during build uses
    the previous build's ICD. After external-interface changes, build twice.
    """
    path = symbol_svg_path(artifact_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(blank_symbol_svg(artifact_id))
    required = unique_connector_ids_from_icd()
    if not required:
        return
    with open(path, encoding="utf-8") as f:
        svg_text = f.read()
    existing, last_y = _existing_pin_state(svg_text, artifact_id)
    if only_if_none and existing:
        return
    missing = [name for name in required if name not in existing]
    if not missing:
        return
    next_y = last_y + 10
    pin_lines = []
    for connector_id in missing:
        pin_lines.append(
            f'<circle class="connector" data-pin-name="{_xml_attr(connector_id)}" '
            f'id="{_xml_attr(connector_id)}" cx="50" cy="{next_y:g}" r="0.1" fill="black" />'
        )
        next_y += 10
    updated = _insert_pins_into_svg(svg_text, artifact_id, pin_lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
        if not updated.endswith("\n"):
            f.write("\n")


_PRIMITIVE_OPEN_RE = re.compile(
    r"<g\b[^>]*\bclass=\"[^\"]*\bsystem-diagram-primitive\b[^\"]*\"[^>]*>",
    re.IGNORECASE,
)
_TRANSFORM_ATTR_RE = re.compile(r"""transform=(["'])(.*?)\1""", re.IGNORECASE)
_SCALE_CALL_RE = re.compile(
    r"scale\s*\(\s*[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"
    r"(?:\s*,\s*[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)?\s*\)",
    re.IGNORECASE,
)


def _format_scale(scale: float) -> str:
    return f"{float(scale):.6g}"


def _transform_with_scale(transform: str, scale: float) -> str:
    piece = f"scale({_format_scale(scale)})"
    if _SCALE_CALL_RE.search(transform):
        return _SCALE_CALL_RE.sub(piece, transform, count=1)
    text = (transform or "").strip()
    return f"{text} {piece}".strip() if text else piece


def _rewrite_primitive_scales(svg_text: str, scale: float) -> str:
    """Set the uniform scale on each system-diagram primitive. Leave translate in place."""

    def repl(match):
        tag = match.group(0)
        found = _TRANSFORM_ATTR_RE.search(tag)
        if not found:
            return tag[:-1] + f' transform="scale({_format_scale(scale)})">'
        updated = _transform_with_scale(found.group(2), scale)
        if updated == found.group(2):
            return tag
        return tag[: found.start(2)] + updated + tag[found.end(2) :]

    return _PRIMITIVE_OPEN_RE.sub(repl, svg_text)


def refresh_system_diagram_primitives(artifact_id: str) -> None:
    """Replace each dropped system-diagram primitive with the current block diagram.

    The primitive stays where it was drawn. Child ids keep the prefix already
    on that primitive, so a second build does not rename a diagram that has
    not changed. Show flags in params.json hide layers with ``display="none"``.
    A primitive nested inside another one is part of the copied diagram, not a
    second copy to refresh. Symbols with no diagram primitive are left alone.
    """
    artifact_id = (artifact_id or "").strip()
    if not artifact_id:
        return
    path = symbol_svg_path(artifact_id)
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        original = f.read()

    # A primitive needs an id so its children can be replaced in the file text.
    next_id = 0

    def give_missing_id(match):
        nonlocal next_id
        tag = match.group(0)
        if re.search(r"\bid\s*=", tag, flags=re.IGNORECASE):
            return tag
        next_id += 1
        insert = ' id="system-diagram-primitive-%s"' % next_id
        if tag.endswith("/>"):
            return tag[:-2] + insert + "/>"
        return tag[:-1] + insert + ">"

    working = _PRIMITIVE_OPEN_RE.sub(give_missing_id, original)
    try:
        root = block_diagram_utils._parse_block_diagram_svg_string(working).getroot()
    except ET.ParseError as exc:
        cli.warn(
            "%s: could not read the subsystem symbol (%s: %s)"
            % (artifact_id, type(exc).__name__, exc)
        )
        return

    parent_map = {child: parent for parent in root.iter() for child in list(parent)}
    parent_map[root] = None
    primitives = []
    for el in root.iter():
        classes = (el.get("class") or "").split()
        if "system-diagram-primitive" not in classes:
            continue
        if _is_under_system_diagram_primitive(parent_map.get(el), parent_map):
            continue
        primitives.append(el)
    if not primitives:
        return

    try:
        inner = system_diagram_primitive_inner_svg(artifact_id)
        wrapped = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg">' + inner + "</svg>\n"
        )
        template = block_diagram_utils._parse_block_diagram_svg_string(wrapped).getroot()
    except (OSError, ET.ParseError, ValueError) as exc:
        cli.warn(
            "%s: could not copy the block diagram into the subsystem symbol (%s: %s)"
            % (artifact_id, type(exc).__name__, exc)
        )
        return

    prefix_re = re.compile(r"^(sdp-[0-9a-z]+-)")
    fresh_n = 0

    def child_prefix(primitive):
        nonlocal fresh_n
        for el in primitive.iter():
            if el is primitive:
                continue
            match = prefix_re.match(el.get("id") or "")
            if match:
                return match.group(1)
        import time

        fresh_n += 1
        return "sdp-%d-" % (int(time.time() * 1000) + fresh_n)

    def apply_prefix(node, prefix):
        id_map = {}
        for el in node.iter():
            old = (el.get("id") or "").strip()
            if not old:
                continue
            id_map[old] = prefix + old
            el.set("id", prefix + old)
        for el in node.iter():
            for key, value in list(el.attrib.items()):
                if not value:
                    continue
                updated = value
                if value in id_map:
                    updated = id_map[value]
                elif value[:1] == "#" and value[1:] in id_map:
                    updated = "#" + id_map[value[1:]]
                elif "url(#" in value:
                    updated = value
                    for old in sorted(id_map, key=len, reverse=True):
                        updated = updated.replace(
                            "url(#%s)" % old, "url(#%s)" % id_map[old]
                        )
                if updated != value:
                    el.set(key, updated)

    updated = 0
    for primitive in primitives:
        pid = (primitive.get("id") or "").strip()
        if not pid:
            continue
        scratch = block_diagram_utils.clone_svg_element(template)
        apply_prefix(scratch, child_prefix(primitive))
        same = block_diagram_utils.svg_children_signature(
            primitive
        ) == block_diagram_utils.svg_children_signature(scratch)
        if same:
            continue
        new_inner = block_diagram_utils.serialize_svg_element_children(scratch)
        if new_inner and not new_inner.endswith("\n"):
            new_inner += "\n"
        if new_inner:
            new_inner = "\n" + new_inner
        spliced = block_diagram_utils.replace_svg_element_inner_by_id(
            working, pid, new_inner
        )
        if spliced is None:
            cli.warn(
                "%s: could not update system-diagram primitive %s" % (artifact_id, pid)
            )
            continue
        working = spliced
        updated += 1
    if working == original:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(working)
        if not working.endswith("\n"):
            f.write("\n")
    if updated:
        print(
            "Copied the block diagram into %s system-diagram primitive(s) on %s."
            % (updated, artifact_id)
        )


def apply_declared_diagram_scale(artifact_id: str) -> None:
    """Write the build-instruction scale onto the symbol's diagram primitive.

    ``scale`` on the ``subsystem_symbol`` ``run_macro`` call is the source of
    truth. An existing primitive keeps its
    position; only its scale changes. Symbols with no numeric scale argument
    are left alone.
    """
    row = next(
        (item for item in list_artifacts() if item.get("artifact_id") == artifact_id),
        None,
    )
    if not row or not row.get("scale_explicit"):
        return
    try:
        scale = float(row.get("scale"))
    except (TypeError, ValueError):
        return
    params = params_path(artifact_id)
    os.makedirs(os.path.dirname(params), exist_ok=True)
    data = {}
    if os.path.isfile(params):
        try:
            with open(params, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    data["scale"] = scale
    with open(params, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    path = symbol_svg_path(artifact_id)
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        svg_text = f.read()
    updated = _rewrite_primitive_scales(svg_text, scale)
    if updated == svg_text:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
        if not updated.endswith("\n"):
            f.write("\n")


def verify_as_device(artifact_id: str, verbose: bool = True) -> None:
    """Run device signals-list checks and warn on symbol-pin mismatches vs the ICD.

    Uses the ICD already on disk (from the previous build). Missing ICD skips
    verification. Extra or missing top-level symbol pins print a warning instead
    of raising (unlike device ``_validate_svg_symbol``). Missing pins are still
    appended by ``sync_connector_pins``.
    """
    from harnice.project_types import device

    try:
        icd_path = fileio.path("icd")
    except (FileNotFoundError, TypeError, OSError):
        icd_path = None
    if not icd_path or not os.path.isfile(icd_path):
        if verbose:
            print(
                "No ICD from a previous build; skipping device-style verification "
                "(build twice after external-interface flags exist)."
            )
        sync_connector_pins(artifact_id)
        refresh_system_diagram_primitives(artifact_id)
        apply_declared_diagram_scale(artifact_id)
        return
    # ========================================================================
    # TODO: turn ICD verification back on
    # ========================================================================
    # device._validate_signals_list(verbose=verbose, signals_path=icd_path)
    path = symbol_svg_path(artifact_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(blank_symbol_svg(artifact_id))
    with open(path, encoding="utf-8") as f:
        svg_text = f.read()
    existing, _ = _existing_pin_state(svg_text, artifact_id)
    required = set(unique_connector_ids_from_icd())
    extra = existing - required
    missing = required - existing
    if extra:
        cli.warn(
            "The following pin(s) exist in SVG symbol but not in Signals List: "
            + ", ".join(sorted(extra))
        )
    if missing:
        cli.warn(
            "The following pin(s) exist in Signals List but not in SVG symbol: "
            + ", ".join(sorted(missing))
        )
    sync_connector_pins(artifact_id)
    refresh_system_diagram_primitives(artifact_id)
    apply_declared_diagram_scale(artifact_id)


def ensure_symbol_svg(artifact_id: str) -> str:
    """Create a blank symbol SVG if missing. Returns the file path."""
    path = symbol_svg_path(artifact_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    created = not os.path.isfile(path) or os.path.getsize(path) == 0
    if created:
        with open(path, "w", encoding="utf-8") as f:
            f.write(blank_symbol_svg(artifact_id))
    params = params_path(artifact_id)
    if not os.path.isfile(params):
        with open(params, "w", encoding="utf-8") as f:
            json.dump({"scale": DEFAULT_SCALE}, f, indent=2)
            f.write("\n")
    sync_connector_pins(artifact_id, only_if_none=not created)
    return path


def read_symbol_svg(artifact_id: str) -> str:
    path = ensure_symbol_svg(artifact_id)
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_symbol_svg(artifact_id: str, svg_text: str) -> None:
    path = symbol_svg_path(artifact_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_text)
        if not svg_text.endswith("\n"):
            f.write("\n")


def scale_for_artifact(artifact_id: str) -> float:
    for row in list_artifacts():
        if row.get("artifact_id") == artifact_id:
            try:
                return float(row.get("scale") or DEFAULT_SCALE)
            except (TypeError, ValueError):
                return DEFAULT_SCALE
    path = params_path(artifact_id)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("scale") or DEFAULT_SCALE)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return DEFAULT_SCALE


def system_diagram_primitive_inner_svg(artifact_id=None) -> str:
    """Inner markup of the system block diagram for a subsystem symbol.

    Reads ``show_*`` from that symbol's params.json when ``artifact_id`` is
    set. A missing flag shows the layer. False sets ``display="none"`` on it,
    the same as the block-diagram sheet.
    """
    show = {}
    for name in DIAGRAM_SHOW_FLAGS:
        show[name] = True
    if artifact_id:
        params = params_path(artifact_id)
        if os.path.isfile(params):
            try:
                with open(params, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict):
                for name in DIAGRAM_SHOW_FLAGS:
                    if isinstance(data.get(name), bool):
                        show[name] = data[name]

    bd_path = fileio.path("block diagram")
    if not bd_path or not os.path.isfile(bd_path):
        raise FileNotFoundError("System block diagram not found")
    tree = block_diagram_utils._parse_block_diagram_svg_file(bd_path)
    root = tree.getroot()
    contents = None
    for el in root.iter():
        eid = (el.get("id") or "").strip()
        if eid.endswith("-contents-start"):
            contents = el
            break
    if contents is None:
        raise ValueError("System block diagram has no contents-start group")
    from harnice.utils import system_utils

    system_utils.apply_component_symbol_fstrings(contents)

    nodes = list(contents)
    parent_map = {child: parent for parent in root.iter() for child in list(parent)}
    parent_map[root] = None
    for el in root.iter():
        if (el.get("id") or "").strip() != "applied-traces":
            continue
        cur = el
        inside = False
        while cur is not None:
            if cur is contents:
                inside = True
                break
            cur = parent_map.get(cur)
        if not inside:
            nodes.append(el)
        break

    hide_ids = {
        "boundary": "show_boundary",
        "harnesses": "show_harnesses",
        "mating-connectors": "show_mating_connectors",
        "external-interface-flags": "show_external_interface_flags",
        "harness-segment-refdes-labels": "show_harness_labels",
        "channel_traces": "show_channel_traces",
        "circuit_traces": "show_circuit_traces",
    }
    for node in nodes:
        for el in node.iter():
            flag = hide_ids.get((el.get("id") or "").strip())
            if flag and not show[flag]:
                el.set("display", "none")
        if (node.get("id") or "").strip() != "devices":
            continue
        if show["show_devices"] and show["show_subsystems"]:
            continue
        for child in list(node):
            classes = (child.get("class") or "").split()
            if "subsystem" in classes:
                if not show["show_subsystems"]:
                    child.set("display", "none")
            elif "device" in classes and not show["show_devices"]:
                child.set("display", "none")

    chunks = []
    for child in nodes:
        chunks.append(
            block_diagram_utils._svg_fragment_preserve_bound_prefixes(
                ET.tostring(child, encoding="unicode")
            )
        )
    return "".join(chunks)
