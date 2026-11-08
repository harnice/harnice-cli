import os
import csv
from harnice import fileio, state
from harnice import build_sandbox
from harnice.lists import (
    post_harness_instances_list,
    circuits_list,
    instances_list,
    library_history,
    channel_map,
    signals_list,
)
from harnice.utils import block_diagram_utils, build_utils, system_utils

default_desc = "SYSTEM, SCOPE, etc."

button_color = "#86e1eb"

gitignore_rules = [
    ".gui_temp/",
    "*.tmp",
    "*.tmp.step",
    ".harnice-wm-*.pdf",
]

# stores all the connectors in the system
connector_list = []

# automatically updated and stored when passthrough_map.new() is called
passthrough_routing_context = []

# automatically updated and stored when passthrough_map updates availability counters
passthrough_availability_counters = {}

# highest requirement number issued by passthrough_map.route() (reset by passthrough_map.new())
passthrough_highest_requirement = 0


def file_structure():
    return {
        "build.py": "build instructions",
        "instances.tsv": "instances list",
        "blockdiagram.svg": "block diagram",
        "signals.tsv": "icd",
        "physical.json": "physical assembly",
        "assembly.step": "assembly",
        # Mating-connector nodes are written here by the system build.
        "available_network.json": "available network",
        # Reference STEP files dropped in from the file browser. The physical
        # view shows one of them at a time.
        "contexts": {},
        "instance_data": {},
        "harnesses": {},
        "lists": {
            "bom.tsv": "bom",
            "circuits.tsv": "circuits list",
            "instances_w_hrns.tsv": "post harness instances list",
            "connectors.tsv": "system connector list",
            "mapped.tsv": "mapped channels set",
            "libhist.tsv": "library history",
        },
        "maps": {
            "channels.tsv": "channel map",
            "channel_map_flattened.tsv": "flattened channel map",
            "passthrough.tsv": "passthrough map",
            "context.tsv": "passthrough routing context",
            "forced_channels_pending.tsv": "pending forced channels",
            "forced_signals.tsv": "forced signal map",
        },
    }


def generate_structure():
    os.makedirs(fileio.dirpath("instance_data"), exist_ok=True)
    os.makedirs(fileio.dirpath("harnesses"), exist_ok=True)
    os.makedirs(fileio.dirpath("lists"), exist_ok=True)
    os.makedirs(fileio.dirpath("maps"), exist_ok=True)
    os.makedirs(fileio.dirpath("contexts"), exist_ok=True)


def _icd_rows_from_unmated_device_connector(connector):
    """Copy the device signals-list rows for one flagged unmated connector.

    ``channel_id`` and ``connector_id`` are written as
    ``{device_refdes}.{value}``.
    """
    refdes = (connector.get("device_refdes") or "").strip()
    conn_name = (connector.get("device_connector") or "").strip()
    if not refdes or not conn_name:
        raise ValueError(
            "External interface flag on an unmated device connector is missing "
            "device_refdes or device_connector"
        )
    path = os.path.join(
        fileio.dirpath("instance_data"), "device", refdes, "signals.tsv"
    )
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(
            f"Cannot build ICD from flagged connector {refdes}.{conn_name}: "
            f"device signals list not found at {path}"
        )
    rows = []
    for row in fileio.read_tsv(path):
        if (row.get("connector_id") or "").strip() != conn_name:
            continue
        copied = {col: (row.get(col) or "").strip() for col in signals_list.COLUMNS}
        ch_id = copied.get("channel_id") or ""
        copied["channel_id"] = f"{refdes}.{ch_id}"
        copied["connector_id"] = f"{refdes}.{conn_name}"
        rows.append(copied)
    return rows


