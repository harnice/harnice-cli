import ast
import importlib
import os

from harnice import fileio, state
from harnice.lists import cached_tsv


def _revs_equivalent(a, b):
    """Return True if two revision labels denote the same rev (strip; numeric int match)."""
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if sa == sb:
        return True
    if sa.isdigit() and sb.isdigit():
        return int(sa) == int(sb)
    return False


# === Global Columns Definition ===
COLUMNS = [
    "project_type",  # the harnice project type (e.g. "harness", "connector", "device", "system", "macro", "flagnote", "tblock")
    "mfg",  # who manufactures this (blank ok)
    "pn",  # name, part number, other identifier of this part. mfg+mpn combination must be unique within the library.
    "desc",  # a brief description of this project
    "rev",  # the revision of the part
    "status",  # "released", "obsolete", etc. Harnice will not build a revision if the status has text in this field as a form of protection.
    "releaseticket",  # many companies do this, but it's not required.
    "library_repo",  # auto-filled on build if the current working directory is discovered to be a library repository.
    "library_subpath",  # auto-filled on build if in a library repository; directories between the library root and the part number (used as lib_subpath when pulling)
    "source_part_number",  # harness only: system PN this harness was imported from
    "source_revision",  # harness only: system revision this harness was imported from
    "source_lib_repo",  # harness only: repository_locations.csv repo URL of that system
    "source_subpath",  # harness only: path from that library root to the system PN folder
    "source_refdes",  # harness only: harness refdes on the source system
    "datestarted",  # auto-filled to be the date when this part was first intialized
    "datemodified",  # updates to today's date upon build
    "datereleased",  # up to user to fill in as needed
    "git_hash_of_harnice_src",  # auto-filled, git hash of the harnice source code during the latest build
    "drawnby",  # auto-filled, the person who created the part
    "checkedby",  # the person who checked the part, blank ok
    "revisionupdates",  # a brief description of the changes made to this revision
    "affectedinstances",  # the instance names of the instances that were affected by this revision. can be referenced later by PDF builders and more.
    "last_build",  # "succeeded" or "failed" after the latest build of this revision; blank until first build
]


def read(path=None):
    """Return a revision history (cached)."""
    if path is None:
        path = fileio.path("revision history")
    return cached_tsv.read(path)


def overwrite(content_dict):
    """
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
    """
    PROTECTED_KEYS = [
        "project_type",
        "mfg",
        "pn",
        "rev",
        "releaseticket",
        "library_repo",
        "library_subpath",
        "datestarted",
        "last_build",
    ]
    # 1) Ensure no unknown keys
    for key in content_dict:
        if key not in COLUMNS:
            raise KeyError(
                f"Harnice does not allow writing unknown key '{key}'. "
                f"Valid columns: {', '.join(COLUMNS)}"
            )

    # 2) Ensure none of the protected keys are being modified
    for key in PROTECTED_KEYS:
        if key in content_dict:
            raise KeyError(
                f"Harnice does not allow overwriting '{key}' by script.\n"
                f"Please edit the revision history manually."
            )

    # 3) Load or create revision history
    path = fileio.path("revision history")
    if not os.path.exists(path):
        new()  # Creates a blank rev history with header

    rows = read(path)

    # 4) Determine which revision we are updating from state
    target_rev = str(state.rev).strip()
    if not target_rev:
        raise RuntimeError("state.rev is not set. Did verify_revision_structure() run?")

    # 5) Update matching row
    found = False
    for row in rows:
        if _revs_equivalent(row.get("rev"), target_rev):
            found = True
            for key, value in content_dict.items():
                row[key] = value

    if not found:
        raise ValueError(f"No revision '{target_rev}' found in revision history.")

    # 6) Write updated TSV
    cached_tsv.write(path, COLUMNS, rows)


def info(rev=None, path=None, field=None, all=False):
    """
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
    """
    if path is None:
        path = fileio.path("revision history")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Revision history file not found at {path}")

    if rev is not None and str(rev).strip() != "":
        rev = str(rev).strip()
    else:
        rev = state.partnumber("R")

    rows = read(path)

    if all:
        return rows

    for row in rows:
        if _revs_equivalent(row.get("rev"), rev):
            # ------------------------------------------------------
            # Field requested
            # ------------------------------------------------------
            if field:
                val = row.get(field)

                if field == "affectedinstances":
                    if not val or val.strip() == "":
                        return []
                    try:
                        return ast.literal_eval(val)
                    except Exception:
                        # fallback: return empty list if malformed
                        return []

                # other fields unchanged
                return val

            # ------------------------------------------------------
            # Entire row requested: parse affectedinstances only
            # ------------------------------------------------------
            full_row = dict(row)
            ai = row.get("affectedinstances")
            if ai and ai.strip() != "":
                try:
                    full_row["affectedinstances"] = ast.literal_eval(ai)
                except Exception:
                    full_row["affectedinstances"] = []
            else:
                full_row["affectedinstances"] = []

            return full_row

    raise ValueError(f"Revision {rev} not found in revision history at {path}")


