from harnice import fileio
from harnice.lists import cached_tsv

COLUMNS = [
    "instance_name",  # instance this import was recorded under; a macro uses its artifact id
    "mpn",  # manufacturer part number that was pulled
    "item_type",  # kind of part that was pulled, such as harness_connector, cable, backshell, or macro
    "lib_repo",  # library URL, or "local"
    "lib_subpath",  # path under that library to the part folder
    "lib_desc",  # description from the library revision history
    "lib_latest_rev",  # latest revision of this part in the library
    "lib_rev_used_here",  # revision copied into this project
    "lib_status",  # status of that library revision
    "lib_releaseticket",  # release ticket on that library revision, when the library records one
    "lib_datestarted",  # date this part was first added to the library
    "lib_datemodified",  # date this part was last modified in the library
    "lib_datereleased",  # date this library revision was released, when that field is set
    "lib_drawnby",  # author recorded on the library revision
    "lib_checkedby",  # checker recorded on the library revision
    "project_editable_lib_modified",  # the editable copy in this project differs from the library snapshot
]


def read():
    """
    Use this when a harness or system build needs every row of the library-import history.

    Return every row of the library-import history.

    The file is ``fileio.path("library history")``. One row per pull.
    ``run_macro`` refuses an artifact id that is already here unless
    ``rerun`` is true.
    """
    return cached_tsv.read(fileio.path("library history"))


def new():
    """
    Use this when the project build is starting the library-import history. Harness and system builds call this before the script and replace the file. A build script does not call it again.

    Create an empty library-history file, replacing one that already exists.
    """
    cached_tsv.write(fileio.path("library history"), COLUMNS, [])


def append(instance_name, instance_data):
    """
    Use this when a harness or system build needs one library import recorded in the library history.

    Record one library import in the library history.

    **Args:**
    - `instance_name`: Name for this import. Raises if that name is already in the history.
    - `instance_data`: Dict of library-history columns (``mpn``, ``item_type``, ``lib_repo``, ``lib_subpath``, and the ``lib_*`` metadata). ``instance_name`` in the dict is replaced by the ``instance_name`` argument. Missing columns are written blank.
    """
    with cached_tsv.edit(fileio.path("library history"), COLUMNS) as rows:
        instance_data["instance_name"] = instance_name
        for row in rows:
            if row.get("instance_name") == instance_name:
                raise ValueError(
                    f"You're trying to import something with instance_name '{instance_name}' but it has already been imported."
                )
        rows.append({key: instance_data.get(key, "") for key in COLUMNS})
