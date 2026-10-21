# Interacting with Circuits Lists
A list of every individual electrical connection that must be present in your system or harness to satisfy your channel and passthrough maps.

---
##Columns 
*Columns are automatically generated when `circuits_list.new()` is called. Additional columns are ok but discouraged due to consistency. If you need more columns, use data structures in build instructions.*

| Column | Description |
|--------|-------------|
| `harness` | documentation needed |
| `harness_chain_index` | 0-based index into channel map ``chain_of_harnesses`` for this segment |
| `circuit_id` | documentation needed |
| `from_signal` | from-side signal name; also the name used on passthrough hops |
| `to_signal` | to-side signal name when circuits_list.force() paired different names; blank when both ends use from_signal |
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
##Commands
*These functions are already available in build instructions as `circuits_list`. Use them as written.*
??? info "`circuits_list.force(from_key, signal_pairs, drop=())`"

    Pair the signals of one pending ``channel_map.force()`` patch.
    
    ``from_key`` is the same endpoint key passed as the first argument to
    ``channel_map.force()``. ``signal_pairs`` maps every from-side signal name
    to a to-side signal name (``{"pos": "live", "neg": "neutral"}``). ``drop``
    lists every to-side signal left unwired (``drop=["earth"]``).
    
    The circuit keeps the from-side name. The to-side cavity is looked up
    under the paired name. A from-side signal cannot be dropped: if the from
    channel has a signal the to channel does not, swap which endpoint is
    ``from_key`` so the extra name is on the to side, then drop it.
    
    Raises ``ValueError`` if ``from_key`` is not pending (the signal names
    already matched, or ``channel_map.force()`` was not called), or if any
    from-side name is unpaired or any to-side name is neither paired nor
    dropped.

??? info "`circuits_list.new()`"

    Build the circuits list from the channel map and passthrough map.
    
    Uses ``chain_of_connectors`` / ``chain_of_harnesses`` (from ``passthrough_map.resolve()``)
    and ordered ``satisfaction`` rows on the passthrough map for passthrough channel IDs.
    
    A channel-map row with ``multi_ch_junction_id`` and no ``to_*`` partner becomes
    one circuit per signal: from is ``from_channel.signal``, to is ``mcj.signal``.
    Signal names come from the first channel type seen on that junction id.
    
    A patch from ``channel_map.force()`` whose signal names differ must
    already have been burned down by ``circuits_list.force()``. Those circuits
    keep the from-side name in ``from_signal`` and look up the to-side cavity under
    ``to_signal``. Passthrough hops are still looked up under ``from_signal``.
    Any pending forced patch raises ``ValueError``.
    
    Clears any existing circuits list.

