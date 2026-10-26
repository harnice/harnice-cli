# Interacting with Post Harness Instances Lists

A list of every physical or notional thing, drawing element, or concept that includes instances added at the harness level, that represents a system

---
##Commands
*These functions are already available in build instructions as `post_harness_instances_list`. Use them as written.*
??? info "`post_harness_instances_list.rebuild()`"

    Use this when a system build needs the post-harness instances list rebuilt from the harnesses that were pushed and from system instances those harnesses do not cover.
    
    Build the 'post harness instances list' by merging instance data from:
      - Every ``instances.tsv`` under the system ``harnesses/`` directory
      - The system-level instances list for harnesses not covered by those files, and for
        instances with no harness
    
    Writes a clean TSV with INSTANCES_LIST_COLUMNS (plus any extra columns found).

??? info "`post_harness_instances_list.push(path_to_system_rev, system_pn_rev)`"

    Use this when a harness build needs its instances list copied into a system revision's harnesses folder.
    
    Copy this harness instances list into a system revision's harnesses folder.
    
    **Args:**
    - `path_to_system_rev`: Directory of the system revision. The instances list is copied to ``{path_to_system_rev}/harnesses/instances.tsv``.
    - `system_pn_rev`: System part-and-revision label, such as ``"mypart-rev1"``. The file is copied using ``path_to_system_rev``; pass the label of the system revision that directory belongs to.

