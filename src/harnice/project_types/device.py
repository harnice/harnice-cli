import os
import re
import tempfile
import json
import xml.etree.ElementTree as ET

from pathlib import Path

from harnice import fileio, state
from harnice import build_sandbox
from harnice.lists import library_history, signals_list
from harnice.utils import block_diagram_utils, build_utils

def _import_yaml():
    """PyYAML, or a clear stop when a configuration file actually has fields."""
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "Reading this device's config.yaml needs PyYAML. "
            "An empty configuration file does not."
        ) from exc
    return yaml


def _yaml_is_blank(raw):
    """True when every line is empty or a comment, so PyYAML is unnecessary."""
    for line in raw.splitlines():
        if line.split("#", 1)[0].strip():
            return False
    return True


default_desc = "DEVICE, FUNCTION, ATTRIBUTES, etc."

button_color = "#d376f5"

def file_structure():
    return {
        "build.py": "build instructions",
        "libhist.tsv": "library history",
        "signals.tsv": "signals list",
        "attributes.json": "attributes",
        "symbol.svg": "block diagram symbol",
        "config.yaml": "configuration setup",
        "body.step": "body",
        "body_images": {},
    }

def generate_structure():
    pass


def _atomic_write_svg(path_str, content_bytes: bytes):
    """Write SVG bytes atomically to avoid corruption from partial writes."""
    path = path_str if isinstance(path_str, str) else str(path_str)
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirpath or ".", suffix=".svg.tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _ensure_svg_symbol_exists():
    """Create a minimal placeholder SVG if the symbol file does not exist."""
    path = fileio.path("block diagram symbol")
    if os.path.exists(path):
        return
    contents_id = f"{state.partnumber('pn-rev')}-contents-start"
    contents_end = contents_id.replace("-contents-start", "-contents-end")
    view_box = "0 0 400 400"
    svg_text = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" data-bbox="{view_box}">
  <g id="{contents_id}" class="component device"></g>
  <g id="{contents_end}"></g>