def generate_icd():
    """
    Write the external ICD signals list from block-diagram external-interface flags.

    Flags on an unmated device connector copy that connector's rows from the
    device's signals list. Flags on a harness-mated face collect matching
    circuit rows.

    The ``subsystem_symbol`` macro (in build instructions) copies unique ICD
    ``connector_id`` values onto symbol pins and runs device signals-list
    checks against that ICD (pin mismatches warn, they do not fail the build).
    This function runs *after* build instructions, so pin sync and verification
    always see the previous build's ICD. After changing external-interface
    flags, build twice. That lag is expected.
    """
    circuits = circuits_list.read()
    connectors_list = fileio.read_tsv("system connector list")

    icd = []

    for connector in connectors_list:
        if (connector.get("external_interface_flag") or "").strip().upper() != "TRUE":
            continue

        h_ref = (connector.get("mating_harness_refdes") or "").strip()
        is_unmated = h_ref == system_utils.UNMATED_HARNESS_REFDES

        if is_unmated:
            icd.extend(_icd_rows_from_unmated_device_connector(connector))
            continue

        connector_key = (
            connector.get("device_refdes"),
            connector.get("device_connector"),
        )

        for circuit in circuits:
            if (
                circuit.get("harness_from_refdes"),
                circuit.get("harness_from_connector_name"),
            ) == connector_key:
                icd.append(
                    {
                        "channel_id": f"{circuit.get('to_side_device_refdes')}.{circuit.get('to_side_device_chname')}",
                        "repeat_channel_id": "",
                        "signal": circuit.get("from_signal"),
                        "connector_id": f"{connector.get('device_refdes')}.{connector.get('device_connector')}",
                        "cavity": circuit.get("harness_from_cavity"),
                        "device_connector_mpn": connector.get("device_connector_mpn"),
                        "harness_connector_mpn": "",
                        "channel_type": circuit.get("from_channel_type"),
                    }
                )
            if (
                circuit.get("harness_to_refdes"),
                circuit.get("harness_to_connector_name"),
            ) == connector_key:
                icd.append(
                    {
                        "channel_id": f"{circuit.get('from_side_device_refdes')}.{circuit.get('from_side_device_chname')}",
                        "repeat_channel_id": "",
                        "signal": circuit.get("from_signal"),
                        "connector_id": f"{connector.get('device_refdes')}.{connector.get('device_connector')}",
                        "cavity": circuit.get("harness_to_cavity"),
                        "device_connector_mpn": connector.get("device_connector_mpn"),
                        "harness_connector_mpn": "",
                        "channel_type": circuit.get("to_channel_type"),
                    }
                )

    icd_path = fileio.path("icd")
    os.makedirs(os.path.dirname(icd_path), exist_ok=True)
    with open(icd_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=signals_list.COLUMNS, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(icd)


def build():
    state.set_harness(None)

    # remove gui temp content if it exists
    fileio.silentremove(os.path.join(fileio.rev_directory(), ".gui_temp/"))

    # write blank build instructions if none exist
    if not os.path.exists(fileio.path("build instructions")):
        with open(fileio.path("build instructions"), "w", encoding="utf-8") as f:
            f.write(
                build_utils.default_contents("system_default_build_instructions.py")
            )

    # write empty block diagram if none exists
    if not os.path.exists(fileio.path("block diagram")):
        fileio.atomic_write_text(
            fileio.path("block diagram"),
            build_utils.default_contents(
                "system_default_block_diagram.svg",
                {"pn_rev": state.partnumber("pn-rev")},
            ),
        )

    library_history.new()
    instances_list.new()

    # data-update-refdes is the name to apply. Move the instance folder and
    # physical.json keys onto it, and rewrite the diagram id, before pull.
    system_utils.apply_staged_instance_renames()

    # export bom and pull device/harness library files into instance_data
    # and the instances list (circuit-derived instances come later via
    # create_instances_from_circuits_list)
    system_utils.export_bom_from_block_diagram()
    system_utils._import_bom_devices(update_instances_list=True)
    system_utils.make_connector_list()
    channel_map.new()

    # run build instructions
    from harnice.utils import pdf_drawings_utils, svg_utils

    pdf_drawings_utils.reset_pdf_generator_runs()
    svg_utils.trace_overlay_style.reset()
    try:
        build_sandbox.run_path(fileio.path("build instructions"))

        # rebuild the post-harness instances list from all the linked-in harnesses
        post_harness_instances_list.rebuild()

        # compile the external ICD from external interface flag
        generate_icd()

        # Append derived trace overlays under ``applied-traces`` (``channel_traces`` / ``circuit_traces``).
        # Prior derived layers are stripped first. Stroke, spacing, and label
        # size come from svg_utils.trace_overlay_style, which the script may
        # have changed before a PDF copy and then put back.
        bd_path = fileio.path("block diagram")
        with open(bd_path, "r", encoding="utf-8") as f:
            svg_diagram = f.read()
        original_svg = svg_diagram
        # Always re-read placed device/subsystem symbols from instance_data so
        # edits (or device builds that update pins) land in the block diagram this build.
        svg_diagram = system_utils.refresh_block_diagram_placed_symbols(svg_diagram)

        def ensure_system_boundary_rect(svg_text):
            """
            Ensure a bottom-most ``#boundary`` rectangle exists under ``*-contents-start``.

            Default geometry is ``0,0`` → ``1008×768`` (10.5 in × 8 in at 96 dpi), black
            stroke, no fill. Returns the (possibly updated) SVG text. Idempotent when a
            ``rect#boundary`` is already present. Does not rewrite the rest of the file.
            """
            boundary_rect_markup = (
                '<rect id="boundary" class="system-boundary" x="0" y="0" width="1008" '
                'height="768" fill="none" stroke="#000000" stroke-width="1" '
                'pointer-events="none"/>'
            )
            if not svg_text or not str(svg_text).strip():
                return svg_text
            tree = block_diagram_utils._parse_block_diagram_svg_string(svg_text)
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
                if (
                    block_diagram_utils._svg_local_tag(child.tag) == "rect"
                    and (child.get("id") or "") == "boundary"
                ):
                    existing = child
                    break

            if existing is not None:
                kids = list(contents_start)
                if kids and kids[0] is existing:
                    return svg_text
                span = block_diagram_utils.find_svg_element_span(svg_text, "boundary")
                if span is None or not contents_id:
                    return svg_text
                start, _open_end, _close_start, end = span
                rect_xml = svg_text[start:end]
                without = svg_text[:start] + svg_text[end:]
                moved = block_diagram_utils.insert_after_svg_element_open(
                    without, contents_id, rect_xml
                )
                return without if moved is None else moved

            if not contents_id:
                return svg_text
            inserted = block_diagram_utils.insert_after_svg_element_open(
                svg_text, contents_id, boundary_rect_markup
            )
            return svg_text if inserted is None else inserted

        svg_diagram = ensure_system_boundary_rect(svg_diagram)
        svg_diagram = system_utils.apply_block_diagram_trace_overlays(svg_diagram)

        if svg_diagram != original_svg:
            fileio.atomic_write_text(bd_path, svg_diagram)

        from harnice.utils import physical_assembly

        # Instance folders are final at this point. Rewrite the assembly so a
        # device that no longer has instance data is not left in assembly.step.
        physical_assembly.sync_assembly()
        physical_assembly.sync_mating_connector_nodes()
    except Exception:
        pdf_drawings_utils.watermark_existing_pdfs_incomplete_rebuild()
        raise

    print("\nSystem built successfully!\n")
