import os
import re
import shutil
import filecmp
import json
from harnice import fileio
from harnice.lists import instances_list, library_history, rev_history

def _mpn_from_instances(instance_name):
    try:
        return (instances_list.attribute_of(instance_name, "mpn") or "").strip()
    except Exception:
        return ""


def _svg_text_as_pulled(library_svg_text, mpn, instance_name):
    """Apply the same SVG id rewrite ``pull`` does when seeding an instance copy."""
    if not mpn or not instance_name:
        return library_svg_text
    return library_svg_text.replace(
        f"{mpn}-drawing-contents-start",
        f"{instance_name}-contents-start",
    ).replace(
        f"{mpn}-drawing-contents-end",
        f"{instance_name}-contents-end",
    )


def instance_modified_vs_library(destination_directory, instance_name):
    """True if editable instance files differ from ``lib``.

    Compares the same files ``pull`` copies into the instance folder. SVG copies
    are compared after the MPN→instance-name contents-id rewrite so an untouched
    pull does not count as modified.
    """
    inst_dir = destination_directory or ""
    instance_name = (instance_name or "").strip()
    if not instance_name or not os.path.isdir(inst_dir):
        return False
    lib_root = os.path.join(inst_dir, fileio.LIBRARY_USED_DIR)
    if not os.path.isdir(lib_root):
        return False
    try:
        rev_names = sorted(
            name
            for name in os.listdir(lib_root)
            if not name.startswith(".")
            and os.path.isdir(os.path.join(lib_root, name))
        )
    except OSError:
        return False
    for rev_name in rev_names:
        rev_path = os.path.join(lib_root, rev_name)
        mpn = _mpn_from_instances(instance_name)
        try:
            filenames = os.listdir(rev_path)
        except OSError:
            continue
        for filename in filenames:
            if filename.startswith(".") or filename == ".DS_Store":
                continue
            lib_file = os.path.join(rev_path, filename)
            if os.path.isdir(lib_file):
                continue
            editable = os.path.join(inst_dir, filename)
            if not os.path.isfile(editable):
                continue
            if _editable_file_differs_from_library(
                lib_file, editable, mpn, instance_name
            ):
                return True
    return False


def _editable_file_differs_from_library(lib_file, editable_file, mpn, instance_name):
    if lib_file.endswith(".svg") and editable_file.endswith(".svg"):
        try:
            with open(lib_file, encoding="utf-8") as f:
                lib_text = f.read()
            with open(editable_file, encoding="utf-8") as f:
                edit_text = f.read()
        except (OSError, UnicodeDecodeError):
            return not filecmp.cmp(lib_file, editable_file, shallow=False)
        return _svg_text_as_pulled(lib_text, mpn, instance_name) != edit_text
    try:
        return not filecmp.cmp(lib_file, editable_file, shallow=False)
    except OSError:
        return True


def _lib_used_rev(destination_directory):
    lib_root = os.path.join(destination_directory or "", fileio.LIBRARY_USED_DIR)
    if not os.path.isdir(lib_root):
        return ""
    try:
        rev_names = sorted(
            name
            for name in os.listdir(lib_root)
            if not name.startswith(".")
            and os.path.isdir(os.path.join(lib_root, name))
        )
    except OSError:
        return ""
    if not rev_names:
        return ""
    parts = fileio.revision_folder_parts(os.path.join(lib_root, rev_names[0]))
    return parts[1] if parts else ""


def _library_rev_is_newer(latest, used):
    latest = "" if latest is None else str(latest).strip()
    used = "" if used is None else str(used).strip()
    if not latest or not used:
        return False
    if latest.isdigit() and used.isdigit():
        return int(latest) > int(used)
    return not rev_history._revs_equivalent(latest, used)


