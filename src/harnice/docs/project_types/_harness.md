# Harnesses
A physical assembly that contains a set of electrical circuits that satisfies a channel map. Can also contain other parts and instructions about how to be built. 


---

## How to define a new harness

1. Make a folder for the part number of your harness somewhere on your computer. Click **Build** in Harnice, which will generate an example harness that you can then edit.

    ??? info "Building a project"

        {% include-markdown "fragments/how-to-build.md" %}

1. Edit the attributes of your new harness.

    ??? info "Editing the Attributes of a Project"

        {% include-markdown "fragments/editing_attributes.md" %}

If the harness was created from a system position, build instructions already import that harness. Connector and M85049 backshell policy belong on the system as ``connector_chooser`` and ``m85049_chooser``; the harness default build rules call them after the import.

The first build writes these instructions when `build.py` does not exist yet.

{% include-markdown "fragments/_harness_default_build_instructions.md" %}


## File Structure

Reference the files in your project by calling `fileio.path("file key")` from your script. They'll automatically use this structure:

```
fileio.dirpath("part_directory")           |-- yourpn/
                                               |-- earlier revs/
fileio.path("revision history")                |-- revhistory.csv
fileio.dirpath("rev_directory")                L-- your rev/
fileio.dirpath("networks")                         |-- networks/
fileio.path("flattened network")                   |   |-- flat.csv
fileio.path("chosen network")                      |   |-- chosen.json
fileio.path("available network")                   |   |-- available.json
fileio.path("chosen entity list")                  |   |-- entities.json
fileio.dirpath("contexts")                         |   L-- contexts/
fileio.dirpath("generated_svgs")                   |-- generated_svgs/
fileio.path("flattened network svg")               |   |-- flat.svg
fileio.path("circuits overlay")                    |   |-- circuits.svg
fileio.path("cable overlay")                       |   L-- cable.svg
fileio.path("build instructions")                  |-- build.py
fileio.path("instances list")                      |-- instances.tsv
fileio.path("library history")                     |-- libhist.tsv
fileio.dirpath("instance_data")                    L-- instance_data/
```
