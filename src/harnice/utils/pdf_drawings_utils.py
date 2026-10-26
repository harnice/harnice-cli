"""PDF drawings: page-setup from ``run_macro("pdf_generator", …)`` and SVG I/O."""

from __future__ import annotations

import ast
import json
import math
import os
import re
import tempfile
from io import BytesIO
from typing import Any

from harnice import fileio, state

DEFAULT_SCALES = {"A": 0.25, "B": 0.3, "C": 1.0}
DEFAULT_ARTIFACT_ID = "pdf_drawing-1"
MACRO_MPN = "pdf_generator"
MASTERS_TRANSLATE = (0, -960000)  # 10000 in @ 96 dpi
_INCOMPLETE_REBUILD_TEXT = "DID NOT COMPLETE REBUILD"
_INCOMPLETE_REBUILD_META = "/HarniceIncompleteRebuild"
_WATERMARK_SKIP_DIRS = {
    fileio.LIBRARY_USED_DIR,
    "__pycache__",
    ".git",
    ".gui_temp",
}

_BLANK_PAGE = {
    "tblock_mpn": "harnice_tblock",
    "tblock_lib_repo": "https://github.com/harnice/harnice-general-library",
    "tblock_lib_subpath": "library/titleblocks/",
    "page_size_in": [11.0, 8.5],
    # Titleblock local origin is bottom-right of the artwork (extends -x/-y).
    # Anchor = which page corner to dock to; offset_px = inset from that corner
    # (default 40 matches the page-frame inner margin so edges meet the border).
    "tblock_anchor": "bottom-right",
    "tblock_offset_px": [40.0, 40.0],
    "text_replacements": {
        "tblock-key-pagedesc": "",
        "tblock-key-desc": "",
        "tblock-key-pn": "",
        "tblock-key-drawnby": "",
        "tblock-key-rev": "",
        "tblock-key-scale": DEFAULT_SCALES["A"],
        "tblock-key-sheet": "autosheet",
    },
}

_TBLOCK_ANCHORS = ("top-left", "top-right", "bottom-left", "bottom-right")
_DEFAULT_INNER_MARGIN_PX = 40.0


def normalize_tblock_placement(page: dict[str, Any]) -> dict[str, Any]:
    """Fill / coerce tblock_anchor + tblock_offset_px on a page dict."""
    anchor = str(page.get("tblock_anchor") or "").strip().lower().replace("_", "-")
    if anchor not in _TBLOCK_ANCHORS:
        anchor = _BLANK_PAGE["tblock_anchor"]
    page["tblock_anchor"] = anchor

    offset = page.get("tblock_offset_px", _BLANK_PAGE["tblock_offset_px"])
    if isinstance(offset, str):
        offset = json.loads(offset)
    if (
        not isinstance(offset, (list, tuple))
        or len(offset) != 2
        or not all(isinstance(v, (int, float)) for v in offset)
    ):
        offset = list(_BLANK_PAGE["tblock_offset_px"])
    page["tblock_offset_px"] = [float(offset[0]), float(offset[1])]
    return page


def tblock_origin_on_page(
    page_w: float,
    page_h: float,
    tblock_w: float,
    tblock_h: float,
    anchor: str,
    offset_xy: list[float] | tuple[float, float],
) -> tuple[float, float]:
    """Page-space translate for a tblock whose local origin is its bottom-right.

    Artwork occupies local ``[-w, 0] × [-h, 0]``. The chosen page corner is inset
    by ``offset_xy`` so the block stays on-page and can meet the frame border.
    """
    ox, oy = float(offset_xy[0]), float(offset_xy[1])
    w, h = float(tblock_w), float(tblock_h)
    anchor = (anchor or "bottom-right").strip().lower().replace("_", "-")
    if anchor == "top-left":
        return (ox + w, oy + h)
    if anchor == "top-right":
        return (page_w - ox, oy + h)
    if anchor == "bottom-left":
        return (ox + w, page_h - oy)
    # bottom-right (default)
    return (page_w - ox, page_h - oy)


