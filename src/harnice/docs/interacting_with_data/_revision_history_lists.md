# Interacting with Revision History Lists
A record of every revision of a part, and its release status

---
##Columns 
*Columns are automatically generated when `rev_history.new()` is called. Additional columns are not supported and may result in an error when parsing.*

| Column | Description |
|--------|-------------|
| `project_type` | the harnice project type (e.g. "harness", "connector", "device", "system", "macro", "flagnote", "tblock") |
| `mfg` | who manufactures this (blank ok) |
| `pn` | name, part number, other identifier of this part. mfg+mpn combination must be unique within the library. |
| `desc` | a brief description of this project |
| `rev` | the revision of the part |
| `status` | "released", "obsolete", etc. Harnice will not build a revision if the status has text in this field as a form of protection. |
| `releaseticket` | many companies do this, but it's not required. |
| `library_repo` | auto-filled on build if the current working directory is discovered to be a library repository. |
| `library_subpath` | auto-filled on build if in a library repository; directories between the library root and the part number (used as lib_subpath when pulling) |
| `source_part_number` | harness only: system PN this harness was imported from |
| `source_revision` | harness only: system revision this harness was imported from |
| `source_lib_repo` | harness only: repository_locations.csv repo URL of that system |
| `source_subpath` | harness only: path from that library root to the system PN folder |
| `source_refdes` | harness only: harness refdes on the source system |
| `datestarted` | auto-filled to be the date when this part was first intialized |
| `datemodified` | updates to today's date upon build |
| `datereleased` | up to user to fill in as needed |
| `git_hash_of_harnice_src` | auto-filled, git hash of the harnice source code during the latest build |
| `drawnby` | auto-filled, the person who created the part |
| `checkedby` | the person who checked the part, blank ok |
| `revisionupdates` | a brief description of the changes made to this revision |
| `affectedinstances` | the instance names of the instances that were affected by this revision. can be referenced later by PDF builders and more. |
| `last_build` | "succeeded" or "failed" after the latest build of this revision; blank until first build |


---
##Commands
*These functions are already available in build instructions as `rev_history`. Use them as written.*
??? info "`rev_history.overwrite(content_dict)`"

    Overwrite a revision history entry.
    
    **Arguments:**
    
    - `content_dict` (dict): The content to overwrite the revision history entry with.
    - This should be a dictionary with the keys and values to overwrite.
    - The keys should be the column names, and the values should be the new values.
    - Some keys are protected and cannot be overwritten:
        - `"project_type"`
        - `"mfg"`
        - `"pn"`
        - `"rev"`
        - `"releaseticket"`
        - `"library_repo"`
        - `"library_subpath"`
        - `"datestarted"`
        - `"last_build"`
    
    The function will update the revision history file as referenced by the current project file structure.
    
    **Returns:**
    
    - `None`
    
    **Raises:**
    
    - `KeyError`: If a key is provided that is not in the COLUMNS list.
    - `KeyError`: If a protected key is provided.
    - `ValueError`: If the revision history file is not found.
    - `ValueError`: If the revision is not found in the revision history file.
    - `RuntimeError`: If `state.rev` is not set.

??? info "`rev_history.info(rev=None, path=None, field=None, all=False)`"

    Get information about a revision history entry.
    
    **Arguments:**
    
    - `rev` (str): The revision to get information about.
    - `path` (str): The path to the revision history file.
        - If not provided, the function will use the default path: `"revision history"`.
    - `field` (str): The field to get information about.
        - If not provided, the function will return the entire row.
        - If provided, the function will return the value of the field.
    - `all` (bool): If `True`, return all rows.
        - If not provided, the function will return the first row.
    
    **Returns:**
    
    - `dict`: The row of the revision history entry (when `field` is not provided).
    - `list`: A list of all rows in the revision history file (when `all=True`).
    - `str`: The value of the field (when `field` is provided).
    
    **Raises:**
    
    - `FileNotFoundError`: If the revision history file is not found.
    - `ValueError`: If the revision is not found in the revision history file.

