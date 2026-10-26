import os
import ast
from harnice import fileio
from harnice.utils import library_utils


def file_structure():
    return {}


def generate_structure():
    pass


def path(channel_type):
    """
Use this when a build needs the path of channel_types.tsv for one channel type's library checkout.

Resolve the on-disk path to the `channel_types.tsv` file for a given
channel type.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand (for example `"(5, 'https://github.com/harnice/harnice-general-library')"`).

**Returns**

- `str`: Absolute path to `channel_types.tsv` at the root of the library
    repository that owns the given channel type.

**Notes**

- This does **not** filter rows; it only locates the TSV file that defines
    all channel types for the given `lib_repo`.
    """
    chid, lib_repo = parse(channel_type)
    return os.path.join(library_utils.get_local_path(lib_repo), "channel_types.tsv")


def parse(val):
    """
    Use this when a build has a channel type as stored text and needs the (channel_type_id, lib_repo) pair.

    Convert stored string into a tuple (chid:int, lib_repo:str).
    Handles both single tuples and extracts first tuple from lists.
    """
    if not val:
        return None
    if isinstance(val, tuple):
        chid, lib_repo = val
    else:
        parsed = ast.literal_eval(str(val))
        # If it's a list, take the first tuple
        if isinstance(parsed, list):
            chid, lib_repo = parsed[0]
        else:
            chid, lib_repo = parsed
    return (int(chid), str(lib_repo).strip())


def compatibles(channel_type):
    """
Use this when a system build needs the channel types declared compatible with one channel type, not including that type itself.

Look up other channel types that are declared as compatible with the given
channel type.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.

**Returns**

- `list[tuple[int, str]]`: List of `(channel_type_id, lib_repo)` tuples taken
    directly from the `compatible_channel_types` column of `channel_types.tsv`.
    Returns an empty list if no compatibles are defined or if the channel type
    cannot be found.

**Data format**

- The `compatible_channel_types` column must be an AST-parseable Python value:
    - Single tuple: `(1, "library_repo")`
    - List of tuples: `[(1, "library_repo"), (2, "library_repo")]`
    """
    channel_type_id, lib_repo = parse(channel_type)

    for row in fileio.read_tsv(path((channel_type_id, lib_repo))):
        if int(row.get("channel_type_id")) == channel_type_id:
            signals_str = row.get("compatible_channel_types", "").strip()
            if not signals_str:
                return []

            # Parse the AST-formatted string
            parsed_value = ast.literal_eval(signals_str)

            # Normalize to list format
            if isinstance(parsed_value, tuple):
                # Single tuple, wrap it in a list
                return [parsed_value]
            elif isinstance(parsed_value, list):
                # Already a list of tuples
                return parsed_value
            else:
                return []

    return []


def is_or_is_compatible_with(channel_type):
    """
Use this when a system build is validating or mapping channels and this channel type should count if it is the requested type or listed as compatible with it.

Return the given channel type plus all channel types declared as compatible
with it.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.

**Returns**

- `list[tuple[int, str]]`: List of `(channel_type_id, lib_repo)` tuples where
    the first entry is the parsed `channel_type` itself and the remaining
    entries are the compatibles returned by `compatibles(channel_type)`.

**Typical use**

- Use this when validating or mapping channels and you want to treat a
    channel type as valid if it is either exactly the requested type or
    explicitly listed as compatible with it.
    """
    output = []
    output.append(parse(channel_type))
    for compatible in compatibles(channel_type):
        output.append(compatible)
    return output


def signals(channel_type):
    """
Use this when a system or device build needs the signal names declared for one channel type.

Return the list of signal names associated with a specific channel type.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.

**Returns**

- `list[str]`: List of signal names from the `signals` column of
    `channel_types.tsv` for the matching `channel_type_id`. If the column is
    blank or the channel type cannot be found, returns an empty list.

**Data format**

- The `signals` column is expected to be a comma-separated string, for
    example: `"CAN_H, CAN_L, SHIELD"`.
    """
    chid, lib_repo = parse(channel_type)

    for row in fileio.read_tsv(path(channel_type)):
        if str(row.get("channel_type_id", "")).strip() == str(chid):
            return [
                sig.strip() for sig in row.get("signals", "").split(",") if sig.strip()
            ]
    return []