def _call_func_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _eval_ast(node, env: dict[str, Any] | None = None):
    """Evaluate a restricted AST node (literals, names, ``dict.get``)."""
    if node is None:
        return None
    env = env or {}
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _eval_ast(node.operand, env)
        if isinstance(v, (int, float)):
            return -v
        return None
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and not node.keywords
            and 1 <= len(node.args) <= 2
        ):
            obj = _eval_ast(func.value, env)
            if isinstance(obj, dict):
                key = _eval_ast(node.args[0], env)
                default = (
                    _eval_ast(node.args[1], env) if len(node.args) == 2 else None
                )
                try:
                    return obj.get(key, default)
                except TypeError:
                    return None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            owner, meth = func.value.id, func.attr
            args = [_eval_ast(a, env) for a in node.args]
            kwargs = {
                k.arg: _eval_ast(k.value, env) for k in node.keywords if k.arg
            }
            try:
                if owner == "state" and meth == "partnumber" and len(args) == 1:
                    from harnice import state as _state

                    return _state.partnumber(args[0])
                if owner == "rev_history" and meth == "info":
                    from harnice.lists import rev_history as _rh

                    return _rh.info(*args, **kwargs)
            except (TypeError, ValueError, FileNotFoundError, RuntimeError, KeyError):
                return None
        return None
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == "state":
            try:
                from harnice import state as _state

                return getattr(_state, node.attr)
            except AttributeError:
                return None
        return None
    if isinstance(node, ast.Dict):
        out = {}
        for k_node, v_node in zip(node.keys, node.values):
            key = _eval_ast(k_node, env)
            if key is None and k_node is not None:
                return None
            if isinstance(key, list):
                key = tuple(key)
            try:
                out[key] = _eval_ast(v_node, env)
            except TypeError:
                return None
        return out
    if isinstance(node, ast.List):
        vals = [_eval_ast(elt, env) for elt in node.elts]
        if any(v is None and not isinstance(elt, ast.Constant) for v, elt in zip(vals, node.elts)):
            # None can be a real value (Constant). Only fail if eval failed.
            pass
        return vals
    if isinstance(node, ast.Tuple):
        return tuple(_eval_ast(elt, env) for elt in node.elts)
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _collect_literal_env(tree: ast.AST) -> dict[str, Any]:
    env: dict[str, Any] = {}

    class _Visitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            try:
                value = _eval_ast(node.value, env)
            except (TypeError, ValueError):
                self.generic_visit(node)
                return
            if value is None and not (
                isinstance(node.value, ast.Constant) and node.value.value is None
            ):
                self.generic_visit(node)
                return
            for target in node.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = value
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            if isinstance(node.target, ast.Name) and node.value is not None:
                value = _eval_ast(node.value, env)
                if value is not None or (
                    isinstance(node.value, ast.Constant) and node.value.value is None
                ):
                    env[node.target.id] = value
            self.generic_visit(node)

    _Visitor().visit(tree)
    return env


def parse_pdf_generator_calls(source: str) -> list[dict[str, Any]]:
    """Return ``[{artifact_id, page_setup}, ...]`` from ``run_macro`` calls."""
    if not source or not str(source).strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    env = _collect_literal_env(tree)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if _call_func_name(node.func) == "run_macro":
                args = list(node.args)
                keywords = {k.arg: k.value for k in node.keywords if k.arg}
                mpn = _eval_ast(args[0], env) if args else _eval_ast(
                    keywords.get("macro_part_number"), env
                )
                if mpn == MACRO_MPN:
                    artifact_id = None
                    if "artifact_id" in keywords:
                        artifact_id = _eval_ast(keywords["artifact_id"], env)
                    elif len(args) >= 4:
                        artifact_id = _eval_ast(args[3], env)
                    artifact_id = str(artifact_id or "").strip()
                    if artifact_id and artifact_id not in seen:
                        page_setup = None
                        if "page_setup" in keywords:
                            page_setup = _eval_ast(keywords["page_setup"], env)
                        seen.add(artifact_id)
                        out.append(
                            {
                                "artifact_id": artifact_id,
                                "page_setup": page_setup
                                if isinstance(page_setup, dict)
                                else None,
                            }
                        )
            self.generic_visit(node)

    _Visitor().visit(tree)
    return out


