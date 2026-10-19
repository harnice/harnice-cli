# Build utilities
---
##Commands
*These functions are already available in build instructions as `build_utils`. Use them as written.*
??? info "`build_utils.run_macro(macro_part_number, lib_subpath, lib_repo, artifact_id, base_directory=None, rerun=False, **kwargs)`"

    Runs a macro script from the library with the given artifact ID.
    
    Imports a macro from the library and executes its Python script. The macro
    is pulled into a directory structure and then executed with the `artifact_id`
    and any additional keyword arguments passed as global variables.
    
    **Args:**
    - `macro_part_number` (str): Part number of the macro to run.
    - `lib_subpath` (str): Library subpath where the macro is located.
    - `lib_repo` (str): Library repository URL or `"local"` for local library.
    - `artifact_id` (str): Instance name for this macro run (like ``J1`` for a
        connector). Must be unique in library history unless `rerun` is True.
        Files land under `instance_data/macro/{artifact_id}/` by default.
    - `base_directory` (str, optional): Base directory for this macro instance. If `None`,
        defaults to `instance_data/macro/{artifact_id}`.
    - `rerun` (bool, optional): If `True`, allow running again when `artifact_id` is
        already in library history (skips the duplicate check and does not re-append
        history). Used by post-build steps such as PDF drawings.
    - `**kwargs`: Additional keyword arguments to pass as global variables to the macro script.
    
    **Raises:**
    - `ValueError`: If `artifact_id` is `None`, `macro_part_number` is `None`, `lib_repo` is `None`,
        or if a macro with the given `artifact_id` already exists in library history
        (when `rerun` is False).

??? info "`build_utils.lookup_outputcsys_from_lib_used(instance, outputcsys, base_directory=None)`"

    Looks up coordinate system transform from an instance's library attributes.
    
    Reads the instance's attributes JSON file to find the specified output coordinate
    system definition and returns its transform values. If the coordinate system is
    `"origin"`, returns zero transform.
    
    **Args:**
    - `instance` (dict): Instance dictionary containing `item_type` and `instance_name`.
    - `outputcsys` (str): Name of the output coordinate system to look up (`"origin"` returns zero transform).
    - `base_directory` (str, optional): Base directory path. If `None`, uses current working directory.
    
    **Returns:**
    - `tuple`: A tuple of `(x, y, rotation)` representing the coordinate system transform.
        Returns `(0, 0, 0)` if the coordinate system is `"origin"` or if the attributes
        file is not found.
    
    **Raises:**
    - `ValueError`: If the specified output coordinate system is not defined in the
        instance's attributes file.

??? info "`build_utils.run_instruction_from_relative(function_name, relative_mpn, relative_repo, relative_subpath, relative_rev, **kwargs)`"

    Imports a function from a relative project's build instructions and calls it here.
    
    Locates that revision with ``repository_locations.csv`` (``relative_repo``)
    plus ``relative_subpath`` and part number, loads
    ``build.py``, and calls
    ``function_name`` in the **caller's** working directory.
    
    Only imports, class/function definitions, and assignment of literal data are
    loaded from that file. Harnice list, utility, and channel-type modules are
    already in the namespace, so the relative does not need to import them.
    Top-level build steps (channel mapping, macros, …) are not re-run. Define
    the function at module scope on the relative, for example
    ``def connector_chooser():``.
    
    This is not a macro: no instance folder, no library-history row.
    
    **Args:**
    - `function_name` (str): Function defined on the relative's build instructions
        (e.g. ``"connector_chooser"``).
    - `relative_mpn` (str): Relative project's part number.
    - `relative_repo` (str): Library repository URL from ``repository_locations.csv``.
    - `relative_subpath` (str): Path from that library root to the relative PN folder
        (may be `""`).
    - `relative_rev` (str): Relative revision label as used in folder names (e.g. ``"rev1"``).
    - `**kwargs`: Extra arguments passed to the function if it accepts them.
    
    **Returns:**
    - The function's return value.
    
    **Raises:**
    - `ValueError`: If locator arguments or ``function_name`` are missing,
        the named attribute is not callable, or ``function_name`` is not
        defined on the relative. Missing functions tell you to either
        remove the caller or add ``def {function_name}`` on the relative.
    - `FileNotFoundError`: If the relative revision folder or build-instructions file
        is missing. The message names the instruction, the relative, and the path.