def attribute(channel_type, attribute):
    """
Use this when a system or device build needs an extra column from channel_types.tsv for one channel type.

Read any additional column from `channel_types.tsv` for a given channel
type.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.
- `attribute`: Column header name in `channel_types.tsv` for the value you
    want to read (for example `"description"`, `"notes"`, `"voltage_rating"`).

**Returns**

- `Any`: Value stored in the requested `attribute` column for the matching
    `channel_type_id`. Returns an empty list `[]` if the channel type cannot
    be found.

**Notes**

- Reads `<library_root>/channel_types.tsv` (same file as `path()`).
- Use this for any per-channel-type metadata you've added as extra columns
    beyond the core ones like `channel_type_id`, `signals`, and
    `compatible_channel_types`.
    """
    chid, lib_repo = parse(channel_type)

    # Same on-disk file as path() / signals() / compatibles(): <lib>/channel_types.tsv
    for row in fileio.read_tsv(path(channel_type)):
        if str(row.get("channel_type_id", "")).strip() == str(chid):
            return row.get(attribute)
    return []


def _appearance_from_cell(raw):
    """Parse one appearance cell. Blank or non-dict input returns ``None``."""
    if raw in (None, "", []):
        return None
    from harnice.utils import appearance

    parsed = appearance.parse(raw)
    if not isinstance(parsed, dict):
        return None
    return parsed


def channel_default_appearance(channel_type):
    """
Use this when a drawing needs the default appearance of one channel type's trace and card.

Optional default appearance for this channel type's channel trace and card.

Reads ``channel_default_appearance`` from the `channel_types.tsv` at the
root of the library named by this channel type's `lib_repo`. The cell is a
Python dict literal, parsed with ``ast.literal_eval`` (see `appearance.parse`).
Example: ``{'base_color': '#D59A10'}``. A blank cell returns ``None``.

A channel trace (``item_type`` ``channel`` or ``harness-channel``) and the
channel card in the connectors view use this appearance. A circuit trace uses
`signal_default_appearances` for its ``signal_of_channel_type`` instead.

An instance ``appearance`` that already includes ``base_color`` is the
appearance drawn for that trace. Traces are drawn when the project is built.
The connectors view reads this column when the page opens. A trace whose
resolved appearance has no ``base_color`` is the rainbow placeholder. A
channel card with no ``base_color`` keeps the console palette.

The dict is an engineering appearance: ``base_color`` plus any of
``outline_color``, ``parallelstripe``, ``perpstripe``, and ``twisted``.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.

**Returns**

- `dict` or `None`: Parsed appearance, or ``None`` when the cell is empty
    or the channel type cannot be found.
    """
    raw = attribute(channel_type, "channel_default_appearance")
    return _appearance_from_cell(raw)


def signal_default_appearances(channel_type):
    """
Use this when a drawing needs the default appearance of each signal on one channel type.

Optional default appearance for each signal of this channel type.

Reads ``signal_default_appearances`` from the `channel_types.tsv` at the
root of the library named by this channel type's `lib_repo`. The cell is a
Python dict literal, parsed with ``ast.literal_eval``: signal name to
appearance dict. Example:
``{'pos': {'base_color': '#E24B4A'}, 'neg': {'base_color': '#2E6B9F'}}``.
A blank cell returns ``{}``. Names that are not themselves dicts are dropped.
Signal names match the ``signals`` column.

A circuit trace uses the entry for its ``signal_of_channel_type``. The
connectors view uses the same entry for that signal's bar. A channel trace
uses `channel_default_appearance`.

An instance ``appearance`` that already includes ``base_color`` is the
appearance drawn for that trace. Traces are drawn when the project is built.
The connectors view reads this column when the page opens. A trace whose
resolved appearance has no ``base_color`` is the rainbow placeholder. A
signal bar with no ``base_color`` keeps the console palette.

Each value is an engineering appearance: ``base_color`` plus any of
``outline_color``, ``parallelstripe``, ``perpstripe``, and ``twisted``.

**Args**

- `channel_type`: Channel type identifier in standard tuple format
    `(channel_type_id, lib_repo)` or any string representation that `parse`
    can understand.

**Returns**

- `dict`: Signal name to appearance dict. Empty when unset or when the
    channel type cannot be found.
    """
    raw = attribute(channel_type, "signal_default_appearances")
    parsed = _appearance_from_cell(raw)
    if not parsed:
        return {}
    return {
        str(name): spec
        for name, spec in parsed.items()
        if isinstance(spec, dict)
    }
