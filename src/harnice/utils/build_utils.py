import ast
import inspect
import json
import math
import os

from harnice import fileio
from harnice import build_sandbox
from harnice.lists import library_history
from harnice.utils import library_utils



def run_macro(
    macro_part_number,
    lib_subpath,
    lib_repo,
    artifact_id,
    base_directory=None,
    rerun=False,
    **kwargs,
):
    """
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
    """
    if artifact_id is None:
        raise ValueError("artifact_id is required")
    if macro_part_number is None:
        raise ValueError("macro_part_number is required")
    if lib_repo is None:
        raise ValueError("lib_repo is required")

    already_recorded = any(
        instance.get("instance_name") == artifact_id
        for instance in library_history.read()
    )
    if already_recorded and not rerun:
        raise ValueError(f"Macro with ID {artifact_id} already exists")

    if base_directory is None:
        base_directory = os.path.join("instance_data", "macro", artifact_id)

    os.makedirs(fileio.dirpath(None, base_directory=base_directory), exist_ok=True)

    library_utils.pull(
        {
            "mpn": macro_part_number,
            "lib_repo": lib_repo,
            "lib_subpath": lib_subpath,
            "item_type": "macro",
            "instance_name": artifact_id,
        },
        destination_directory=fileio.dirpath(None, base_directory=base_directory),
        update_instances_list=False,
        # Re-runs already have a history row; appending again would raise.
        record_library_history=not already_recorded,
    )

    script_path = os.path.join(
        fileio.dirpath(None, base_directory=base_directory), f"{macro_part_number}.py"
    )

    # always pass the basics, but let kwargs override/extend
    init_globals = {
        "artifact_id": artifact_id,
        "artifact_path": base_directory,
        "base_directory": base_directory,
        **kwargs,  # merges/overrides
    }

    build_sandbox.run_path(script_path, run_name="__main__", init_globals=init_globals)


def lookup_outputcsys_from_lib_used(instance, outputcsys, base_directory=None):
    """
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
    """
    if outputcsys == "origin":
        return 0, 0, 0

    attributes_path = os.path.join(
        fileio.dirpath(None, base_directory=base_directory),
        "instance_data",
        instance.get("item_type"),
        instance.get("instance_name"),
        "attributes.json",
    )

    try:
        with open(attributes_path, "r", encoding="utf-8") as f:
            attributes_data = json.load(f)
    except FileNotFoundError:
        return 0, 0, 0

    csys_children = attributes_data.get("csys_children", {})

    if outputcsys not in csys_children:
        raise ValueError(
            f"Output coordinate system '{outputcsys}' not defined in {attributes_path}"
        )

    child_csys = csys_children[outputcsys]

    # Extract values with safe numeric defaults
    x = child_csys.get("x", 0)
    y = child_csys.get("y", 0)
    angle = child_csys.get("angle", 0)
    distance = child_csys.get("distance", 0)
    rotation = child_csys.get("rotation", 0)

    # Convert angle to radians if it's stored in degrees
    angle_rad = math.radians(angle)

    # Apply translation based on distance + angle
    x = x + distance * math.cos(angle_rad)
    y = y + distance * math.sin(angle_rad)

    return x, y, rotation


def run_instruction_from_relative(
    function_name,
    relative_mpn,
    relative_repo,
    relative_subpath,
    relative_rev,
    **kwargs,
):
    """
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
    """
    from harnice import state

    name = (function_name or "").strip()
    if not name or not name.isidentifier():
        raise ValueError(f"Invalid function_name: {function_name!r}")

    relative_mpn = (relative_mpn or "").strip()
    relative_rev = (relative_rev or "").strip()
    if len(relative_rev) >= 3 and relative_rev[:3].lower() == "rev":
        relative_rev = relative_rev[3:].lstrip()
    relative_repo = (relative_repo or "").strip()
    relative_subpath = (relative_subpath or "").strip()
    if not relative_mpn or not relative_rev:
        raise ValueError("relative_mpn and relative_rev are required")
    if not relative_repo:
        raise ValueError("relative_repo is required")

    relative_rev_dir = os.path.join(
        library_utils.get_local_path(relative_repo),
        relative_subpath,
        relative_mpn,
        fileio.revision_folder_name(relative_rev),
    )
    relative_id = f"{relative_mpn}-rev{relative_rev}"
    if not os.path.isdir(relative_rev_dir):
        raise FileNotFoundError(
            f"When running instruction {name} from relative {relative_id}, "
            f"could not find relative at {relative_rev_dir}"
        )

    script_path = os.path.join(relative_rev_dir, "build.py")
    if not os.path.isfile(script_path):
        raise FileNotFoundError(
            f"When running instruction {name} from relative {relative_id}, "
            f"could not find relative at {script_path}"
        )

    # Load only imports, defs, and literal data — do not re-run the relative's build.
    with open(script_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=script_path)
    kept = []
    for node in tree.body:
        if isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            kept.append(node)
        elif isinstance(node, ast.Assign):
            if not any(isinstance(child, (ast.Call, ast.Await)) for child in ast.walk(node.value)):
                kept.append(node)
        elif isinstance(node, ast.AnnAssign) and (
            node.value is None
            or not any(isinstance(child, (ast.Call, ast.Await)) for child in ast.walk(node.value))
        ):
            kept.append(node)
    module = ast.Module(body=kept, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = build_sandbox.public_globals()
    ns.update(
        {
            "__name__": "parent_build_instructions",
            "__file__": script_path,
            "__package__": None,
        }
    )
    exec(compile(module, script_path, "exec"), ns)

    fn = ns.get(name)
    if fn is None:
        raise ValueError(
            "Build instruction from relative not found. Either remove the "
            "caller from this project's build instructions, or navigate to "
            "the relative project and write a function "
            f"(def {name}) using standard Python terminology."
        )
    if not callable(fn):
        raise ValueError(
            f"{name!r} in {relative_mpn}-{relative_rev} build instructions is not callable"
        )

    call_kwargs = {
        "relative_mpn": relative_mpn,
        "relative_rev": relative_rev,
        "relative_repo": relative_repo,
        "relative_subpath": relative_subpath,
    }
    try:
        call_kwargs["caller_pn"] = state.partnumber("pn")
        call_kwargs["caller_rev"] = state.partnumber("rev")
    except (NameError, ValueError, AttributeError):
        pass
    try:
        call_kwargs["caller_harness"] = state.harness
    except (NameError, AttributeError):
        pass
    call_kwargs.update(kwargs)

    sig = inspect.signature(fn)
    if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        call_kwargs = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
    result = fn(**call_kwargs)
    print(f"Harnice: ran {name} from {relative_mpn}-{relative_rev}")
    return result


def default_contents(filename, replacements=None):
    import harnice
    from harnice.runtime import bundled_defaults_dir

    bundled = bundled_defaults_dir()
    if bundled is not None:
        path = os.path.join(str(bundled), filename)
    else:
        path = os.path.join(os.path.dirname(harnice.__file__), "defaults", filename)

    with open(path, "r") as f:
        content = f.read()

    if replacements:
        for key, value in replacements.items():
            content = content.replace("{" + key + "}", str(value))

    return content