def instance_newer_library_rev_available(
    destination_directory,
    instance_name,
    import_row=None,
    latest_rev_cache=None,
):
    """True if the source library has a newer revision than this instance uses.

    Prefers a live look at the local library clone. Falls back to
    ``lib_latest_rev`` / ``lib_rev_used_here`` from the last build if the
    library path cannot be resolved.
    """
    row = import_row or {}
    used = _lib_used_rev(destination_directory) or str(
        row.get("lib_rev_used_here") or ""
    ).strip()
    mpn = str(row.get("mpn") or "").strip() or _mpn_from_instances(instance_name)
    lib_repo = str(row.get("lib_repo") or "").strip()
    lib_subpath = str(row.get("lib_subpath") or "").strip()
    latest = ""
    cache_key = (lib_repo, lib_subpath, mpn)
    if latest_rev_cache is not None and cache_key in latest_rev_cache:
        latest = latest_rev_cache[cache_key] or ""
    elif mpn and lib_repo:
        try:
            if lib_repo == "local":
                lib_root = os.path.join(fileio.part_directory(), "library")
            else:
                lib_root = get_local_path(
                    lib_repo,
                    instance_name=instance_name,
                    mpn=mpn,
                    lib_subpath=lib_subpath,
                )
            source_lib_path = os.path.join(lib_root, lib_subpath, mpn)
            if os.path.isdir(source_lib_path):
                _folder, _rev, highest, _tip = resolve_mpn_revision(
                    source_lib_path, mpn
                )
                latest = highest
        except (ValueError, FileNotFoundError, OSError, TypeError, RuntimeError):
            latest = ""
        if latest_rev_cache is not None:
            latest_rev_cache[cache_key] = latest
    if not latest:
        latest = str(row.get("lib_latest_rev") or "").strip()
    return _library_rev_is_newer(latest, used)


def resolve_mpn_revision(source_lib_path, mpn, lib_rev_used_here=None):
    """
    Choose which ``rev*`` folder to use under ``source_lib_path``.

    Same tip / explicit-rev rules as ``pull``: if ``lib_rev_used_here`` is blank,
    pick the library tip (max numeric suffix if all digit, else latest mtime);
    otherwise resolve the requested suffix.

    **Returns:**
    - `tuple`: ``(source_folder_name, rev_to_use, highest_source_rev, tip_folder)``

    **Raises:**
    - `FileNotFoundError`: If no revision folders exist, or the requested rev is missing.
    """
    def list_revision_dirs():
        mpn_l = (mpn or "").lower()
        out = []
        for name in os.listdir(source_lib_path):
            path = os.path.join(source_lib_path, name)
            parts = fileio.revision_folder_parts(path)
            if parts is None:
                continue
            pn, suf = parts
            if pn.lower() != mpn_l:
                continue
            out.append((name, suf))
        return out

    def pick_tip(entries):
        suffixes = [s for _, s in entries]
        if all(s.isdigit() for s in suffixes):
            best_n = max(int(s) for s in suffixes)
            for fn, s in entries:
                if s.isdigit() and int(s) == best_n:
                    return fn, s
            raise RuntimeError("revision folder list inconsistency")
        best = max(
            entries,
            key=lambda e: os.path.getmtime(os.path.join(source_lib_path, e[0])),
        )
        return best[0], best[1]

    entries = list_revision_dirs()
    if not entries:
        raise FileNotFoundError(
            f"No revision folders found for {mpn} in {source_lib_path}"
        )
    tip_folder, highest_source_rev = pick_tip(entries)

    if lib_rev_used_here:
        rev_to_use = str(lib_rev_used_here).strip()
        if len(rev_to_use) >= 3 and rev_to_use[:3].lower() == "rev":
            rev_to_use = rev_to_use[3:].lstrip()
        source_folder_name = next(
            (
                fn
                for fn, s in entries
                if rev_history._revs_equivalent(s, rev_to_use)
            ),
            None,
        )
        if not source_folder_name:
            raise FileNotFoundError(
                f"No revision folder for {mpn!r} rev {rev_to_use!r} under {source_lib_path}"
            )
        return source_folder_name, rev_to_use, highest_source_rev, tip_folder

    return tip_folder, highest_source_rev, highest_source_rev, tip_folder


