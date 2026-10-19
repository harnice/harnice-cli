"""Current build context: part number, revision, project type, and file structure.

The CLI and `fileio` set these before running a project. Scripts can read `state.pn`,
`state.rev`, and `state.partnumber(format)`; `state.file_structure` is used by `fileio`
when resolving path keys.
"""

import re


# not initializing these variables so that a NameError is raised if they are not set
def set_pn(x):
    """Set the current part number (e.g. `"mypart"`). Called by `fileio.verify_revision_structure()`.

    **Args:**
    - `x`: Part number string, for example ``"mypart"``. Later calls to ``partnumber`` read this value.
    """
    global pn
    pn = x


def set_rev(x):
    """Set the current revision (number or string, e.g. 1 or \"A\"). Called by `fileio.verify_revision_structure()`.

    **Args:**
    - `x`: Revision number or letter, for example ``1`` or ``"A"``. ``partnumber`` formats this as ``rev1`` or ``revA``.
    """
    global rev
    rev = x


def set_project_type(x):
    """Set the current project type (e.g. `"harness"`, `"system"`).

    **Args:**
    - `x`: Project type name, for example ``"harness"``, ``"system"``, or ``"device"``.
    """
    global project_type
    project_type = x


def set_harness(x):
    """Set the current harness context (used during build).

    **Args:**
    - `x`: Harness name for this build. New instances pick it up when they do not set ``harness`` themselves.
    """
    global harness
    harness = x


def set_file_structure(x):
    """Set the default file structure dict used by `fileio.path()` and `fileio.dirpath()`.

    The CLI calls this with the current project type's `file_structure()` result.

    **Args:**
    - `x`: File-structure dict. ``fileio.path`` and ``fileio.dirpath`` resolve keys against it.
    """
    global file_structure
    file_structure = x


def partnumber(format):
    """Return the current part number and/or revision in the requested format.

    Assumes `state.pn` and `state.rev` are set (e.g. by `fileio.verify_revision_structure()`).
    For a part `"mypart"` and rev `1`:

    **Args:**

    - **format** — One of:
        - `"pn-rev"`: full part-rev string, e.g. `"mypart-rev1"`
        - `"pn"`: part number only, e.g. `"mypart"`
        - `"rev"`: revision label, e.g. `"rev1"`
        - `"R"`: revision number only, e.g. `"1"`

    **Returns:** The requested substring of `"pn-revRev"` (e.g. `"mypart-rev1"`) (`str`).

    **Raises:** `ValueError` if **format** is not one of the options above.
    """
    pn_rev = f"{pn}-rev{rev}"

    if format == "pn-rev":
        if not rev:
            return pn
        else:
           return pn_rev

    elif format == "pn":
        match = re.search(r"-rev", pn_rev)
        if match:
            return pn_rev[: match.start()]

    elif format == "rev":
        match = re.search(r"-rev", pn_rev)
        if match:
            return pn_rev[match.start() + 1 :]

    elif format == "R":
        match = re.search(r"-rev", pn_rev)
        if match:
            return pn_rev[match.start() + 4 :]

    else:
        raise ValueError("Function 'partnumber' not presented with a valid format")