def list_pdf_generator_calls() -> list[dict[str, Any]]:
    """``pdf_generator`` ``run_macro`` calls in the open project's build instructions."""
    path = None
    try:
        path = fileio.path("build instructions")
    except Exception:
        path = None
    source = ""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            source = f.read()
    return parse_pdf_generator_calls(source)


def get_pdf_generator_call(artifact_id: str) -> dict[str, Any] | None:
    key = (artifact_id or "").strip()
    if not key:
        return None
    for call in list_pdf_generator_calls():
        if call.get("artifact_id") == key:
            return call
    return None


def reset_pdf_generator_runs() -> None:
    """Stamp existing revision PDFs at the start of a build.

    Red ``DID NOT COMPLETE REBUILD`` text is drawn across every page so a failed
    build cannot leave the previous output looking current. A successful
    ``pdf_generator`` run in build instructions rewrites those PDFs without the stamp.
    """
    watermark_existing_pdfs_incomplete_rebuild()


def _pdf_literal(text: str) -> str:
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def _incomplete_rebuild_overlay_page(width: float, height: float):
    """A same-size page with diagonal red stamp text, for ``merge_page``."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        FloatObject,
        NameObject,
    )

    w, h = float(width), float(height)
    if w <= 0 or h <= 0:
        w, h = 612.0, 792.0
    text = _INCOMPLETE_REBUILD_TEXT
    diag = math.hypot(w, h)
    font_size = max(18.0, min(w, h) * 0.09)
    est_width = 0.62 * font_size * len(text)
    if est_width > 0:
        font_size *= (0.78 * diag) / est_width
        font_size = max(14.0, min(font_size, min(w, h) * 0.2))
        est_width = 0.62 * font_size * len(text)
    angle = math.atan2(h, w)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    cx, cy = w / 2.0, h / 2.0
    tx, ty = -est_width / 2.0, -font_size / 2.4
    stream = (
        "q\n"
        "/GS1 gs\n"
        f"1 0 0 1 {cx:.3f} {cy:.3f} cm\n"
        f"{cos_a:.5f} {sin_a:.5f} {-sin_a:.5f} {cos_a:.5f} 0 0 cm\n"
        f"1 0 0 1 {tx:.3f} {ty:.3f} cm\n"
        "BT\n"
        f"/F1 {font_size:.3f} Tf\n"
        "1 0 0 rg\n"
        "0 Tr\n"
        f"{_pdf_literal(text)} Tj\n"
        "ET\n"
        "Q\n"
    )
    writer = PdfWriter()
    page = writer.add_blank_page(width=w, height=h)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
        }
    )
    gs = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/ExtGState"),
            NameObject("/CA"): FloatObject(0.55),
            NameObject("/ca"): FloatObject(0.55),
        }
    )
    resources = page[NameObject("/Resources")]
    resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
    resources[NameObject("/ExtGState")] = DictionaryObject({NameObject("/GS1"): gs})
    contents = DecodedStreamObject()
    contents.set_data(stream.encode("latin-1"))
    page.replace_contents(contents)
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return PdfReader(buf).pages[0]


def _pdf_already_incomplete_rebuild(reader) -> bool:
    meta = getattr(reader, "metadata", None)
    if meta is not None:
        try:
            if str(meta.get(_INCOMPLETE_REBUILD_META) or "").strip():
                return True
        except Exception:
            pass
    try:
        for page in reader.pages:
            if _INCOMPLETE_REBUILD_TEXT in (page.extract_text() or ""):
                return True
    except Exception:
        pass
    return False


def _iter_revision_pdfs(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _WATERMARK_SKIP_DIRS and not name.startswith(".")
        ]
        for name in filenames:
            if not name.lower().endswith(".pdf"):
                continue
            if name.startswith("."):
                continue
            yield os.path.join(dirpath, name)


def _watermark_pdf_incomplete_rebuild(path: str) -> bool:
    """Stamp every page. Return True if the file was rewritten."""
    from pypdf import PdfReader, PdfWriter

    try:
        reader = PdfReader(path)
    except Exception:
        return False
    if _pdf_already_incomplete_rebuild(reader):
        return False
    writer = PdfWriter()
    try:
        for page in reader.pages:
            box = page.mediabox
            overlay = _incomplete_rebuild_overlay_page(box.width, box.height)
            page.merge_page(overlay)
            writer.add_page(page)
    except Exception:
        return False
    if reader.metadata:
        try:
            writer.add_metadata(dict(reader.metadata))
        except Exception:
            pass
    writer.add_metadata({_INCOMPLETE_REBUILD_META: "true"})
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".harnice-wm-", suffix=".pdf", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            writer.write(f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    return True


def watermark_existing_pdfs_incomplete_rebuild() -> None:
    """Stamp all PDFs in the current revision with incomplete-rebuild text."""
    try:
        root = fileio.rev_directory()
    except Exception:
        return
    if not root or not os.path.isdir(root):
        return
    for path in _iter_revision_pdfs(root):
        _watermark_pdf_incomplete_rebuild(path)


def is_pdf_generator_instance(
    item_type: str, instance_name: str, inst_dir: str | None = None
) -> bool:
    if (item_type or "").strip().lower() != "macro":
        return False
    if inst_dir and os.path.isfile(os.path.join(inst_dir, "pdf_generator.py")):
        return True
    name = (instance_name or "").strip()
    return any(c.get("artifact_id") == name for c in list_pdf_generator_calls())


def macro_base_directory(artifact_id: str) -> str:
    return os.path.join("instance_data", "macro", artifact_id)


def master_contents_path(artifact_id: str) -> str:
    return os.path.join(
        fileio.dirpath(None, base_directory=macro_base_directory(artifact_id)),
        f"{artifact_id}-mastercontents.svg",
    )


def page_svgs_dir(artifact_id: str) -> str:
    return os.path.join(
        fileio.dirpath(None, base_directory=macro_base_directory(artifact_id)),
        "page_svgs",
    )


def page_svg_path(artifact_id: str, page_counter: int, page_name: str) -> str:
    return os.path.join(
        page_svgs_dir(artifact_id),
        f"{page_counter}-{page_name}-user-editable.svg",
    )


def page_name(page: dict[str, Any]) -> str:
    """Page identity is ``text_replacements['tblock-key-pagedesc']``."""
    tr = page.get("text_replacements")
    if not isinstance(tr, dict):
        return ""
    return str(tr.get("tblock-key-pagedesc") or "").strip()


def blank_page_dict(name: str) -> dict[str, Any]:
    page = {
        "tblock_mpn": _BLANK_PAGE["tblock_mpn"],
        "tblock_lib_repo": _BLANK_PAGE["tblock_lib_repo"],
        "tblock_lib_subpath": _BLANK_PAGE["tblock_lib_subpath"],
        "page_size_in": list(_BLANK_PAGE["page_size_in"]),
        "tblock_anchor": _BLANK_PAGE["tblock_anchor"],
        "tblock_offset_px": list(_BLANK_PAGE["tblock_offset_px"]),
        "text_replacements": dict(_BLANK_PAGE["text_replacements"]),
    }
    page["text_replacements"]["tblock-key-pagedesc"] = name
    return page


def default_page_setup() -> dict[str, Any]:
    """Seed pages for a new drawing. Systems get a single ``page1`` sheet."""
    if str(getattr(state, "project_type", "") or "").strip().lower() == "system":
        return {"pages": [blank_page_dict("page1")]}
    return {
        "pages": [
            blank_page_dict("overview"),
            blank_page_dict("to-from table"),
            blank_page_dict("channel map"),
        ]
    }


def normalize_page_setup(data: Any) -> dict[str, Any]:
    """Fill defaults and validate a page_setup dict. Does not write a file."""
    if not isinstance(data, dict) or "pages" not in data:
        data = default_page_setup()
    if not isinstance(data.get("pages"), list):
        raise TypeError("'pages' must be a list")
    pages = []
    names = []
    for i, page in enumerate(data["pages"], start=1):
        if not isinstance(page, dict):
            raise TypeError(f"page {i} must be a dict")
        incoming_tr = page.get("text_replacements")
        if isinstance(incoming_tr, str):
            incoming_tr = json.loads(incoming_tr) if incoming_tr.strip() else {}
        if not isinstance(incoming_tr, dict):
            incoming_tr = {}
        text_replacements = dict(_BLANK_PAGE["text_replacements"])
        text_replacements.update(incoming_tr)

        new_page = {
            "tblock_mpn": str(
                page.get("tblock_mpn") or _BLANK_PAGE["tblock_mpn"]
            ).strip(),
            "tblock_lib_repo": str(
                page.get("tblock_lib_repo") or _BLANK_PAGE["tblock_lib_repo"]
            ).strip(),
            "tblock_lib_subpath": str(
                page.get("tblock_lib_subpath") or _BLANK_PAGE["tblock_lib_subpath"]
            ).strip(),
            "page_size_in": page.get("page_size_in", _BLANK_PAGE["page_size_in"]),
            "tblock_anchor": page.get("tblock_anchor", _BLANK_PAGE["tblock_anchor"]),
            "tblock_offset_px": page.get(
                "tblock_offset_px", _BLANK_PAGE["tblock_offset_px"]
            ),
            "text_replacements": text_replacements,
        }
        name = page_name(new_page)
        if not name:
            raise KeyError(
                f"page {i} missing text_replacements['tblock-key-pagedesc']"
            )
        size = new_page.get("page_size_in", _BLANK_PAGE["page_size_in"])
        if isinstance(size, str):
            size = json.loads(size)
        if (
            not isinstance(size, (list, tuple))
            or len(size) != 2
            or not all(isinstance(v, (int, float)) for v in size)
        ):
            raise ValueError(f"page {i} page_size_in must be [width_in, height_in]")
        new_page["page_size_in"] = [float(size[0]), float(size[1])]
        normalize_tblock_placement(new_page)
        names.append(name)
        pages.append(new_page)
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Duplicate page name(s): {', '.join(sorted(str(d) for d in dupes))}")
    return {"pages": pages}


def load_page_setup(artifact_id: str) -> dict[str, Any]:
    """Page setup from the ``page_setup=`` arg on ``run_macro("pdf_generator", …)``."""
    call = get_pdf_generator_call(artifact_id)
    if not call or not isinstance(call.get("page_setup"), dict):
        raise ValueError(
            f'No page_setup on run_macro("pdf_generator", artifact_id={artifact_id!r}) '
            "in build instructions"
        )
    return normalize_page_setup(call["page_setup"])


def _master_name_from_filename(filename: str) -> str | None:
    if not filename.endswith("-master.svg"):
        return None
    if filename.endswith("-mastercontents.svg") or filename.endswith(
        "mastercontents.svg"
    ):
        return None
    return filename[: -len("-master.svg")] or None


def _svg_has_matching_master_group(svg_path: str, master_name: str) -> bool:
    """True when the file contains id="{master_name}-contents-start"."""
    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    return f'id="{master_name}-contents-start"' in text


BLOCK_DIAGRAM_MASTER_NAME = "block-diagram"
_APPLIED_TRACES_GROUP_ID = "applied-traces"

# Device answers live in the SVG namespace as ``<configuration>``. Inkscape does
# not know that type (``WARNING: unknown type: svg:configuration``). Values are
# already baked into attribute-text nodes; the element is metadata only.
_CONFIGURATION_ELEMENT_RE = re.compile(
    r"<((?:[\w.-]+:)?configuration)\b(?:[^>]*/>|[^>]*>.*?</\1\s*>)",
    re.IGNORECASE | re.DOTALL,
)


def strip_configuration_elements(svg_text: str) -> str:
    """Remove Harnice ``<configuration>`` metadata from SVG sent to Inkscape."""
    if not svg_text or "configuration" not in svg_text:
        return svg_text
    return _CONFIGURATION_ELEMENT_RE.sub("", svg_text)


_IMAGE_TAG_RE = re.compile(r"<image\b[^>]*>", re.IGNORECASE)
_IMAGE_HREF_RE = re.compile(
    r'((?:xlink:)?href\s*=\s*")([^"]*)(")',
    re.IGNORECASE,
)
_RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def rasterize_linked_images(svg_text, svg_directory=None, search_roots=None):
    """Replace linked raster ``<image href>`` values with embedded image data.

    The sheet SVG keeps the links. Call this on the copy sent to Inkscape so
    the PDF contains the pixels. A link is resolved against ``svg_directory``,
    each extra search root, then the revision directory. Missing files and
    links that are already ``data:`` URIs are left alone.
    """

    def _raster_data_uri(path):
        """``data:`` URI for a raster file, or None when it is not a readable image."""
        import base64

        suffix = os.path.splitext(path)[1].lower()
        if suffix not in _RASTER_SUFFIXES or not os.path.isfile(path):
            return None
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }[suffix]
        with open(path, "rb") as handle:
            payload = base64.b64encode(handle.read()).decode("ascii")
        return f"data:{mime};base64,{payload}"

    def _resolve_image_href(url, roots):
        """Absolute file for an SVG image link, or '' when none of the roots has it."""
        from urllib.parse import unquote, urlparse

        text = (url or "").strip()
        if not text or text.startswith("data:"):
            return ""
        if text.startswith("file:"):
            parsed = urlparse(text)
            text = unquote(parsed.path)
        text = os.path.normpath(text)
        if os.path.isabs(text) and os.path.isfile(text):
            return text
        for root in roots:
            if not root:
                continue
            candidate = os.path.normpath(os.path.join(root, text))
            if os.path.isfile(candidate):
                return candidate
        return ""

    if not svg_text or "<image" not in svg_text.lower():
        return svg_text
    roots = []
    if svg_directory:
        roots.append(svg_directory)
    for root in search_roots or []:
        if root and root not in roots:
            roots.append(root)
    try:
        rev = fileio.rev_directory()
    except Exception:
        rev = ""
    if rev and rev not in roots:
        roots.append(rev)

    def replace_tag(match):
        tag = match.group(0)

        def replace_href(href_match):
            url = href_match.group(2)
            if url.startswith("data:"):
                return href_match.group(0)
            path = _resolve_image_href(url, roots)
            data = _raster_data_uri(path) if path else None
            if not data:
                return href_match.group(0)
            return href_match.group(1) + data + href_match.group(3)

        return _IMAGE_HREF_RE.sub(replace_href, tag)

    return _IMAGE_TAG_RE.sub(replace_tag, svg_text)


def extra_project_masters() -> list[dict[str, str]]:
    """Cloneable SVGs that are not ``*-master.svg`` files.

    Systems expose the block diagram in the PDF palette even though it is not a
    master drawing. The name is an XML id (``block-diagram``), not the file key.
    """
    try:
        path = fileio.path("block diagram")
    except Exception:
        return []
    if not path or not os.path.isfile(path):
        return []
    return [{"name": BLOCK_DIAGRAM_MASTER_NAME, "path": path}]


def _svg_root_open_tag(svg_text: str) -> re.Match[str] | None:
    return re.search(r"<svg\b[^>]*>", svg_text, flags=re.IGNORECASE | re.DOTALL)


def ensure_attr_on_root_svg(svg_text: str, attr: str, value: str) -> str:
    """Set ``attr="value"`` on the root ``<svg>`` if that attribute is absent."""
    m = _svg_root_open_tag(svg_text)
    if not m:
        return svg_text
    tag = m.group(0)
    if re.search(rf"\b{re.escape(attr)}\s*=", tag):
        return svg_text
    patched = re.sub(r"<svg\b", f'<svg {attr}="{value}"', tag, count=1, flags=re.IGNORECASE)
    return svg_text[: m.start()] + patched + svg_text[m.end() :]


def copy_root_svg_namespaces(source_svg: str, dest_svg: str) -> str:
    """Copy ``xmlns:*`` declarations from the source root ``<svg>`` onto dest."""
    m = _svg_root_open_tag(source_svg)
    if not m:
        return dest_svg
    for am in re.finditer(r'\b(xmlns:[A-Za-z_][\w.-]*)="([^"]*)"', m.group(0)):
        dest_svg = ensure_attr_on_root_svg(dest_svg, am.group(1), am.group(2))
    return dest_svg


def _contents_group_name_from_svg(svg_text: str) -> str:
    """Name of the document ``*-contents-start`` group (not nested symbols)."""
    try:
        pn_rev = state.partnumber("pn-rev")
    except Exception:
        pn_rev = ""
    if pn_rev and f'id="{pn_rev}-contents-start"' in svg_text:
        return pn_rev
    m = re.search(r'id="([^"]+)-contents-start"', svg_text)
    if not m:
        raise ValueError("No *-contents-start group in source SVG")
    return m.group(1)


def _extract_element_outer_xml(svg_text: str, element_id: str) -> str | None:
    """Return the outer XML of the first element with ``id=element_id``."""
    needle = f'id="{element_id}"'
    attr_i = svg_text.find(needle)
    if attr_i < 0:
        return None
    start = svg_text.rfind("<", 0, attr_i)
    if start < 0:
        return None
    name_m = re.match(r"<([A-Za-z_][\w:.-]*)", svg_text[start:])
    if not name_m:
        return None
    tag = name_m.group(1)
    gt = svg_text.find(">", start)
    if gt < 0:
        return None
    if svg_text[start : gt + 1].rstrip().endswith("/>"):
        return svg_text[start : gt + 1]
    open_re = re.compile(rf"<{re.escape(tag)}\b", re.IGNORECASE)
    close_re = re.compile(rf"</{re.escape(tag)}\s*>", re.IGNORECASE)
    depth = 0
    pos = start
    while pos < len(svg_text):
        om = open_re.search(svg_text, pos)
        cm = close_re.search(svg_text, pos)
        if cm is None:
            return None
        if om is not None and om.start() < cm.start():
            ogt = svg_text.find(">", om.start())
            if ogt >= 0 and svg_text[om.start() : ogt + 1].rstrip().endswith("/>"):
                pos = ogt + 1
                continue
            depth += 1
            pos = om.end()
            continue
        depth -= 1
        pos = cm.end()
        if depth == 0:
            return svg_text[start:pos]
    return None


def _insert_before_contents_end(svg_text: str, dest_group_name: str, markup: str) -> str:
    end_tag = f'id="{dest_group_name}-contents-end"'
    end_i = svg_text.find(end_tag)
    if end_i == -1:
        raise ValueError(f"Missing {end_tag}")
    end_i = svg_text.rfind("<", 0, end_i)
    return svg_text[:end_i] + markup + svg_text[end_i:]


def copy_svg_inner_into_group(
    source_svg_path: str, dest_svg_path: str, dest_group_name: str
) -> None:
    """Copy a non-master SVG (system block diagram) into a PDF master group.

    Uses the document ``{pn-rev}-contents-start`` inner markup, not the whole
    ``<svg>``. Dumping the root would paste an XML id that starts with a digit
    (invalid) and drop ``xmlns:schem``, which makes page SVGs unparseable.
    """
    from harnice.utils import svg_utils

    with open(source_svg_path, encoding="utf-8") as f:
        source = f.read()
    source_group = _contents_group_name_from_svg(source)
    svg_utils.find_and_replace_svg_group(
        source_svg_path, source_group, dest_svg_path, dest_group_name
    )
    traces = _extract_element_outer_xml(source, _APPLIED_TRACES_GROUP_ID)
    with open(dest_svg_path, encoding="utf-8") as f:
        dest = f.read()
    if traces:
        dest = _insert_before_contents_end(
            dest, dest_group_name, "\n" + traces + "\n"
        )
    dest = copy_root_svg_namespaces(source, dest)
    dest = strip_configuration_elements(dest)
    with open(dest_svg_path, "w", encoding="utf-8") as f:
        f.write(dest)


def _merge_extra_master_names(names: list[str]) -> list[str]:
    extra = [m["name"] for m in extra_project_masters()]
    extra_set = set(extra)
    return extra + [n for n in names if n not in extra_set]


def list_masters_from_disk() -> list[dict[str, str]]:
    """Discover *-master.svg files the same way pdf_generator does.

    Only includes files whose inner group id matches the filename stem
    (``{name}-master.svg`` requires ``id="{name}-contents-start"``).
    Also prepends :func:`extra_project_masters` (system block diagram).
    """
    directory_to_search = fileio.dirpath(None)
    masters: list[tuple[str, str]] = []
    for root, _, files in os.walk(directory_to_search):
        for filename in files:
            master_name = _master_name_from_filename(filename)
            if not master_name:
                continue
            svg_path = os.path.join(root, filename)
            if not _svg_has_matching_master_group(svg_path, master_name):
                continue
            masters.append((master_name, svg_path))
    masters.sort(key=lambda x: x[0])
    extra = extra_project_masters()
    extra_names = {m["name"] for m in extra}
    disk = [
        {"name": name, "path": path}
        for name, path in masters
        if name not in extra_names
    ]
    return extra + disk


def _top_level_group_ids(inner: str) -> list[str]:
    """``id`` of each top-level ``<g>`` in ``inner`` (depth-0 only)."""
    names: list[str] = []
    depth = 0
    pos = 0
    tag_re = re.compile(r"</?g\b[^>]*>", re.IGNORECASE)
    while True:
        m = tag_re.search(inner, pos)
        if not m:
            break
        tag = m.group(0)
        pos = m.end()
        if tag.startswith("</"):
            depth = max(0, depth - 1)
            continue
        self_close = tag.rstrip().endswith("/>")
        if depth == 0:
            idm = re.search(r'\bid="([^"]+)"', tag)
            if idm:
                names.append(idm.group(1))
        if not self_close:
            depth += 1
    return names


def list_masters_from_mastercontents(artifact_id: str) -> list[str]:
    path = master_contents_path(artifact_id)
    if not os.path.exists(path):
        return _merge_extra_master_names([m["name"] for m in list_masters_from_disk()])
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return _merge_extra_master_names([m["name"] for m in list_masters_from_disk()])
    start_tag = 'id="svg-master-contents-start"'
    end_tag = 'id="svg-master-contents-end"'
    si = text.find(start_tag)
    ei = text.find(end_tag)
    names: list[str] = []
    if si != -1 and ei != -1 and ei > si:
        si = text.find(">", si) + 1
        ei = text.rfind("<", 0, ei)
        names = _top_level_group_ids(text[si:ei])
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n in ("svg-master",) or n.endswith("-contents-start"):
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    if not out:
        return _merge_extra_master_names([m["name"] for m in list_masters_from_disk()])
    return _merge_extra_master_names(out)


def pages_summary(artifact_id: str) -> list[dict[str, Any]]:
    setup = load_page_setup(artifact_id)
    pages = []
    for i, page in enumerate(setup.get("pages", []), start=1):
        name = page_name(page) or f"page-{i}"
        svg_path = page_svg_path(artifact_id, i, name)
        pages.append(
            {
                "index": i,
                "name": name,
                "svg_exists": os.path.exists(svg_path),
                "svg_path": svg_path,
                "tblock_mpn": page.get("tblock_mpn"),
            }
        )
    return pages


def read_page_svg(artifact_id: str, page_index: int) -> str | None:
    setup = load_page_setup(artifact_id)
    pages = setup.get("pages", [])
    if page_index < 1 or page_index > len(pages):
        raise IndexError(f"page index {page_index} out of range")
    page = pages[page_index - 1]
    path = page_svg_path(artifact_id, page_index, page_name(page))
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_page_svg(artifact_id: str, page_index: int, svg_text: str) -> str:
    setup = load_page_setup(artifact_id)
    pages = setup.get("pages", [])
    if page_index < 1 or page_index > len(pages):
        raise IndexError(f"page index {page_index} out of range")
    page = pages[page_index - 1]
    path = page_svg_path(artifact_id, page_index, page_name(page))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_text)
    return path
