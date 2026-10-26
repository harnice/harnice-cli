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
MACRO_LIB_SUBPATH = "library/macros/system_artifacts"
MACRO_LIB_REPO = "https://github.com/harnice/harnice-general-library"
DEFAULT_SCALE = 0.1
DEFAULT_ARTIFACT_ID = "subsystem-symbol-1"

_SKIP_PRIMITIVE_CHILD_IDS = frozenset(
    {
        block_diagram_utils.BD_APPLIED_TRACES_GROUP_ID,
        block_diagram_utils.BD_CHANNEL_TRACES_GROUP_ID,
        block_diagram_utils.BD_CIRCUIT_TRACES_GROUP_ID,
    }
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
    with open(params, "w", encoding="utf-8") as f:
        json.dump({"scale": scale}, f, indent=2)
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


def _skip_primitive_child(el) -> bool:
    cid = (el.get("id") or "").strip()
    if cid in _SKIP_PRIMITIVE_CHILD_IDS:
        return True
    if cid == "boundary":
        return True
    classes = (el.get("class") or "").split()
    if "system-boundary" in classes:
        return True
    return False


def _set_svg_text_content(el, value: str) -> None:
    value = "" if value is None else str(value)
    current = "".join(el.itertext()).strip() if el is not None else ""
    if current == value.strip():
        return
    tspans = [
        c for c in list(el) if block_diagram_utils._svg_local_tag(c.tag) == "tspan"
    ]
    if tspans:
        first = tspans[0]
        first.text = value
        first.tail = None
        for extra in tspans[1:]:
            el.remove(extra)
        for sub in list(first):
            first.remove(sub)
        el.text = None
        return
    el.text = value
    for child in list(el):
        if block_diagram_utils._svg_local_tag(child.tag) == "tspan":
            el.remove(child)


def _format_config_display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value)
    return str(value)


def _patch_component_attribute_texts(root) -> None:
    """Bake instance REFDES (and configuration values) into attribute-text nodes."""
    local = block_diagram_utils._svg_local_tag
    for g in root.iter():
        if local(g.tag) != "g":
            continue
        classes = set((g.get("class") or "").split())
        if "component" not in classes:
            continue
        if "device" not in classes:
            continue
        gid = (g.get("id") or "").strip().strip("?")
        if not gid or gid.endswith("-contents-start") or gid.endswith("-contents-end"):
            continue
        config = {}
        for child in list(g):
            if local(child.tag) != "configuration":
                continue
            raw = "".join(child.itertext()).strip()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                config = parsed
            break
        for node in g.iter():
            if local(node.tag) not in ("text", "tspan"):
                continue
            name = (node.get("data-attribute-name") or "").strip()
            if not name:
                continue
            if name == "REFDES":
                _set_svg_text_content(node, gid)
            elif name in config:
                _set_svg_text_content(node, _format_config_display(config[name]))


def system_diagram_primitive_inner_svg() -> str:
    """Inner markup of the system block diagram contents, without trace overlays."""
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
    _patch_component_attribute_texts(contents)
    chunks = []
    for child in list(contents):
        if _skip_primitive_child(child):
            continue
        chunks.append(
            block_diagram_utils._svg_fragment_preserve_bound_prefixes(
                ET.tostring(child, encoding="unicode")
            )
        )
    return "".join(chunks)
