import os
import os.path
import datetime
import shutil
import csv
import json
import re
import subprocess
import sys
from harnice import state

# standard punctuation:
#  .  separates between name hierarchy levels
#  _  means nothing, basically a space character
#  -  if multiple instances are found at the same hierarchy level with the same name,
# this separates name from unique instance identifier

# Read-only copy of the library revision a pull used, inside an instance folder.
LIBRARY_USED_DIR = "lib"


def harnice_root():
    """Return the Harnice user-data directory on this computer."""
    from harnice.runtime import user_data_dir

    return str(user_data_dir())


# ``rev1``, ``rev11``, ``revA``. Avoid matching ordinary names like ``review``.
_SHORT_REV_FOLDER_RE = re.compile(r"^rev([0-9]+|[A-Za-z])$")


def revision_folder_parts(path=None):
    """Return ``(pn, rev_suffix)`` if ``path`` is a ``rev{rev}`` folder, else ``None``.

    Part number is the parent folder name.
    """
    folder = os.path.normpath(os.path.abspath(path or os.getcwd()))
    name = os.path.basename(folder)
    parent = os.path.basename(os.path.dirname(folder))
    match = _SHORT_REV_FOLDER_RE.fullmatch(name)
    if match:
        return parent, match.group(1)
    return None


def revision_folder_name(rev):
    """Directory name for a revision: ``rev{rev}``."""
    return f"rev{rev}"


def list_revision_folders(part_dir):
    """Return ``{rev_suffix: abs_path}`` for revision folders under ``part_dir``."""
    found = {}
    try:
        names = os.listdir(part_dir)
    except OSError:
        return found
    for name in names:
        folder = os.path.join(part_dir, name)
        if not os.path.isdir(folder):
            continue
        parts = revision_folder_parts(folder)
        if parts is None:
            continue
        _pn, suffix = parts
        found[str(suffix)] = os.path.normpath(os.path.abspath(folder))
    return found


def is_revision_folder(path=None):
    """True if ``path`` (default cwd) is a ``rev{N}`` folder."""
    return revision_folder_parts(path) is not None


def _stdin_can_prompt():
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _should_prompt_for_identity_files():
    from harnice.runtime import is_standalone_app

    if is_standalone_app():
        return False
    return _stdin_can_prompt()


def repository_locations_path():
    """Absolute path to ``repository_locations.csv`` (the file may not exist yet)."""
    return os.path.join(harnice_root(), "repository_locations.csv")


def read_repository_locations():
    """Return ``[{repo_url, local_path}, ...]`` from ``repository_locations.csv``.

    Missing file → empty list. Lines starting with ``#`` and a ``repo_url`` header
    row are skipped. Handles files written with or without a header.
    """
    path = repository_locations_path()
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for parts in csv.reader(f):
            if not parts:
                continue
            url = (parts[0] or "").strip()
            if not url or url.startswith("#"):
                continue
            if url.lower() == "repo_url":
                continue
            local = (parts[1] if len(parts) > 1 else "").strip()
            rows.append({"repo_url": url, "local_path": local})
    return rows


def write_repository_locations(rows):
    """Replace ``repository_locations.csv`` with **rows** (list of ``repo_url``/``local_path`` dicts)."""
    path = repository_locations_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["repo_url", "local_path"])
        for row in rows:
            writer.writerow(
                [
                    str((row or {}).get("repo_url") or "").strip(),
                    str((row or {}).get("local_path") or "").strip(),
                ]
            )
    return path


# Public library repos the first-run / Help setup wizard offers to clone.
BASIC_LIBRARY_REPOS = (
    "https://github.com/harnice/harnice-aerospace-library",
    "https://github.com/harnice/harnice-av-library",
    "https://github.com/harnice/harnice-general-library",
)


def ensure_repository_locations():
    """Create an empty ``repository_locations.csv`` (header only) if missing.

    Unlike ``path("repository locations")``, this never prompts. New installs
    start empty so the console can offer the library setup walkthrough.
    """
    path = repository_locations_path()
    if os.path.exists(path):
        return path
    write_repository_locations([])
    return path


def repository_locations_empty():
    """True when the CSV is missing or has no non-blank repository rows."""
    path = repository_locations_path()
    if not os.path.exists(path):
        return True
    for row in read_repository_locations():
        url = (row.get("repo_url") or "").strip()
        local = (row.get("local_path") or "").strip()
        if url or local:
            return False
    return True


def part_directory():
    """Return the part directory: the parent of the current working directory.

    When running in a revision folder (e.g. `rev1`), this is the part folder
    (e.g. `mypart`). Equivalent to `os.path.dirname(os.getcwd())`.
    """
    return os.path.dirname(os.getcwd())


