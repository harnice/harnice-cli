# Interacting with Library History
A report of what was imported during the most recent build of the current project

---
##Columns 
*Columns are automatically generated when `library_history.new()` is called. Additional columns are not supported and may result in an error when parsing.*

| Column | Description |
|--------|-------------|
| `instance_name` | documentation needed |
| `mpn` | documentation needed |
| `item_type` | documentation needed |
| `lib_repo` | documentation needed |
| `lib_subpath` | documentation needed |
| `lib_desc` | documentation needed |
| `lib_latest_rev` | documentation needed |
| `lib_rev_used_here` | documentation needed |
| `lib_status` | documentation needed |
| `lib_releaseticket` | documentation needed |
| `lib_datestarted` | documentation needed |
| `lib_datemodified` | documentation needed |
| `lib_datereleased` | documentation needed |
| `lib_drawnby` | documentation needed |
| `lib_checkedby` | documentation needed |
| `project_editable_lib_modified` | documentation needed |


---
##Commands
*These functions are already available in build instructions as `library_history`. Use them as written.*
??? info "`library_history.new()`"

    Create an empty library-history file, replacing one that already exists.

??? info "`library_history.append(instance_name, instance_data)`"

    Record one library import in the library history.
    
    **Args:**
    - `instance_name`: Name for this import. Raises if that name is already in the history.
    - `instance_data`: Dict of library-history columns (``mpn``, ``item_type``, ``lib_repo``, ``lib_subpath``, and the ``lib_*`` metadata). ``instance_name`` in the dict is replaced by the ``instance_name`` argument. Missing columns are written blank.

