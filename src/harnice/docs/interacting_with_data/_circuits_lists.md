# Interacting with Circuits Lists
A list of every individual electrical connection that must be present in your system or harness to satisfy your channel and passthrough maps.

---
##Columns 
*Columns are automatically generated when `circuits_list.new()` is called. Additional columns are not supported and may result in an error when parsing.*

| Column | Description |
|--------|-------------|
| `harness` | documentation needed |
| `harness_chain_index` | 0-based index into channel map ``chain_of_harnesses`` for this segment |
| `circuit_id` | documentation needed |
| `signal` | documentation needed |
| `harness_from_refdes` | documentation needed |
| `harness_from_channel_id` | documentation needed |
| `harness_from_connector_name` | documentation needed |
| `harness_from_cavity` | documentation needed |
| `harness_to_refdes` | documentation needed |
| `harness_to_channel_id` | documentation needed |
| `harness_to_connector_name` | documentation needed |
| `harness_to_cavity` | documentation needed |
| `from_side_device_refdes` | documentation needed |
| `from_side_device_chname` | documentation needed |
| `to_side_device_refdes` | documentation needed |
| `to_side_device_chname` | documentation needed |
| `from_channel_type` | documentation needed |
| `to_channel_type` | documentation needed |
| `multi_ch_junction_id` | set when the circuit is from_channel.signal → mcj.signal |


---
##Commands:
*These functions are already available in build instructions as `circuits_list`. Use them as written.*
??? info "`circuits_list.new()`"

    Build the circuits list from the channel map and passthrough map.
    
    Uses ``chain_of_connectors`` / ``chain_of_harnesses`` (from ``passthrough_map.resolve()``)
    and ordered ``satisfaction`` rows on the passthrough map for passthrough channel IDs.
    
    A channel-map row with ``multi_ch_junction_id`` and no ``to_*`` partner becomes
    one circuit per signal: from is ``from_channel.signal``, to is ``mcj.signal``.
    Signal names come from the first channel type seen on that junction id.
    
    Overwrites any existing circuits list.