??? info "`rev_history.initial_release_exists()`"

    Check if an initial release exists.
    
    **Arguments:**
    
    None
    
    **Returns:**
    
    - `bool`: `True` if a revision with the text `"INITIAL RELEASE"` in the `"revisionupdates"` field exists, `False` otherwise.

??? info "`rev_history.initial_release_desc()`"

    Get the description of the initial release.
    
    **Arguments:**
    
    None
    
    **Returns:**
    
    - `str`: The description of the revision which has `revisionupdates == 'INITIAL RELEASE'`.

??? info "`rev_history.update_datemodified()`"

    Update the `datemodified` field of the current revision with today's date.
    
    Called when the project is built (console **Build** or ``harnice -b``), not
    when the console merely mounts the project. Also refreshes ``drawnby`` and
    ``git_hash_of_harnice_src``.
    
    **Arguments:**
    
    None
    
    **Returns:**
    
    - `None`
    
    **Raises:**
    
    - `ValueError`: If the revision history file is not found.
    - `ValueError`: If the revision is not found in the revision history file.

??? info "`rev_history.update_last_build(result)`"

    Set ``last_build`` on the current revision to ``"succeeded"`` or ``"failed"``.
    
    Called when the project is built (console **Build** or ``harnice -b``).
    
    **Arguments:**
    
    - `result` (str): ``"succeeded"`` or ``"failed"``.
    
    **Returns:**
    
    - `None`
    
    **Raises:**
    
    - `ValueError`: If ``result`` is not ``"succeeded"`` or ``"failed"``.

??? info "`rev_history.new(ignore_project_type=False, path=None)`"

    Create a new revision history file.
    
    **Arguments:**
    
    - `ignore_project_type` (bool):
        - If `True`, the function will raise an error if `state.project_type` is not set first.
        - If `False`, the function will prompt the user to select a project type.
    - `path`: Revision-history file to create. Optional. Omit it to use the current project's revision history. Raises if that file already exists.
    
    **Returns:**
    
    - `None`
    
    **Raises:**
    
    - `ValueError`: If attempting to create a new revision history file without a project type when `ignore_project_type=True`.
    - `ValueError`: If attempting to overwrite an existing revision history file.

??? info "`rev_history.append(next_rev=None)`"

    Append a new revision history entry to the current revision history file.
    
    If the revision history file does not exist, the function will create it.
    If the revision history file exists, the function will append a new entry to the file.
    
    It will prompt the user for the following fields:
    
    - `project_type`: The project type of the part.
    - `desc`: The description of the part.
    - `revisionupdates`: What is the purpose of this revision?
    
    If the previous revision has a blank status, the function will prompt the user to obsolete it with a message.
    
    **Arguments:**
    
    - `next_rev` The next revision number to append.
    
    **Returns:**
    
    - `None`

??? info "`rev_history.part_family_append(content_dict, rev_history_path)`"

    Append a new revision history entry to the part family revision history file.
    
    Intended to be called by part family scripts only.
    
    The function will automatically update the following fields in the content dictionary:
    
    - `datemodified`: Set to today's date
    - `drawnby`: Set to the current user's name
    - `git_hash_of_harnice_src`: Set to the current git hash of the harnice source code
    
    If the revision history file does not exist, the function will create it.
    If an entry with the same revision number already exists, the function will update that entry.
    Otherwise, the function will append a new entry to the file.
    
    **Arguments:**
    
    - `content_dict` (dict): The content to append to the part family revision history file.
        - Should contain keys matching the `COLUMNS` list.
        - The `rev` key is used to determine if an entry already exists.
    - `rev_history_path` (str): The path to the part family revision history file.
    
    **Returns:**
    
    - `None`
    
    **Raises:**
    
    - `ValueError`: If the content dictionary contains invalid keys or missing required fields.

