from harnice import fileio
from harnice.lists import cached_tsv

COLUMNS = [
    "instance_name", #documentation needed
    "mpn", #documentation needed
    "item_type", #documentation needed
    "lib_repo", #documentation needed
    "lib_subpath", #documentation needed
    "lib_desc", #documentation needed
    "lib_latest_rev", #documentation needed
    "lib_rev_used_here", #documentation needed
    "lib_status", #documentation needed
    "lib_releaseticket", #documentation needed
    "lib_datestarted", #documentation needed
    "lib_datemodified", #documentation needed
    "lib_datereleased", #documentation needed
    "lib_drawnby", #documentation needed
    "lib_checkedby", #documentation needed
    "project_editable_lib_modified", #documentation needed
]


def read():
    """Return the library import history (cached)."""
    return cached_tsv.read(fileio.path("library history"))


def new():
    cached_tsv.write(fileio.path("library history"), COLUMNS, [])


def append(instance_name, instance_data):
    with cached_tsv.edit(fileio.path("library history"), COLUMNS) as rows:
        instance_data["instance_name"] = instance_name
        for row in rows:
            if row.get("instance_name") == instance_name:
                raise ValueError(
                    f"You're trying to import something with instance_name '{instance_name}' but it has already been imported."
                )
        rows.append({key: instance_data.get(key, "") for key in COLUMNS})
