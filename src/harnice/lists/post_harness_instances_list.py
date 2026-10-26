import os
import csv
import shutil
from harnice import fileio
from harnice.lists import instances_list


def rebuild():
    """
    Use this when a system build needs the post-harness instances list rebuilt from the harnesses that were pushed and from system instances those harnesses do not cover.

    Build the 'post harness instances list' by merging instance data from:
      - Every ``instances.tsv`` under the system ``harnesses/`` directory
      - The system-level instances list for harnesses not covered by those files, and for
        instances with no harness

    Writes a clean TSV with INSTANCES_LIST_COLUMNS (plus any extra columns found).
    """

    post_harness_instances = []
    covered_harnesses = set()

    # Read system instances once; fallback paths reuse this in-memory copy.
    try:
        system_instances = instances_list.read()
    except FileNotFoundError:
        system_instances = []

    harnesses_dir = fileio.dirpath("harnesses")
    if os.path.isdir(harnesses_dir):
        for name in sorted(os.listdir(harnesses_dir)):
            if name != "instances.tsv":
                continue
            path = os.path.join(harnesses_dir, name)
            if not os.path.isfile(path):
                continue
            for instance in fileio.read_tsv(path):
                post_harness_instances.append(instance)
                harness = (instance.get("harness") or "").strip()
                if harness:
                    covered_harnesses.add(harness)

    seen_names = {
        inst.get("instance_name")
        for inst in post_harness_instances
        if inst.get("instance_name")
    }
    for system_instance in system_instances:
        harness = (system_instance.get("harness") or "").strip()
        name = system_instance.get("instance_name")
        if not name or name in seen_names:
            continue
        # Prefer pushed harness files for harnesses they already cover.
        if harness and harness in covered_harnesses:
            continue
        post_harness_instances.append(system_instance)
        seen_names.add(name)

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


def push(path_to_system_rev, system_pn_rev):
    """
    Use this when a harness build needs its instances list copied into a system revision's harnesses folder.

    Copy this harness instances list into a system revision's harnesses folder.

    **Args:**
    - `path_to_system_rev`: Directory of the system revision. The instances list is copied to ``{path_to_system_rev}/harnesses/instances.tsv``.
    - `system_pn_rev`: System part-and-revision label, such as ``"mypart-rev1"``. The file is copied using ``path_to_system_rev``; pass the label of the system revision that directory belongs to.
    """
    path_to_harness_dir_of_system = os.path.join(path_to_system_rev, "harnesses")
    shutil.copy(fileio.path("instances list"), path_to_harness_dir_of_system)
