# Devices
Any electrical item, active or passive, that is not a harness.

A device may have terminating **channel endpoints** (one connector per channel) and **passthroughs** (the same `channel_id` on exactly two connectors, each with a `repeat_channel_id`). Both are devices; place them with Place device.


---

##  How device data is stored

The primary data structure of a device is a TSV called a “signals_list”. Signals lists can be written manually or generated from a python script that can help automate the generation of lists for complicated devices.

The definition of a device lives in a TSV file called a "Signals List".

??? info "Signals List"

    {% include-markdown "interacting_with_data/_signals_lists.md" %}

## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")          |-- yourpn/
                                              |-- earlier revs/
fileio.path("revision history")               |-- revhistory.csv
fileio.dirpath("rev_directory")               L-- your rev/
fileio.path("build instructions")                 |-- build.py
fileio.path("signals list")                       |-- signals.tsv
fileio.path("attributes")                         |-- attributes.json
fileio.path("block diagram symbol")               |-- symbol.svg
fileio.path("configuration setup")                L-- config.yaml
```


---

## Building a device

When a Device is built in Harnice, here's what happens:

1. Harnice runs the build instructions if it's found in the device directory.
1. The signals list is validated and verified.
1. A block diagram symbol SVG that can represent this device in a system block diagram is generated or updated based on the signals list.

---

## How to define a new device
1. Ensure every channel going into or out of a device has a type defined in a repo somewhere.

    ??? info "Channel Types"

        {% include-markdown "project_types/_channel_type.md" %}

1. Make a folder for the part number of your device somewhere on your computer. Click **Build** in Harnice, which will generate an example device that you can then edit.

    ??? info "Building a project"

        {% include-markdown "fragments/how-to-build.md" %}

1. Edit the attributes of your new device.

    ??? info "Editing the Attributes of a Project"

        {% include-markdown "fragments/editing_attributes.md" %}

1. Edit the signals list of your new device. To generate `build.py` from a pinout, ICD, or datasheet, paste the **Device signals list** prompt on [AI Prompts](../ai_prompts.md); put the source file next to `build.py` in the revision folder.

    ??? info "Updating a Signals List"

        {% include-markdown "fragments/how-to-update-signals-list.md" %}

1. Work on your block diagram symbol.

    ??? info "Working on a Block Diagram Symbol"

        {% include-markdown "fragments/working-with-a-block-diagram-symbol.md" %}


---

##  Device modeling for simulation of behavior in a system (future work)

It is often useful to model how an entire electrical system will behave by aggregating up behaviors of many contained devices and how they interact with each other.

Eventually, Harnice will allow you to do this automatically within the same source-of-truth system definition that defines your harnesses.

When this feature is implemented, devices will contain an automatically generated .kicad_esch file that will allow the user to define a schematic that represents the lump behavior of your device. Harnice will ensure that every signal on your signals list is accounted for in the simulation esch, and the user may choose to connect any simulation device between those symbols. This way, when the device is used in a system block diagram, this device esch can referenced by the system simulator and its behavior can be considered while running an entire system simulation profile.