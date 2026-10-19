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
            "hierarchical_channel_map.tsv": "hierarchical channel map",
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
        with open(fileio.path("block diagram"), "w", encoding="utf-8") as f:
            f.write(
                build_utils.default_contents(
                    "system_default_block_diagram.svg",
                    {"pn_rev": state.partnumber("pn-rev")},
                )
            )

    library_history.new()
    instances_list.new()

    # export bom and pull device/harness library files into instance_data
    # and the instances list (circuit-derived instances come later via
    # create_instances_from_circuits_list)
    system_utils.export_bom_from_block_diagram()
    system_utils._import_bom_devices(update_instances_list=True)
    system_utils.make_connector_list()
    channel_map.new()

    # run build instructions
    from harnice.utils import pdf_drawings_utils

    pdf_drawings_utils.reset_pdf_generator_runs()
    try:
        build_sandbox.run_path(fileio.path("build instructions"))

        # rebuild the post-harness instances list from all the linked-in harnesses
        post_harness_instances_list.rebuild()

        # compile the external ICD from external interface flag
        generate_icd()

        # Append derived trace overlays under ``applied-traces`` (``channel_traces`` / ``circuit_traces``).
        # Markup comes from ``block_diagram_harness_overlay_markup``; ``replace_block_diagram_applied_traces``
        # strips prior derived layers before writing.
        bd_path = fileio.path("block diagram")
        with open(bd_path, "r", encoding="utf-8") as f:
            svg_diagram = f.read()
        original_svg = svg_diagram
        # Always re-read placed device/subsystem symbols from instance_data so
        # edits (or device builds that update pins) land in the block diagram this build.
        svg_diagram = system_utils.refresh_block_diagram_placed_symbols(svg_diagram)
        svg_diagram = block_diagram_utils.ensure_system_boundary_rect(svg_diagram)

        instances = instances_list.read()
        channel_instances = []
        circuit_instances = []
        for instance in instances:
            if instance.get("item_type") == "harness-channel":
                channel_instances.append(instance)
            elif instance.get("item_type") == "circuit":
                circuit_instances.append(instance)

        channel_overlay = system_utils.block_diagram_harness_overlay_markup(
            channel_instances, include_multi_ch_junction_overlays=True
        )
        circuit_overlay = system_utils.block_diagram_harness_overlay_markup(
            circuit_instances, include_multi_ch_junction_overlays=False
        )
        svg_diagram = block_diagram_utils.replace_block_diagram_applied_traces(
            svg_diagram, channel_overlay, circuit_overlay
        )

        if svg_diagram != original_svg:
            with open(bd_path, "w", encoding="utf-8") as f:
                f.write(svg_diagram)
    except Exception:
        pdf_drawings_utils.watermark_existing_pdfs_incomplete_rebuild()
        raise

    print("\nSystem built successfully!\n")