def initial_release_exists():
    """
    Check if an initial release exists.

    **Arguments:**

    None

    **Returns:**

    - `bool`: `True` if a revision with the text `"INITIAL RELEASE"` in the `"revisionupdates"` field exists, `False` otherwise.
    """
    try:
        for row in read():
            if str(row.get("revisionupdates", "")).strip() == "INITIAL RELEASE":
                return True
            else:
                return False
    except NameError:
        return False


def initial_release_desc():
    """
    Get the description of the initial release.

    **Arguments:**

    None

    **Returns:**

    - `str`: The description of the revision which has `revisionupdates == 'INITIAL RELEASE'`.
    """
    for row in read():
        if row.get("revisionupdates") == "INITIAL RELEASE":
            return row.get("desc")


def update_datemodified():
    """
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
    """
    target_rev = state.partnumber("R")

    path = fileio.path("revision history")
    rows = read(path)

    # Modify matching row(s)
    for row in rows:
        if _revs_equivalent(row.get("rev"), target_rev):
            row["datemodified"] = fileio.today()
            row["drawnby"] = fileio.drawnby()["name"]
            row["git_hash_of_harnice_src"] = fileio.get_git_hash_of_harnice_src()

    cached_tsv.write(path, COLUMNS, rows)


def update_last_build(result):
    """
    Set ``last_build`` on the current revision to ``"succeeded"`` or ``"failed"``.

    Called when the project is built (console **Build** or ``harnice -b``).

    **Arguments:**

    - `result` (str): ``"succeeded"`` or ``"failed"``.

    **Returns:**

    - `None`

    **Raises:**

    - `ValueError`: If ``result`` is not ``"succeeded"`` or ``"failed"``.
    """
    value = (result or "").strip().lower()
    if value not in ("succeeded", "failed"):
        raise ValueError(
            f"last_build must be 'succeeded' or 'failed', got {result!r}"
        )

    target_rev = state.partnumber("R")
    path = fileio.path("revision history")
    rows = read(path)

    for row in rows:
        if _revs_equivalent(row.get("rev"), target_rev):
            row["last_build"] = value

    cached_tsv.write(path, COLUMNS, rows)


def update_library_identity():
    """Set ``library_repo`` / ``library_subpath`` on the current revision from cwd.

    Uses ``fileio.library_identity_for_path`` on the parent of the PN folder
    (the location the part was created in). Called from
    ``fileio.verify_revision_structure`` so library fields stay current whenever
    the revision structure is verified.
    """
    target_rev = state.partnumber("R")
    library_repo, library_subpath = fileio.library_identity_for_path(
        os.path.dirname(fileio.part_directory())
    )

    path = fileio.path("revision history")
    rows = read(path)

    for row in rows:
        if _revs_equivalent(row.get("rev"), target_rev):
            row["library_repo"] = library_repo
            row["library_subpath"] = library_subpath

    cached_tsv.write(path, COLUMNS, rows)


def new(ignore_project_type=False, path=None):
    """
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
    """
    if path is None:
        path = fileio.path("revision history")

    if not ignore_project_type:
        from harnice.cli import select_project_type

        state.set_project_type(select_project_type())

    if ignore_project_type and not state.project_type:
        raise ValueError(
            "You tried to create a new revision history file without a project type. This is not allowed."
        )

    if not os.path.exists(path):
        cached_tsv.write(path, COLUMNS, [])

    else:
        raise ValueError(
            "You tried to overwrite a revision history file- this is not allowed."
        )


def create_initial(
    pn_folder: str,
    part_number: str,
    rev,
    project_type: str,
    desc: str,
    revisionupdates: str = "INITIAL RELEASE",
    library_repo=None,
    library_subpath=None,
    source_part_number="",
    source_revision="",
    source_lib_repo="",
    source_subpath="",
    source_refdes="",
):
    """Create a new revision history TSV for a part (non-interactive).

    Writes ``{pn_folder}/{part_number}-revision_history.tsv`` with a single row.
    Used by the console New project flow so CLI prompting is not required.

    **Raises:**

    - ``ValueError`` — If the file already exists, or required fields are missing.
    """
    part_number = (part_number or "").strip()
    project_type = (project_type or "").strip()
    desc = (desc or "").strip()
    rev_s = "" if rev is None else str(rev).strip()
    if rev_s.lower().startswith("rev"):
        rev_s = rev_s[3:]
    revisionupdates = (revisionupdates or "").strip() or "INITIAL RELEASE"
    if not part_number or not project_type or not rev_s:
        raise ValueError("part_number, project_type, and rev are required")
    if not desc:
        raise ValueError("desc is required")

    pn_folder = os.path.normpath(os.path.abspath(pn_folder))
    path = os.path.join(pn_folder, f"{part_number}-revision_history.tsv")
    if os.path.exists(path):
        raise ValueError(f"Revision history already exists: {path}")

    today = fileio.today()
    if library_repo is None or library_subpath is None:
        inferred_repo, inferred_subpath = fileio.library_identity_for_path(
            os.path.dirname(pn_folder)
        )
        if library_repo is None:
            library_repo = inferred_repo
        if library_subpath is None:
            library_subpath = inferred_subpath
    row = {col: "" for col in COLUMNS}
    row.update(
        {
            "project_type": project_type,
            "pn": part_number,
            "rev": rev_s,
            "desc": desc,
            "status": "",
            "library_repo": library_repo,
            "library_subpath": library_subpath,
            "datestarted": today,
            "datemodified": today,
            "revisionupdates": revisionupdates,
        }
    )
    if project_type == "harness":
        source_revision_s = (source_revision or "").strip()
        if source_revision_s and not source_revision_s.lower().startswith("rev"):
            source_revision_s = f"rev{source_revision_s}"
        row.update(
            {
                "source_part_number": (source_part_number or "").strip(),
                "source_revision": source_revision_s,
                "source_lib_repo": (source_lib_repo or "").strip(),
                "source_subpath": (source_subpath or "").strip(),
                "source_refdes": (source_refdes or "").strip(),
            }
        )

    os.makedirs(pn_folder, exist_ok=True)
    cached_tsv.write(path, COLUMNS, [row])
    return path