</svg>
'''
    _atomic_write_svg(path, svg_text.encode("utf-8"))


def _validate_svg_symbol():
    """Ensure SVG symbol exists, has pins matching the signals list, and append any missing pins.

    Each connector circle is identified by ``data-pin-name`` (not the
    symbol-editor ``sde-…`` element ``id``). That name must match a
    signals-list ``connector_id`` and be unique within the symbol. A missing
    ``data-pin-name`` is filled from a real connector ``id`` when present.
    """
    _ensure_svg_symbol_exists()
    path = fileio.path("block diagram symbol")
    svg_text = Path(path).read_text(encoding="utf-8")

    if "<svg" not in svg_text.lower() or "</svg>" not in svg_text.lower():
        os.remove(path)
        _ensure_svg_symbol_exists()
        svg_text = Path(path).read_text(encoding="utf-8")

    required = set(signals_list.unique_connector_ids())
    tree = block_diagram_utils._parse_block_diagram_svg_string(svg_text)
    root = tree.getroot()
    parent_map = block_diagram_utils._svg_build_parent_map(root)
    circles = block_diagram_utils._svg_device_connector_circles(root, parent_map)
    attr_patches = []
    for el in circles:
        pin = (el.get("data-pin-name") or "").strip()
        cid = (el.get("id") or "").strip()
        if pin and not cid:
            attr_patches.append(("data-pin-name", pin, "id", pin))
        elif (
            cid
            and not pin
            and not block_diagram_utils._is_editor_generated_element_id(cid)
        ):
            attr_patches.append(("id", cid, "data-pin-name", cid))
    block_diagram_utils.apply_missing_device_connector_ids(circles)
    id_errors = block_diagram_utils.device_connector_id_errors(circles, required)
    blocking = [
        e
        for e in id_errors
        if not e.startswith("signals list connector(s) missing from symbol")
    ]
    if blocking:
        extra_msg = next(
            (e for e in blocking if e.startswith("symbol connector(s) not in signals list")),
            None,
        )
        if extra_msg:
            extras = extra_msg.split(": ", 1)[-1]
            raise ValueError(
                f"The following pin(s) exist in SVG symbol but not in Signals List: {extras}"
            )
        raise ValueError("; ".join(blocking))

    existing = {
        block_diagram_utils.device_connector_identity(el) for el in circles
    }
    existing.discard("")
    missing = required - existing
    contents = None
    for el in root.iter():
        if (el.get("id") or "") == f"{state.partnumber('pn-rev')}-contents-start":
            contents = el
            break
    if contents is None:
        for el in root.iter():
            if (el.get("id") or "").endswith("-contents-start"):
                contents = el
                break
    if contents is None and missing:
        raise ValueError(
            f'Block diagram symbol SVG must contain a group with id "{state.partnumber("pn-rev")}-contents-start"'
        )

    last_y = 20.0
    for el in circles:
        try:
            last_y = max(last_y, float(el.get("cy") or 0))
        except (TypeError, ValueError):
            pass
    next_y = last_y + 10
    append_parts = []
    for connector_id in sorted(missing):
        cy = f"{next_y:g}"
        circle = ET.Element("circle")
        circle.set("class", "connector")
        circle.set("data-pin-name", connector_id)
        circle.set("id", connector_id)
        circle.set("cx", "50")
        circle.set("cy", cy)
        circle.set("r", "0.1")
        circle.set("fill", "black")
        contents.append(circle)
        append_parts.append(
            f'<circle class="connector" data-pin-name="{connector_id}" '
            f'id="{connector_id}" cx="50" cy="{cy}" r="0.1" fill="black"/>'
        )
        next_y += 10

    if not attr_patches and not append_parts:
        return

    out = svg_text
    surgical = True
    for find_by, find_val, name, value in attr_patches:
        if find_by == "id":
            nxt = block_diagram_utils.add_svg_attribute_by_id(out, find_val, name, value)
        else:
            nxt = block_diagram_utils.add_svg_attribute_by_attr(
                out, find_by, find_val, name, value
            )
        if nxt is None:
            surgical = False
            break
        out = nxt
    if surgical and append_parts:
        contents_id = (contents.get("id") or "").strip()
        nxt = (
            block_diagram_utils.insert_before_svg_element_close(
                out, contents_id, "".join(append_parts)
            )
            if contents_id
            else None
        )
        if nxt is None:
            surgical = False
        else:
            out = nxt

    if not surgical:
        out = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            root, encoding="unicode"
        )
        if not out.endswith("\n"):
            out += "\n"
        out = block_diagram_utils.normalize_block_diagram_svg_ns0_elementtree_artifact(
            out
        )

    if out != svg_text:
        _atomic_write_svg(path, out.encode("utf-8"))


def _validate_attributes_json():
    """Ensure an attributes JSON file exists with default values if missing."""

    default_attributes = {"default_refdes": "DEVICE"}

    attributes_path = fileio.path("attributes")

    # If attributes file does not exist, create it with defaults
    if not os.path.exists(attributes_path):
        with open(attributes_path, "w", encoding="utf-8") as f:
            json.dump(default_attributes, f, indent=4)

    # If it exists, load it and verify required keys
    else:
        with open(attributes_path, "r", encoding="utf-8") as f:
            try:
                attributes = json.load(f)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in attributes file: {attributes_path}")

        updated = False
        for key, value in default_attributes.items():
            if key not in attributes:
                attributes[key] = value
                updated = True

        if updated:
            with open(attributes_path, "w", encoding="utf-8") as f:
                json.dump(attributes, f, indent=4)
            print(f"Updated attributes file with missing defaults at {attributes_path}")


def _validate_signals_list(verbose=True, signals_path=None):
    signals_list.validate(path=signals_path, verbose=verbose)


CONFIG = {
    "valid_types": {
        "text", "textarea", "url", "number",
        "select", "radio", "multiselect", "boolean",
        "scale", "rating", "slider",
        "matrix",
        "ip_addr", "mac_addr", "channel_type",
    },

    "choice_types": {"select", "radio", "multiselect"},

    "valid_formats": {
        "email", "uri", "date", "date-time", "time", "uuid",
        "ipv4", "ipv6", "hostname", "mac", "channel_type",
    },

    "valid_operators": {
        "equals", "not_equals", "contains", "not_contains",
        "greater_than", "less_than", "greater_than_or_equal",
        "less_than_or_equal", "is_empty", "is_not_empty",
        "starts_with", "ends_with",
    },

    # Validation keys allowed per field type (types not listed accept none)
    "allowed_validation_keys": {
        "text": {"minLength", "maxLength", "pattern", "format"},
        "textarea": {"minLength", "maxLength", "pattern", "format"},
        "url": {"format"},
        "number": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
        "select": {},
        "radio": {},
        "multiselect": {"minItems", "maxItems", "uniqueItems"},
        "boolean": {},
        "scale": {"minimum", "maximum"},
        "rating": {"minimum", "maximum"},
        "slider": {"minimum", "maximum", "multipleOf"},
        "matrix": {},
        "ip_addr": {"pattern", "format"},
        "mac_addr": {"format"},
        "channel_type": {"format"},
    },

    # non-validation keys allowed to sit alongside 'validation' rules
    "extra_validation_keys": {"errorMessages", "custom"},
}


def _validate_config_yaml():
    """
    Validate a form-definition YAML file.

    Raises a ValueError describing exactly which line is wrong and why
    the moment the first problem is found. Returns nothing if the file
    is valid.
    """

    # --- helpers (kept local so the module exposes a single function) ---

    def fail(line, message):
        location = f"line {line}" if line is not None else "unknown location"
        raise ValueError(f"Invalid form definition at {location}: {message}")

    def line_of(node):
        # Every mapping loaded below carries a '__line__' key (1-indexed)
        # injected by the custom loader. Falls back to None if unavailable.
        if isinstance(node, dict):
            return node.get("__line__")
        return None

    def make_line_loader():
        class LineLoader(yaml.SafeLoader):
            pass

        def construct_mapping(loader, node, deep=False):
            mapping = yaml.SafeLoader.construct_mapping(loader, node, deep=deep)
            mapping["__line__"] = node.start_mark.line + 1
            return mapping

        LineLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
        )
        return LineLoader

    def option_values(field):
        opts = field.get("options")
        if not isinstance(opts, list):
            return set()
        return {o.get("value") for o in opts if isinstance(o, dict)}

    def validate_options(field, line):
        ftype = field.get("type")
        opts = field.get("options")
        if opts is None:
            fail(line, f"field '{field.get('id')}' has type '{ftype}' which requires an 'options' list")
        if not isinstance(opts, list) or len(opts) == 0:
            fail(line, f"field '{field.get('id')}' has 'options' that must be a non-empty list")

        seen_values = set()
        for opt in opts:
            opt_line = line_of(opt) or line
            if not isinstance(opt, dict):
                fail(opt_line, f"field '{field.get('id')}' has an option entry that is not a mapping with 'value' and 'label'")
            if "value" not in opt:
                fail(opt_line, f"field '{field.get('id')}' has an option missing required key 'value'")
            if opt["value"] in seen_values:
                fail(opt_line, f"field '{field.get('id')}' has a duplicate option value '{opt['value']}'")
            seen_values.add(opt["value"])
            if "label" not in opt:
                fail(opt_line, f"field '{field.get('id')}' has an option missing required key 'label'")

    def validate_validation_block(field, line):
        ftype = field.get("type")
        validation = field["validation"]
        if not isinstance(validation, dict):
            fail(line, f"field '{field.get('id')}' has a 'validation' key that must be a mapping")

        allowed = CONFIG['allowed_validation_keys'].get(ftype, set())
        for key in validation:
            if key == "__line__" or key in CONFIG["extra_validation_keys"]:
                continue
            if key not in allowed:
                fail(
                    line,
                    f"field '{field.get('id')}' has validation key '{key}' which is not applicable "
                    f"to type '{ftype}' (allowed: {sorted(allowed)})",
                )

        if "format" in validation and validation["format"] not in CONFIG['valid_formats']:
            fail(
                line,
                f"field '{field.get('id')}' has unknown format '{validation['format']}' "
                f"(valid: {sorted(CONFIG['valid_formats'])})",
            )

        lo, hi = validation.get("minimum"), validation.get("maximum")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
            fail(line, f"field '{field.get('id')}' has 'minimum' ({lo}) greater than 'maximum' ({hi})")

        lo_len, hi_len = validation.get("minLength"), validation.get("maxLength")
        if isinstance(lo_len, int) and isinstance(hi_len, int) and lo_len > hi_len:
            fail(line, f"field '{field.get('id')}' has 'minLength' ({lo_len}) greater than 'maxLength' ({hi_len})")

        lo_items, hi_items = validation.get("minItems"), validation.get("maxItems")
        if isinstance(lo_items, int) and isinstance(hi_items, int) and lo_items > hi_items:
            fail(line, f"field '{field.get('id')}' has 'minItems' ({lo_items}) greater than 'maxItems' ({hi_items})")

        if "pattern" in validation:
            import re
            try:
                re.compile(validation["pattern"])
            except re.error as e:
                fail(line, f"field '{field.get('id')}' has an invalid regex in 'pattern': {e}")

    def validate_show_if(field, line, field_ids):
        show_if = field["show_if"]
        if not isinstance(show_if, dict):
            fail(line, f"field '{field.get('id')}' has a 'show_if' key that must be a mapping")

        ref_field = show_if.get("field")
        if not ref_field:
            fail(line, f"field '{field.get('id')}' has 'show_if' missing required key 'field'")
        if ref_field not in field_ids:
            fail(line, f"field '{field.get('id')}' has 'show_if.field' referencing unknown field id '{ref_field}'")

        op = show_if.get("operator")
        if not op:
            fail(line, f"field '{field.get('id')}' has 'show_if' missing required key 'operator'")
        if op not in CONFIG['valid_operators']:
            fail(
                line,
                f"field '{field.get('id')}' has 'show_if.operator' with unknown value '{op}' "
                f"(valid: {sorted(CONFIG['valid_operators'])})",
            )

        if op not in ("is_empty", "is_not_empty") and "value" not in show_if:
            fail(
                line,
                f"field '{field.get('id')}' has 'show_if' missing required key 'value' "
                f"(required unless operator is is_empty/is_not_empty)",
            )

    def validate_field(field, field_ids):
        line = line_of(field)

        if not isinstance(field, dict):
            fail(line, "each entry in 'fields' must be a mapping")

        fid = field.get("id")
        if not fid:
            fail(line, "field is missing required key 'id'")
        if not isinstance(fid, str):
            fail(line, f"field 'id' must be a string, got {type(fid).__name__}")

        ftype = field.get("type")
        if not ftype:
            fail(line, f"field '{fid}' is missing required key 'type'")
        if ftype not in CONFIG['valid_types']:
            fail(line, f"field '{fid}' has unknown type '{ftype}' (valid: {sorted(CONFIG['valid_types'])})")

        if not field.get("label"):
            fail(line, f"field '{fid}' is missing required key 'label'")

        if "default" not in field:
            fail(line, f"field '{fid}' is missing required key 'default' (use null if no sensible default exists)")

        if "required" in field and not isinstance(field["required"], bool):
            fail(line, f"field '{fid}' has 'required' that must be a boolean")

        if ftype in CONFIG['choice_types']:
            validate_options(field, line)
        elif "options" in field:
            fail(line, f"field '{fid}' has an 'options' key which is not applicable to type '{ftype}'")

        if ftype in ("select", "radio") and field.get("default") is not None:
            opt_values = option_values(field)
            if opt_values and field["default"] not in opt_values:
                fail(line, f"field '{fid}' has 'default' ({field['default']!r}) that is not one of its declared option values {opt_values}")

        if ftype == "multiselect" and field.get("default") is not None:
            if not isinstance(field["default"], list):
                fail(line, f"field '{fid}' has 'default' that must be a list for type 'multiselect'")
            opt_values = option_values(field)
            bad = [v for v in field["default"] if opt_values and v not in opt_values]
            if bad:
                fail(line, f"field '{fid}' has 'default' containing values not in its options: {bad}")

        if "validation" in field:
            validate_validation_block(field, line)

        if "show_if" in field:
            validate_show_if(field, line, field_ids)

    # --- load file ---

    try:
        with open(fileio.path("configuration setup"), "r") as f:
            raw = f.read()
    except FileNotFoundError: # file must not exist, disregard
        return

    if _yaml_is_blank(raw):
        return

    yaml = _import_yaml()
    try:
        data = yaml.load(raw, Loader=make_line_loader())
    except yaml.YAMLError as e:
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line = e.problem_mark.line + 1
        fail(line, f"YAML syntax error: {e}")

    # Comment-only / empty default template — nothing to validate yet
    if data is None:
        return

    # --- validate top level ---

    if not isinstance(data, dict):
        fail(line_of(data), "top-level document must be a mapping")

    if "fields" not in data:
        fail(line_of(data), "missing required top-level key 'fields'")

    fields = data["fields"]
    if not isinstance(fields, list):
        fail(data.get("__line__"), "'fields' must be a list")

    field_ids = set()
    for field in fields:
        if isinstance(field, dict):
            fid = field.get("id")
            if isinstance(fid, str) and fid:
                if fid in field_ids:
                    fail(line_of(field), f"duplicate field id '{fid}'")
                field_ids.add(fid)

    for field in fields:
        validate_field(field, field_ids)



def _default_configuration_from_setup():
    """Build ``{field_id: default}`` from the device configuration-setup YAML.

    Returns ``{}`` when the file is missing, empty/comment-only, or has no fields.
    Includes fields whose ``default`` is ``null`` (as ``None``). Does not apply
    ``show_if`` — visibility is a form concern; defaults are static.
    """
    path = fileio.path("configuration setup")
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    if _yaml_is_blank(raw):
        return {}

    yaml = _import_yaml()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict):
        return {}

    fields = data.get("fields")
    if not isinstance(fields, list):
        return {}

    configuration = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        fid = field.get("id")
        if not isinstance(fid, str) or not fid:
            continue
        if "default" not in field:
            continue
        configuration[fid] = field.get("default")
    return configuration


def build(verbose=True, configuration=None):
    _validate_attributes_json()

    if not os.path.exists(fileio.path("configuration setup")):
        with open(fileio.path("configuration setup"), "w", encoding="utf-8") as f:
            f.write(
                build_utils.default_contents(
                    "device_configuration_setup_default.yaml"
                )
            )

    if not os.path.exists(fileio.path("signals list")):
        if not os.path.exists(fileio.path("build instructions")):
            with open(fileio.path("build instructions"), "w", encoding="utf-8") as f:
                f.write(
                    build_utils.default_contents(
                        "device_default_build_instructions.py"
                    )
                )

    if configuration is None:
        configuration = _default_configuration_from_setup()
    else:
        # Fill missing keys from setup defaults (e.g. system BOM passes {} or a partial dict)
        # so build instructions and the subsequent signals-list validation see a complete config.
        configuration = {**_default_configuration_from_setup(), **configuration}

    library_history.new()

    if os.path.exists(fileio.path("build instructions")):
        init_globals = {"configuration": configuration}
        build_sandbox.run_path(
            fileio.path("build instructions"),
            run_name="__main__",
            init_globals=init_globals,
        )
        if verbose:
            print("Successfully rebuilt signals list per build instructions.")

    _validate_signals_list(verbose)
    _validate_svg_symbol()
    _validate_config_yaml()
    from harnice.utils import physical_body
    physical_body.require_saved_mates()