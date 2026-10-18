### General Signals List Rules

 - Every signal in the Signals List must be contained by a pre-defined channel type

    ??? info "Channel Types"
        {% include-markdown "project_types/_channel_type.md" %}

 - Each signal in the signals list must have every other signal defined by its channel type also present in the list.
    - you can't just define 'positive' if the channel type requires 'positive' and 'negative'

 - Each signal defined in the list is contained by one or more cavities of connectors. 
     - you can't "cap off" or not populate one of the signals within a channel because that changes the channel type.

 - Every combination of (channel_id, signal, repeat_channel_id) must be unique within the signals list
    - you can’t have two i.e. “ch1, pos” signals on the same endpoint
    - if you need to break one signal out onto multiple conductors, you'll need to change the channel type to one that defines multiple conductors (i.e. named "ch1, pos-1")

 - Each channel endpoint lives on exactly one connector_id
    - a **passthrough** is the same `channel_id` on two connectors, each with its own `repeat_channel_id`
    - signals that belong to one endpoint cannot be split across connectors
    - more than two endpoints on one `channel_id` is an error

### Configurable Device Signals List Rules

A configuration is **how** a device is used, not **what** it is. The same part number can have different electrical behavior (balanced vs unbalanced, voltage setting, phantom on/off) without a new part number, as long as form, fit, and function of the hardware stay the same.

The signals list is not a pile of alternate rows that get filtered. Build instructions write **one** signals list for the answers currently in `configuration` (a dict). Harnice fills that dict from the defaults in `fileio.path("configuration setup")`, or—when the device is placed in a system—from that instance's answers on the block diagram / BOM.

  - **Declare fields in `fileio.path("configuration setup")`, then read them in build instructions**
    - Each field has an `id`. In the script, use `configuration["that_id"]` (channel type, select, boolean, number, and so on).
    - You can have as many fields as you need. One field is enough for an SM58 that is either balanced or unbalanced. A mixing console might have a field per input (mic vs line, balanced vs unbalanced) so automatic channel mapping sees the type you actually set, and the instance records how to set the hardware up.
    - Field types, validation, `show_if`, and a full YAML example are in the device configurations documentation.

  - **The list you emit still has to obey the general signals-list rules**
    - Complete endpoints, unique `(channel_id, signal, repeat_channel_id)`, one connector per endpoint. Validation only sees the list for this configuration.

  - **Do not use configuration to change the physical part**
    - If connectors, cavities, or the build of the device change, that is a new part number, not a configuration. Unused signals that are still on the connector should stay in the list.

### Passthrough Signals List Rules

 - A passthrough is exactly two endpoints of the same `channel_id`, each with a distinct `repeat_channel_id`
 - The two channel types must be compatible with each other
     - this is so a patch that crosses the device still mates compatible types on both faces
 - A single-endpoint channel must leave `repeat_channel_id` blank; a 3-tuple in `map()` on that channel is an error