def rev_directory():
    """Return the current revision directory (the current working directory).

    All project file-structure paths are resolved relative to this directory.
    Same as `os.getcwd()`.
    """
    return os.getcwd()


def silentremove(filepath):
    """Remove a file or directory and its contents if it exists.

    No-op if the path does not exist. Removes symlinks as files (does not follow).

    **Args:**

    - **filepath** — Path to the file or directory to remove.
    """
    if os.path.exists(filepath):
        if os.path.isfile(filepath) or os.path.islink(filepath):
            os.remove(filepath)  # remove file or symlink
        elif os.path.isdir(filepath):
            shutil.rmtree(filepath)  # remove directory and contents


def drawnby_path():
    """Absolute path to ``drawnby.json`` (the file may not exist yet)."""
    return os.path.join(harnice_root(), "drawnby.json")


def read_drawnby():
    """Return ``{"name": ...}`` from ``drawnby.json``, or ``None`` if missing/invalid."""
    path = drawnby_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        return {"name": "" if name is None else str(name)}
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def write_drawnby(name):
    """Write ``drawnby.json`` with ``{"name": name}``. Name must be non-blank."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Drawn-by name cannot be blank")
    path = drawnby_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"name": name}, f)
        f.write("\n")
    return path


_SETUP_PROGRESS_STATES = frozenset({"open", "done", "waived"})
_SETUP_PROGRESS_TEXT_FIELDS = ("note", "path", "draft")


def setup_progress_path():
    """Absolute path to ``setup_progress.json`` (the file may not exist yet).

    Lives in the Harnice app-data folder, next to ``drawnby.json``.
    """
    return os.path.join(harnice_root(), "setup_progress.json")


def _setup_progress_text(value, limit=500):
    text = "" if value is None else str(value).strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _normalize_setup_progress(data):
    """Return ``{"cwd", "items"}`` with only known checklist fields."""
    empty = {"cwd": "", "items": {}}
    if not isinstance(data, dict):
        return empty
    items = {}
    raw_items = data.get("items")
    if isinstance(raw_items, dict):
        for key, row in raw_items.items():
            item_id = _setup_progress_text(key, 300)
            if not item_id or not isinstance(row, dict):
                continue
            state = str(row.get("state") or "open").strip().lower()
            if state not in _SETUP_PROGRESS_STATES:
                state = "open"
            cleaned = {"state": state}
            for field in _SETUP_PROGRESS_TEXT_FIELDS:
                if field in row:
                    cleaned[field] = _setup_progress_text(row.get(field))
            items[item_id] = cleaned
    return {"cwd": _setup_progress_text(data.get("cwd"), 1000), "items": items}


def read_setup_progress():
    """Return setup-checklist progress from ``setup_progress.json``.

    Missing or unreadable file → ``{"cwd": "", "items": {}}``.
    """
    path = setup_progress_path()
    if not os.path.exists(path):
        return {"cwd": "", "items": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {"cwd": "", "items": {}}
    return _normalize_setup_progress(data)


def write_setup_progress(data):
    """Write ``setup_progress.json`` in the app-data folder.

    Unknown fields are dropped. Item ``state`` is ``open``, ``done``, or
    ``waived``.
    """
    cleaned = _normalize_setup_progress(data)
    path = setup_progress_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)
        f.write("\n")
    return path


def path(target_value, structure_dict=None, base_directory=None):
    """Return the full path to a file identified by its file key.

    * file structure dict (`state.file_structure`, or **structure_dict** if provided) is searched for a *value* equal to **target_value**. The path is built from the rev directory + **base_directory** (if any) + the key path to that value.

    **Special Target Values:**

    - **`revision history`:** the revision history file of the project you're currently working on
    - **`repository locations`:** the repository locations file on your computer (`repository_locations.csv`)
    - **`drawnby`:** the text file on your computer that stores your name
    - **`rev directory`:** the revsion directory of the project you're currently working on
    - **`part directory`:** the part directory of the project you're currently working on

    **Args:**

    - **target_value** — File key to look up (e.g. `"signals list"`, `"build instructions"`).
    - **structure_dict** — Optional. Override the default structure (e.g. for a macro).
        If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory to use as
        the root for structure paths. If `None` or `""`, paths are under the rev directory only.

    **Returns:** Absolute path to the file (`str`).

    **Raises:** `TypeError` if **target_value** is not found in the structure (for non-special keys).

    **First run**
    - If `repository locations` is missing, Harnice creates an empty CSV without
      prompting. Setup-checklist progress (finished and waived rows) is stored in
      ``setup_progress.json`` in that same folder. If `drawnby.json` is missing,
      the CLI (`harnice -b`, `--newrev`, `--newpn`) asks for your name when stdin
      is a terminal and writes it there. The desktop app asks from Settings
      (gear) → Drawn by… instead. The name is never guessed.

    """
    # FILES NOT DEPENDENT ON PRODUCT TYPE
    if target_value == "revision history":
        file_path = os.path.join(
            part_directory(), f"{state.partnumber('pn')}-revision_history.tsv"
        )
        return file_path

    # FILES DEPENDENT ON HARNICE ROOT

    if target_value == "repository locations":
        csv_path = repository_locations_path()
        if not os.path.exists(csv_path):
            ensure_repository_locations()
        return csv_path

    if target_value == "drawnby":
        return drawnby_path()

    # FILES INSIDE OF A STRUCURE DEFINED BY FILEIO
    # look up from default structure state if not provided
    if structure_dict is None:
        structure_dict = state.file_structure

    def recursive_search(data, path):
        if isinstance(data, dict):
            for key, value in data.items():
                if value == target_value:
                    return path + [key]
                result = recursive_search(value, path + [key])
                if result:
                    return result
        elif isinstance(data, list):
            for index, item in enumerate(data):
                if item == target_value:
                    return path + [f"[{index}]"]
                result = recursive_search(item, path + [f"[{index}]"])
                if result:
                    return result
        return None

    path_value = recursive_search(structure_dict, [])

    if not path_value:
        raise TypeError(f"Could not find filepath of '{target_value}'.")
    if base_directory in [None, ""]:
        return os.path.join(rev_directory(), *path_value)
    else:
        return os.path.join(rev_directory(), base_directory, *path_value)


def dirpath(target_key, structure_dict=None, base_directory=None):
    """Return the full path to a directory identified by its key in the file structure.

    Searches the file structure (`state.file_structure` or **structure_dict**) for a
    *key* equal to **target_key** (directory names are keys; file keys are values).
    The path is built from the rev directory + **base_directory** (if any) + the path to that key.

    **Special Target Keys:**

    - **`part directory`:** part directory of the project you're currently working on
    - **`rev directory`:** rev directory of the project you're currently working on

    **Args:**

    - **target_key** — Directory name in the structure (e.g. `"lists"`, `"maps"`).
        Pass `None` to get the rev directory (or rev + **base_directory**).
    - **structure_dict** — Optional. Override the default structure. If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory. If `None` or `""`,
        paths are under the rev directory only.

    **Returns:** Absolute path to the directory (`str`).

    **Raises:** `TypeError` if **target_key** is not `None` and not found in the structure.
    """
    if target_key == "rev directory":
        return rev_directory()

    if target_key == "part directory":
        return part_directory()

    if target_key is None:
        if base_directory in [None, ""]:
            return os.path.join(rev_directory())
        else:
            return os.path.join(rev_directory(), base_directory)

    if structure_dict is None:
        structure_dict = state.file_structure

    def recursive_search(data, path):
        if isinstance(data, dict):
            for key, value in data.items():
                # if the current key matches, return its path immediately
                if key == target_key:
                    return path + [key]
                # otherwise, keep descending
                result = recursive_search(value, path + [key])
                if result:
                    return result
        elif isinstance(data, list):
            for index, item in enumerate(data):
                result = recursive_search(item, path + [f"[{index}]"])
                if result:
                    return result
        return None

    path_key = recursive_search(structure_dict, [])
    if not path_key:
        raise TypeError(f"Could not find directory '{target_key}'.")
    if base_directory in [None, ""]:
        return os.path.join(rev_directory(), *path_key)
    else:
        return os.path.join(rev_directory(), base_directory, *path_key)


def library_identity_for_path(folder):
    """If **folder** sits inside a library, return ``(repo_url, lib_subpath)``.

    ``lib_subpath`` is the path under the matching ``local_path`` from
    ``repository_locations.csv`` (trailing ``/``), or ``""`` if **folder** is
    the library root itself.

    Containment is an exact string prefix after ``abspath`` / ``normpath`` —
    no case folding, no ``relpath``. Longest matching library root wins.
    """
    folder = str(folder or "").strip()
    if not folder:
        return "", ""
    folder = os.path.normpath(os.path.abspath(os.path.expanduser(folder)))
    folder = folder.replace("\\", "/").rstrip("/")
    if not folder:
        return "", ""

    lib_locs = repository_locations_path()
    if not os.path.exists(lib_locs):
        return "", ""
    try:
        rows = read_tsv(lib_locs, delimiter=",")
    except Exception:
        return "", ""

    best_root_len = -1
    library_repo = ""
    library_subpath = ""
    for row in rows:
        local = str(row.get("local_path") or "").strip()
        if not local:
            continue
        local = os.path.normpath(os.path.abspath(os.path.expanduser(local)))
        local = local.replace("\\", "/").rstrip("/")
        if not local:
            continue
        if folder == local:
            rest = ""
        elif folder.startswith(local + "/"):
            rest = folder[len(local) + 1 :] + "/"
        else:
            continue
        if len(local) < best_root_len:
            continue
        best_root_len = len(local)
        library_repo = str(row.get("repo_url") or "").strip()
        library_subpath = rest
    return library_repo, library_subpath


def verify_revision_structure():
    """Ensure the current directory is a valid revision folder and set `state.pn` and `state.rev`.

    Called before building and when the console opens a project.

    **Behavior:**

    - If cwd is a `rev<N>` folder: sets `state.pn` and `state.rev` from the path.
    - If cwd is a part folder that contains rev folders: prints a message and exits.
    - Otherwise: fails — create new projects from the Harnice console (**New project…**).

    Ensures revision_history exists and that the revision status is blank (Harnice only
    builds revisions with blank status). Updates revision_history library_repo /
    library_subpath from the current path. Does not change ``datemodified``; that
    is stamped when the project is built.
    """
    from harnice.lists import rev_history

    cwd = os.getcwd()
    cwd_name = os.path.basename(cwd)
    identity = revision_folder_parts(cwd)

    # --- 1) Already in a rev folder? (``rev1``; rev can be a number or letter) ---
    if identity is not None:
        parent, suffix = identity
        state.set_pn(parent)
        state.set_rev(int(suffix) if suffix.isdigit() else suffix)

    # --- 2) In a part folder that contains revision folders? ---
    elif list_revision_folders(cwd):
        print(f"This is a part folder ({cwd_name}).")
        print(f"Please `cd` into a revision folder (e.g. `rev1`) and rerun.")
        raise SystemExit(1)

    # --- 3) No revision structure ---
    else:
        raise RuntimeError(
            f"No valid Harnice file structure detected in '{cwd_name}'. "
            "Open a revision folder (e.g. MyPart/rev1), or create a project "
            "from the Harnice console (New project…)."
        )

    # --- Ensure revision_history entry exists ---
    try:
        rev_history.info()
    except ValueError:
        rev_history.append(next_rev=state.rev)
    except FileNotFoundError:
        rev_history.append(next_rev=state.rev)

    # --- Status must be blank to proceed ---
    if rev_history.info(field="status") != "":
        raise RuntimeError(
            f"Revision {state.rev} status is not clear. "
            f"Harnice only builds revisions with a blank status."
        )

    print(f"Loaded PN: {state.pn}, Rev: {state.rev}")
    rev_history.update_library_identity()

    return 0


def today():
    """Return today's date as a short string: `M/D/YY` (e.g. `2/12/25`)."""
    d = datetime.date.today()
    return f"{d.month}/{d.day}/{d.year % 100}"


