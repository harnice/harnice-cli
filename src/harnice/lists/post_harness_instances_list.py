import ast
import csv
import os
from harnice import fileio
from harnice.lists import instances_list


# Columns whose value is only unique inside one harness. Each is rewritten to
# ``{harness refdes}.{value}`` so instances pulled from different harnesses cannot
# collide once they share the system-level list.
NAMESPACED_COLUMNS = [
    "instance_name",
    "print_name",
    "segment_group",
    "connector_group",
    "channel_group",
    "circuit_id",
    "node_at_end_a",
    "node_at_end_b",
    "parent_csys_instance_name",
    "cable_group",
    "note_number",
    "note_parent",
]

# Same idea, but the cell holds a Python-literal list of instance names.
NAMESPACED_LIST_COLUMNS = [
    "note_affected_instances",
]

# File each imported harness keeps its instances in, under
# ``instance_data/harness/{refdes}/``.
HARNESS_INSTANCES_FILENAME = "instances.tsv"


def rebuild():
    """
    Rebuild the instances list to also append instances from every referenced harness design.

    Every instance on the system instances list is written first, unchanged. Then, for
    each harness on the BOM with ``design_exists`` set to ``TRUE`` ("Design exists"
    ticked on the harness), every instance on its imported
    ``instance_data/harness/{refdes}/instances.tsv`` is appended, with the columns in ``NAMESPACED_COLUMNS``
    and ``NAMESPACED_LIST_COLUMNS`` prefixed with ``{refdes}.`` and ``harness`` set to
    the refdes. The system's own circuits therefore remain in the list as the
    requirement, alongside the harness instances that implement them. Harnesses without
    "Design exists" ticked add nothing.

    Writes a clean TSV with INSTANCES_LIST_COLUMNS (plus any extra columns found).

    **Raises:**
    - `FileNotFoundError`: If "Design exists" is ticked on a harness but its design
      was not imported into ``instance_data``.
    - `ValueError`: If a namespaced column is not an instances list column, or if two
      instances end up sharing an ``instance_name``.
    """

    unknown_columns = [
        column
        for column in NAMESPACED_COLUMNS + NAMESPACED_LIST_COLUMNS
        if column not in instances_list.COLUMNS
    ]
    if unknown_columns:
        raise ValueError(
            "NAMESPACED_COLUMNS / NAMESPACED_LIST_COLUMNS name columns that are not on "
            f"the instances list: {unknown_columns}"
        )

    def namespaced(value, refdes):
        text = "" if value is None else str(value).strip()
        if not text:
            return ""
        return f"{refdes}.{text}"

    try:
        post_harness_instances = list(instances_list.read())
    except FileNotFoundError:
        post_harness_instances = []

    harness_refdes_list = sorted(
        (bom_row.get("device_refdes") or "").strip()
        for bom_row in fileio.read_tsv("bom")
        if (bom_row.get("harness") or "").strip().upper() == "TRUE"
        and (bom_row.get("design_exists") or "").strip().upper() == "TRUE"
    )

    for refdes in harness_refdes_list:
        # Only the top level of the harness folder is read, so the library
        # snapshot under ``lib/`` is ignored.
        path = os.path.join(
            fileio.dirpath("instance_data"), "harness", refdes, HARNESS_INSTANCES_FILENAME
        )
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Design exists is ticked for harness {refdes}, but no imported "
                f"design was found at {path}"
            )
        for instance in fileio.read_tsv(path):
            instance = dict(instance)
            for column in NAMESPACED_COLUMNS:
                instance[column] = namespaced(instance.get(column), refdes)
            for column in NAMESPACED_LIST_COLUMNS:
                text = (instance.get(column) or "").strip()
                try:
                    names = ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    names = None
                if text and isinstance(names, (list, tuple, set)):
                    instance[column] = repr([f"{refdes}.{name}" for name in names])
                else:
                    instance[column] = namespaced(text, refdes)
            # The refdes the harness is installed as replaces whatever the
            # harness's own build wrote here.
            instance["harness"] = refdes
            post_harness_instances.append(instance)

    seen_names = set()
    duplicate_names = set()
    for instance in post_harness_instances:
        name = instance.get("instance_name")
        if name in seen_names:
            duplicate_names.add(name)
        seen_names.add(name)
    if duplicate_names:
        raise ValueError(
            "Post harness instances list would contain duplicate instance names: "
            f"{sorted(duplicate_names)}"
        )

    # --- Determine fieldnames dynamically (COLUMNS first, then any unknown headers) ---
    all_keys = set()
    for instance in post_harness_instances:
        all_keys.update(instance.keys())
    fieldnames = list(instances_list.COLUMNS) + [
        k for k in sorted(all_keys) if k not in instances_list.COLUMNS
    ]

    # --- Write TSV file ---
    with open(
        fileio.path("post harness instances list"), "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for instance in post_harness_instances:
            writer.writerow({k: instance.get(k, "") for k in fieldnames})