def append(next_rev=None):
    """
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
    """
    from harnice import cli

    if not os.path.exists(fileio.path("revision history")):
        new()
    rows = read()
    if rows:
        for row in reversed(rows):
            candidate = (row.get("project_type") or "").strip()
            if candidate:
                state.set_project_type(candidate)
                break
    if not state.project_type:
        state.set_project_type(cli.select_project_type())

    default_desc = ""
    if state.project_type:
        try:
            product_module = importlib.import_module(
                f"harnice.project_types.{state.project_type}"
            )
        except ModuleNotFoundError:
            product_module = None
        else:
            default_desc = getattr(product_module, "default_desc", "") or ""

    desc = ""
    if rows:
        # Latest rev in file order (append-only history); supports numeric and letter labels.
        highest_existing_rev = None
        for row in reversed(rows):
            r = (row.get("rev") or "").strip()
            if r:
                highest_existing_rev = r
                break

        if highest_existing_rev is not None and not _revs_equivalent(
            next_rev, highest_existing_rev
        ):
            for row in rows:
                if _revs_equivalent(row.get("rev"), highest_existing_rev):
                    desc = row.get("desc")
                    if row.get("status") in [None, ""]:
                        print(
                            f"Your existing highest revision ({highest_existing_rev}) has no status. Do you want to obsolete it?"
                        )
                        obsolete_message = cli.prompt(
                            "Type your message here, leave blank for 'OBSOLETE' message, or type 'n' to keep it blank.",
                            default="OBSOLETE",
                        )
                        if obsolete_message == "n":
                            obsolete_message = ""
                        row["status"] = obsolete_message  # ← modified here
                    break

    if desc in [None, ""]:
        desc = cli.prompt(
            f"Enter a description of this {state.project_type}",
            default=default_desc,
        )

    revisionupdates = "INITIAL RELEASE"
    if any(
        str(row.get("revisionupdates", "")).strip() == "INITIAL RELEASE" for row in rows
    ):
        revisionupdates = ""
    revisionupdates = cli.prompt(
        "Enter a description for this revision", default=revisionupdates
    )
    while not revisionupdates or not revisionupdates.strip():
        cli.warn("Revision updates can't be blank!")
        revisionupdates = cli.prompt(
            "Enter a description for this revision", default=None
        )

    # add lib_repo if filepath is found in repository locations
    library_repo, library_subpath = fileio.library_identity_for_path(
        os.path.dirname(fileio.part_directory())
    )

    ####

    new_row = {col: "" for col in COLUMNS}
    if rows:
        for row in reversed(rows):
            if (row.get("rev") or "").strip():
                for key in (
                    "source_part_number",
                    "source_revision",
                    "source_lib_repo",
                    "source_subpath",
                    "source_refdes",
                ):
                    new_row[key] = row.get(key) or ""
                break
    new_row.update(
        {
            "project_type": state.project_type,
            "pn": state.pn,
            "rev": next_rev,
            "desc": desc,
            "status": "",
            "library_repo": library_repo,
            "library_subpath": library_subpath,
            "datestarted": fileio.today(),
            "datemodified": fileio.today(),
            "revisionupdates": revisionupdates,
        }
    )
    rows.append(new_row)

    cached_tsv.write(fileio.path("revision history"), COLUMNS, rows)


def part_family_append(content_dict, rev_history_path):
    """
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
    """
    actual_content_dict = content_dict

    actual_content_dict["datemodified"] = fileio.today()
    actual_content_dict["drawnby"] = fileio.drawnby()["name"]
    actual_content_dict["git_hash_of_harnice_src"] = (
        fileio.get_git_hash_of_harnice_src()
    )

    if os.path.exists(rev_history_path):
        rows = read(rev_history_path)
    else:
        rows = []

    found = False
    for i, row in enumerate(rows):
        if _revs_equivalent(row.get("rev"), actual_content_dict.get("rev")):
            rows[i] = actual_content_dict
            found = True
            break

    if not found:
        rows.append(actual_content_dict)

    if not os.path.exists(rev_history_path):
        new(path=rev_history_path, ignore_project_type=True)
    cached_tsv.write(rev_history_path, COLUMNS, rows)