def pull(
    input_dict,
    update_instances_list=True,
    destination_directory=None,
    record_library_history=True,
    include_filenames=None,
    replace_destination=False,
):
    """
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
    """
    # throw errors if required fields are blank
    if input_dict.get("instance_name") in [None, ""]:
        raise ValueError(
            f"when importing {input_dict.get('instance_name')} 'instance_name' is required but blank"
        )
    if input_dict.get("lib_repo") in [None, ""]:
        raise ValueError(
            f"when importing {input_dict.get('instance_name')} 'lib_repo' is required but blank"
        )
    if input_dict.get("mpn") in [None, ""]:
        raise ValueError(
            f"when importing {input_dict.get('instance_name')} 'mpn' is required but blank"
        )

    # determine destination directory
    if destination_directory is None:
        destination_directory = os.path.join(
            fileio.dirpath(None),
            "instance_data",
            input_dict.get("item_type"),
            input_dict.get("instance_name"),
        )
    os.makedirs(destination_directory, exist_ok=True)

    # ``lib_repo`` in instances / library history is the traceable URL (or
    # ``"local"``). Resolve a filesystem root separately for the copy.
    lib_repo_key = input_dict.get("lib_repo")
    if lib_repo_key == "local":
        lib_local_root = os.path.join(fileio.part_directory(), "library")
    else:
        lib_local_root = get_local_path(
            lib_repo_key,
            instance_name=input_dict.get("instance_name"),
            mpn=input_dict.get("mpn"),
            lib_subpath=input_dict.get("lib_subpath", ""),
        )

    # determine source library path
    source_lib_path = os.path.join(
        lib_local_root,
        input_dict.get("lib_subpath", ""),
        input_dict.get("mpn"),
    )
    if not os.path.isdir(source_lib_path):
        raise FileNotFoundError(
            f"No library part {input_dict.get('mpn')!r} at {source_lib_path}"
        )

    # === Find revision folders and choose tip or explicit rev (see resolve_mpn_revision)
    source_folder_name, rev_to_use, highest_source_rev, _tip_folder = resolve_mpn_revision(
        source_lib_path,
        input_dict.get("mpn"),
        input_dict.get("lib_rev_used_here"),
    )

    # === Import library contents freshly every time
    lib_used_path = os.path.join(destination_directory, fileio.LIBRARY_USED_DIR)
    os.makedirs(lib_used_path, exist_ok=True)

    lib_used_rev_path = os.path.join(
        lib_used_path, fileio.revision_folder_name(rev_to_use)
    )
    if os.path.exists(lib_used_rev_path):
        shutil.rmtree(lib_used_rev_path)

    source_lib_rev_path = os.path.join(source_lib_path, source_folder_name)

    selected_filenames = None
    if include_filenames is not None:
        selected_filenames = tuple(dict.fromkeys(str(name) for name in include_filenames))
        for filename in selected_filenames:
            if not filename or os.path.basename(filename) != filename:
                raise ValueError(
                    f"include_filenames entries must be top-level filenames: {filename!r}"
                )
            source_file = os.path.join(source_lib_rev_path, filename)
            if not os.path.isfile(source_file):
                raise FileNotFoundError(
                    f"Required library file {filename!r} not found in {source_lib_rev_path}"
                )

    if replace_destination:
        shutil.rmtree(destination_directory, ignore_errors=True)
        os.makedirs(destination_directory, exist_ok=True)

    # .DS_Store is Finder noise, never library content, and would otherwise be laid
    # down as an editable file and counted when detecting local modifications.
    if selected_filenames is None:
        shutil.copytree(
            source_lib_rev_path,
            lib_used_rev_path,
            ignore=shutil.ignore_patterns(".DS_Store"),
        )
    else:
        os.makedirs(lib_used_rev_path, exist_ok=True)
        for filename in selected_filenames:
            shutil.copy2(
                os.path.join(source_lib_rev_path, filename),
                os.path.join(lib_used_rev_path, filename),
            )

    # === Copy editable files into the editable directory only if not already present
    Modified = False
    for filename in os.listdir(lib_used_rev_path):
        lib_used_do_not_edit_file = os.path.join(lib_used_rev_path, filename)

        # the editable layer is flat. parts that carry subtrees of their own (a harness
        # brings its instance_data and networks) keep them under lib.
        if os.path.isdir(lib_used_do_not_edit_file):
            continue
        if filename.startswith(".") or filename == ".DS_Store":
            continue

        editable_file_path = os.path.join(destination_directory, filename)
        if not os.path.exists(editable_file_path):
            shutil.copy2(lib_used_do_not_edit_file, editable_file_path)

            # special rules for copying svg
            if filename.endswith(".svg"):
                with open(editable_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace(
                    f"{input_dict.get('mpn')}-drawing-contents-start",
                    f"{input_dict.get('instance_name')}-contents-start",
                ).replace(
                    f"{input_dict.get('mpn')}-drawing-contents-end",
                    f"{input_dict.get('instance_name')}-contents-end",
                )
                with open(editable_file_path, "w", encoding="utf-8") as f:
                    f.write(content)

        else:
            # Compare the existing editable file and the library version
            if not filecmp.cmp(
                lib_used_do_not_edit_file, editable_file_path, shallow=False
            ):
                Modified = Modified or True

    # === Load revision row from revision history TSV in source library ===
    revhistory_path = os.path.join(
        source_lib_path, f"{input_dict.get('mpn')}-revision_history.tsv"
    )
    revhistory_row = rev_history.info(rev=rev_to_use, path=revhistory_path)

    attributes_data = {}
    
    try:
        with open(
            os.path.join(destination_directory, "attributes.json"),
            "r",
            encoding="utf-8",
        ) as f:
            attributes_data = json.load(f)

        csys_children = attributes_data.get("csys_children") or {}
        tools = attributes_data.get("tools") or []
        build_notes = attributes_data.get("build_notes") or []

    except Exception:
        csys_children = {}
        tools = []
        build_notes = []

    update_contents = {
        "mpn": input_dict.get("mpn"),
        "item_type": input_dict.get("item_type"),
        "csys_children": csys_children,
        "lib_repo": lib_repo_key,
        "lib_subpath": input_dict.get("lib_subpath"),
        "lib_desc": revhistory_row.get("desc"),
        "lib_latest_rev": highest_source_rev,
        "lib_rev_used_here": rev_to_use,
        "lib_status": revhistory_row.get("status"),
        "lib_releaseticket": revhistory_row.get("releaseticket"),
        "lib_datestarted": revhistory_row.get("datestarted"),
        "lib_datemodified": revhistory_row.get("datemodified"),
        "lib_datereleased": revhistory_row.get("datereleased"),
        "lib_drawnby": revhistory_row.get("drawnby"),
        "lib_checkedby": revhistory_row.get("checkedby"),
        "lib_tools": tools,
        "lib_build_notes": build_notes,
        "project_editable_lib_modified": Modified,
        "attributes_json": attributes_data,
    }
    if "device_configuration" in input_dict:
        update_contents["device_configuration"] = (
            input_dict.get("device_configuration") or ""
        )

    if update_instances_list:
        try:
            instances_list.modify(input_dict.get("instance_name"), update_contents)
        except ValueError:
            instances_list.new_instance(
                input_dict.get("instance_name"), update_contents
            )

    if record_library_history:
        library_history.append(input_dict.get("instance_name"), update_contents)

    if (input_dict.get("item_type") or "").strip() == "system":
        _import_system_channel_map(lib_used_rev_path, destination_directory)

    return destination_directory


def _import_system_channel_map(lib_used_rev_path, destination_directory):
    """Copy an imported system's channel map onto the instance.

    ``maps/channels.tsv`` next to the instance's other files is the source of
    truth for the downstream system. It is refreshed from the revision just
    pulled. Nested subsystems keep the channel maps already stored in that
    revision; those are not rewritten here.
    """
    src = os.path.join(lib_used_rev_path, "maps", "channels.tsv")
    if not os.path.isfile(src):
        return
    dest = os.path.join(destination_directory, "maps", "channels.tsv")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)


