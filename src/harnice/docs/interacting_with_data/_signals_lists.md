# Interacting with Signals Lists
Signals Lists define every signal going into or out of a device or disconnect. They are the primary way Harnice stores information about devices.

![The signals list those instructions produce](images/signals-list-table.png)

Signals lists are usually repetative, long, and deterministic. Harnice helps you build signals lists efficiently using build instructuons, which are python rules that build the lists for you.

![Build instructions that write a device signals list](images/signals-list-build-instructions.png)

---
##Columns 
*Columns are automatically generated when `signals_list.new()` is called. Additional columns are ok but discouraged due to consistency. If you need more columns, use data structures in build instructions.*

| Column | Description |
|--------|-------------|
| `channel_id` | the channel this row belongs to; the same id on every signal of that channel |
| `repeat_channel_id` | which endpoint, when the channel is a passthrough with two ends; the two repeats must differ; blank when the channel has one endpoint |
| `channel_type` | channel type string; every signal name it declares must be appended for this endpoint, and the string must parse as a channel type |
| `signal` | signal name; one of the names declared by channel_type |
| `cavity` | pin, socket, or stud this signal uses on its connector; required, and unique on that connector |
| `connector_id` | the connector that holds this signal; every signal of one endpoint uses the same connector |
| `device_connector_mpn` | manufacturer part number of the device-side connector; set this or harness_connector_mpn, not both, and use the same choice for every row of that connector |
| `harness_connector_mpn` | manufacturer part number of the harness-side connector; set this or device_connector_mpn, not both |


---
## Signals List Validation Checks:
*(These are automatically validated when you build the device that owns the list.)*

{% include-markdown "fragments/signals_list_requirements.md" %}

---

---
##Commands
*These functions are already available in build instructions as `signals_list`. Use them as written.*
??? info "`signals_list.read(path_to_signals_list=None)`"

    Use this when a device or system build needs the rows of a signals list: a path, a file key, or the signals list of the revision that is open.
    
    Return signals-list rows from a path, file key, or the current project list.

??? info "`signals_list.new()`"

    Use this when a device build is starting the signals list and should replace the file that is already there.
    
    Create a signals TSV at fileio.path("signals list") with only the header row.

??? info "`signals_list.append(**kwargs)`"

    Use this when a device build needs one signal added to the signals list.
    
    Append one signal row. Missing optional fields are written as empty strings.
    
    Required: channel_id, signal, cavity, connector_id, channel_type, and exactly
    one of device_connector_mpn or harness_connector_mpn.
    
    **Args:**
    - `channel_id`: Channel this row belongs to. Use the same id on every signal of that channel.
    - `channel_type`: Channel type string. Every signal name it declares must be appended for this endpoint, and the string must parse as a channel type.
    - `signal`: Signal name. It must be one of the names declared by ``channel_type``.
    - `cavity`: Pin, socket, or stud this signal uses on its connector. Required, and unique on that connector.
    - `connector_id`: Connector that holds this signal. Every signal of one endpoint must use the same connector.
    - `repeat_channel_id`: Which endpoint, when the channel is a passthrough with two ends. The two repeats must differ. Leave blank when the channel has one endpoint. Optional.
    - `device_connector_mpn`: Manufacturer part number of the device-side connector. Set this or ``harness_connector_mpn``, not both, and use the same choice for every row of that connector.
    - `harness_connector_mpn`: Manufacturer part number of the harness-side connector. Set this or ``device_connector_mpn``, not both.

??? info "`signals_list.cavity_of_signal(channel_id, signal, path_to_signals_list, repeat_channel_id='')`"

    Use this when a build needs the cavity one signal uses on a channel endpoint.
    
    Return the cavity a signal uses on one channel endpoint.
    
    **Args:**
    - `channel_id`: Channel id of the signal whose cavity you want.
    - `signal`: Signal name on that channel, such as ``pos`` or ``neg``.
    - `path_to_signals_list`: Path, or file key, of the signals list to read.
    - `repeat_channel_id`: Which endpoint when the channel has two. Leave blank to match a single-endpoint channel. Optional.

??? info "`signals_list.connector_id_of_channel(channel_id, path_to_signals_list, repeat_channel_id='')`"

    Use this when a build needs the connector id of one channel in a signals list.
    
    Return ``connector_id`` for a channel endpoint.
    
    **Args:**
    - `channel_id`: Channel id whose connector you want.
    - `path_to_signals_list`: Path, or file key, of the signals list to read. Raises if that file does not exist.
    - `repeat_channel_id`: Which endpoint when the channel has two. Leave blank to match a single-endpoint channel. Optional.

---
