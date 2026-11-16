# Interacting with Post Harness Instances Lists

A list of every physical or notional thing, drawing element, or concept that includes instances added at the harness level, that represents a system

---
##Commands
*These functions are already available in build instructions as `post_harness_instances_list`. Use them as written.*
??? info "`post_harness_instances_list.rebuild()`"

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