def resolve_source_library_revision_folder(input_dict):
    """
    Absolute path to the selected MPN revision directory in the library
    (e.g. ``.../MPN/rev3``). Uses the same revision selection rules as :func:`pull`.
    ``input_dict`` must include ``lib_repo``, ``mpn``, and may include ``lib_subpath``,
    ``lib_rev_used_here``.

    **Returns:**
    - `tuple`: ``(rev_folder_path, rev_suffix)``
    """
    if not input_dict.get("mpn"):
        raise ValueError("mpn is required")
    if input_dict.get("lib_repo") == "local":
        lib_repo = os.path.join(fileio.part_directory(), "library")
    else:
        lib_repo = get_local_path(
            input_dict.get("lib_repo"),
            instance_name=input_dict.get("instance_name"),
            mpn=input_dict.get("mpn"),
            lib_subpath=input_dict.get("lib_subpath", ""),
        )

    source_lib_path = os.path.join(
        lib_repo,
        input_dict.get("lib_subpath", ""),
        input_dict.get("mpn"),
    )
    if not os.path.isdir(source_lib_path):
        raise FileNotFoundError(f"No library folder at {source_lib_path}")

    source_folder_name, rev_to_use, _highest, _tip = resolve_mpn_revision(
        source_lib_path,
        input_dict.get("mpn"),
        input_dict.get("lib_rev_used_here"),
    )
    return os.path.join(source_lib_path, source_folder_name), rev_to_use


