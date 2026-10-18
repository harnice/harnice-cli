# Interacting with Signals Lists
A Signals List is an exhaustive list of every signal going into or out of a thing. Signals Lists are the primary way Harnice stores information about devices, and act as the source of truth for devices.

---
## Signals List Validation Checks:
*(These are automatically validated when you build the device that owns the list.)*

{% include-markdown "fragments/signals_list_requirements.md" %}
---
##Columns 
*Columns are automatically generated when `signals_list.new()` is called. Additional columns are not supported and may result in an error when parsing.*
### Columns of Signals Lists 


---

---
##Commands:
*These functions are already available in build instructions as `signals_list`. Use them as written.*
??? info "`signals_list.new()`"

    Create a signals TSV at fileio.path("signals list") with only the header row.

??? info "`signals_list.append(**kwargs)`"

    Append one signal row. Missing optional fields are written as empty strings.
    
    Required: channel_id, signal, cavity, connector_id, channel_type, and exactly
    one of device_connector_mpn or harness_connector_mpn.

??? info "`signals_list.cavity_of_signal(channel_id, signal, path_to_signals_list, repeat_channel_id='')`"

    Documentation needed.

??? info "`signals_list.connector_id_of_channel(channel_id, path_to_signals_list, repeat_channel_id='')`"

    Return ``connector_id`` for a channel endpoint.

---