def get_git_hash_of_harnice_src():
    """Return the git commit hash of the Harnice source repo (HEAD).

    Used for version/attribution in outputs. Returns `"UNKNOWN"` if git is
    unavailable or the repo cannot be read.
    """
    try:
        # ask git for commit hash
        from harnice.runtime import no_console_kwargs

        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=harnice_root(),
                stderr=subprocess.DEVNULL,
                **no_console_kwargs(),
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def read_tsv(filepath, delimiter="\t"):
    """Read a TSV file and return a list of row dicts (one dict per row, keys from header).

    If **filepath** is an existing file path, that file is read. If not, **filepath** is
    treated as a file key and `fileio.path(filepath)` is used to resolve the path
    (e.g. `"instances list"` or `"signals list"`).

    **Args:**

    - **filepath** — Path to a TSV file, or a file key (e.g. `"instances list"`).
    - **delimiter** — Column delimiter; default `"\\t"`.

    **Returns:** List of dicts, one per data row, with keys from the header row (`list`).

    **Raises:** `FileNotFoundError` if the path does not exist or the resolved path does not exist.
    """
    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter=delimiter))
    except FileNotFoundError:
        filepath = path(filepath)
        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f, delimiter=delimiter))
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Expected csv or tsv file with delimiter '{delimiter}' at path or key {filepath}"
            )


def drawnby():
    """Load and return the contents of the drawnby file (path from `fileio.path("drawnby")`).

    The drawnby file stores author/credits info on this computer.

    That file should be structured like this, and this function will return exactly the same as a json object:
    ```json
    {
        "name": "K SHUTT"
    }
    ```
    Use case:
    ```python
    name = fileio.drawnby().get("name")
    ```

    The CLI asks for this name on a terminal when the file does not exist yet.
    The desktop app asks from Settings (gear) → Drawn by….
    """
    data = read_drawnby()
    name = ((data or {}).get("name") or "").strip()
    if not name:
        raise RuntimeError(
            "Drawn-by name is not set. Open the Harnice console and use "
            "Settings (gear) → Drawn by… to enter your name."
        )
    return {"name": name}