def read_default_refdes_prefix_for_import(input_dict):
    """
    Read ``default_refdes`` from ``attributes.json`` in the library revision folder.

    Returns the prefix stripped to characters safe for the left side of an instance name
    (letters, digits, underscore), or ``DEVICE`` if missing/invalid.
    """
    try:
        folder, _rev = resolve_source_library_revision_folder(input_dict)
        candidates = [
            os.path.join(folder, "attributes.json"),
        ]
        for path in candidates:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = (data.get("default_refdes") or "").strip()
            if not raw:
                continue
            t = re.sub(r"[^A-Za-z0-9_]", "", raw)
            if t:
                return t
        if (input_dict.get("item_type") or "").strip() == "system":
            return "SYS"
        return "DEVICE"
    except Exception:
        if (input_dict.get("item_type") or "").strip() == "system":
            return "SYS"
        return "DEVICE"


def get_local_path(lib_repo, instance_name=None, mpn=None, lib_subpath=None):
    """
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
    """
    def lookup_error(*, empty_local=False):
        if instance_name is not None or mpn is not None or lib_subpath is not None:
            sub = "" if lib_subpath is None else lib_subpath
            if empty_local:
                return (
                    f"when importing instance {instance_name} (mpn: {mpn}, lib_subpath {sub}) "
                    f"found repository {lib_repo} in repository_locations.csv but no local path is set"
                )
            return (
                f"when importing instance {instance_name} (mpn: {mpn}, lib_subpath {sub}) "
                f"could not find repository {lib_repo} in repository_locations.csv"
            )
        if empty_local:
            return f"No local path found for '{lib_repo}'"
        return (
            f"'{lib_repo}' not found in repository locations. "
            f"Check your repository locations file at {csv_path}"
        )

    csv_path = fileio.path("repository locations")

    # ----------------------------------------------------
    # If file does not exist, auto-generate with default
    # ----------------------------------------------------
    if not os.path.exists(csv_path):
        # Determine base directory of the Harnice repo
        # (__file__) → .../harnice/utils/library_utils.py
        # dirname 3 times → repo root
        repo_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
        )

        default_local_path = os.path.join(repo_root, "harnice-library-public")

        # Ensure the directory exists for the CSV
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

        with open(csv_path, "w", encoding="utf-8") as f:
            # Normalize the default path to ensure correct separators
            normalized_path = os.path.normpath(default_local_path)
            f.write(f"https://github.com/harnice/harnice-general-library,{normalized_path}\n")

        print(f"[harnice] Created '{csv_path}'")
        print(f"[harnice] Default library-public location: {default_local_path}")

    # ----------------------------------------------------
    # Normal lookup (with BOM-safe decoding)
    # ----------------------------------------------------
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(",")
            if len(parts) < 2:
                continue

            url = parts[0].strip()
            local = parts[1].strip()

            # Case-insensitive match
            if url.lower() == lib_repo.lower().strip():
                if not local:
                    raise ValueError(lookup_error(empty_local=True))
                # Expand user directory (~) and normalize path separators for current platform
                expanded_path = os.path.expanduser(local)
                # Normalize separators - os.path.normpath() converts forward slashes to
                # backslashes on Windows, ensuring proper path format
                return os.path.normpath(expanded_path)

    raise ValueError(lookup_error())
