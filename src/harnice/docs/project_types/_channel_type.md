# Channel Types

---

## How are channels mapped?

---

## How to define a new channel type
1. In a repository of your choice (or start with [harnice-general-library](https://github.com/harnice/harnice-general-library) on your own branch), navigate to `channel_types.tsv` at the library root
1. If you want channel definitions to be private and are therefore working in a private repository, ensure the repo's path is listed in file `repository_locations.csv` (located at root of your harnice source code repo). The first column is the URL or traceable path, and the second column is your local path.
1. If you find the channel_type you're looking for, temporarily note it as a touple in a notepad somewhere with format `(ch_type_id, universal_library_repository)`. 
1. If you don't find it, make a new one. It's important to try and reduce the number of channel_types in here to reduce complexity, but it's also important that you adhere to strict and true rules about what is allowed to be mapped to what. Modifications and additions to this document should be taken and reviewed very seriously.

Two optional columns set the default appearance. Both cells are Python dict literals, parsed with `ast.literal_eval`. Leave a cell blank to leave that default unset. Harnice reads the `channel_types.tsv` at the root of the library named by the channel type's `lib_repo`.

- `channel_default_appearance` — one engineering appearance dict. A channel trace (`channel` or `harness-channel`) and the channel card in the connectors view use it. Example: `{'base_color': '#D59A10'}`.
- `signal_default_appearances` — signal name to appearance dict. A circuit trace uses the entry for its `signal_of_channel_type`, and the connectors view uses that entry for the signal bar. Names match the `signals` column. Example: `{'pos': {'base_color': '#E24B4A'}, 'neg': {'base_color': '#2E6B9F'}}`.

An instance `appearance` that already includes `base_color` is the appearance drawn for that trace. Traces are drawn when the project is built, so a change to these columns shows up on overlays after the next build. The connectors view reads the columns when the page opens. A trace whose resolved appearance has no `base_color` is the rainbow placeholder. A card or bar with no `base_color` keeps the console palette.

The dict is the engineering appearance from the Appearance guide: `base_color`, and optionally `outline_color`, `parallelstripe`, `perpstripe`, and `twisted`. Single quotes match the rows already in the file. The separator is a tab, so a comma inside the literal stays in the cell.

??? info "`chtype.parse(val)`"

    Use this when a build has a channel type as stored text and needs the (channel_type_id, lib_repo) pair.
    
    Convert stored string into a tuple (chid:int, lib_repo:str).
    Handles both single tuples and extracts first tuple from lists.

??? info "`chtype.signals(channel_type)`"

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

??? info "`chtype.channel_default_appearance(channel_type)`"

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

??? info "`chtype.signal_default_appearances(channel_type)`"

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

??? info "`chtype.compatibles(channel_type)`"

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

??? info "`chtype.is_or_is_compatible_with(channel_type)`"

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

??? info "`chtype.attribute(channel_type, attribute)`"

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

??? info "`chtype.path(channel_type)`"

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

