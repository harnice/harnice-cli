# Library Utilities
---
##Commands
*These functions are already available in build instructions as `library_utils`. Use them as written.*
??? info "`library_utils.pull(input_dict, update_instances_list=True, destination_directory=None, record_library_history=True, include_filenames=None, replace_destination=False)`"

    Imports a part from the library into the project.
    
    Copies a part (device, connector, cable, etc.) from the library repository into
    the project's `instance_data` directory. Handles revision selection, file copying,
    and updating the instances list and library history. The function:
    
    1. Validates required fields (`instance_name`, `lib_repo`, `mpn`)
    2. Determines which revision to use (specified or latest available)
    3. Copies the library revision to `lib`
    4. Copies editable files to the instance directory (only if not already present)
    5. Updates the instances list with library metadata
    6. Records the import in library history
    
    When ``include_filenames`` is provided, only those top-level files are copied
    into both the library snapshot and editable layer. ``replace_destination``
    removes the previous imported destination after the source revision and
    requested files have been validated.
    
    A system import also copies ``maps/channels.tsv`` to the instance. That file
    is the source of truth for a parent system's hierarchical channel map.
    
    **Args:**
    - `input_dict` (dict): Dictionary containing part information with required keys:
        - `instance_name` (str): Name for this instance in the project
        - `lib_repo` (str): Library repository URL or `"local"` for local library
        - `mpn` (str): Manufacturer part number
        - `item_type` (str): Type of item (device, connector, cable, etc.)
        - `lib_subpath` (str, optional): Subpath within the library
        - `lib_rev_used_here` (str, optional): Specific revision to use (e.g., `"1"`, `"rev1"`, `"A"`)
    - `update_instances_list` (bool, optional): If `True`, updates the instances list with
        library metadata. Defaults to `True`.
    - `destination_directory` (str, optional): Custom destination directory. If `None`,
        defaults to `instance_data/{item_type}/{instance_name}`.
    - `record_library_history` (bool, optional): If `True`, appends to library history.
        Set to `False` for scratch/temp imports (e.g. GUI place preview).
    - `include_filenames` (iterable[str] | None, optional): Restrict the imported
        payload to these top-level files.
    - `replace_destination` (bool, optional): Replace the destination rather than
        retaining existing editable files.
    
    **Returns:**
    - `str`: Path to the destination directory where the part was imported.
    
    **Raises:**
    - `ValueError`: If required fields (`lib_repo`, `mpn`, `item_type`) are blank.
    - `FileNotFoundError`: If no revision folders are found for the part number in the library.

??? info "`library_utils.get_local_path(lib_repo, instance_name=None, mpn=None, lib_subpath=None)`"

    Looks up the local filesystem path for a library repository URL.
    
    Reads the `repository_locations.csv` file to find the mapping between a library
    repository URL and its local filesystem path. If the CSV file doesn't exist,
    it creates one with a default entry for the `harnice-library-public` repository.
    
    The lookup is case-insensitive. The local path is expanded (e.g., `~` is expanded
    to the user's home directory).
    
    **Args:**
    - `lib_repo` (str): Library repository URL to look up (e.g.,
        `"https://github.com/harnice/harnice-general-library"`).
    - `instance_name` (str, optional): Instance being imported, included in lookup errors.
    - `mpn` (str, optional): Manufacturer part number being imported, included in lookup errors.
    - `lib_subpath` (str, optional): Library subpath being imported, included in lookup errors.
    
    **Returns:**
    - `str`: Local filesystem path to the library repository.
    
    **Raises:**
    - `ValueError`: If the library repository URL is not found in the CSV file,
        or if no local path is specified for the repository.

