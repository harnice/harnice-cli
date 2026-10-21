*Harnice defines a signals list to be a table that keeps track of every single signal going into and out of a device, which connector or channel it's part of, which signal names it has, which connector contact number or part number it has.*

To generate `build.py` from a pinout, ICD, datasheet, or spreadsheet, copy the **Device signals list** brief on [AI Prompts](../ai_prompts.md). Put the source file in the device revision folder (next to `build.py`) or give the agent that path.

1. If your device is very simple (has only a small number of signals), you are free to edit `fileio.path("signals list")` manually. If you choose to do this, delete `fileio.path("build instructions")` before clicking **Build** again, because the script will overwrite the signals list. However, it is recommended that you edit the Python build instructions instead to produce a validated, reproduceable, and portable result.
2. To edit the build instructions Python file, this quick-start guide should give you an idea of how the default script is set up, and how you might be able to change it to suit your needs. The goal of this file is to make a signals list. Do not be concerned with writing this efficiently, as it will only be ran while building the device.
    1. List, utility, and channel-type modules (`signals_list`, `chtype`, and the rest) are already available in the script — you do not need to import them from harnice.
    1. Copy your channel_type touples in from earlier notepad step. Again, these are relevant only to the device you're trying to make. The dictionary is used to store these here so that you can reference the touples in a human-readable format in this script only.
`ch_type_ids = {`
`    "in": (1, "https://github.com/harnice/harnice-general-library"),`
`    "out": (4, "https://github.com/harnice/harnice-general-library"),`
`    "chassis": (5, "https://github.com/harnice/harnice-general-library")`
`}`
    1. Define your pinouts. Default convention is this dictionary, where if you reference something like `xlr_pinout.pos`, this dictionary should return the cavity name. Reminder: channels do not contain information about pinouts or connectors so this has to be done at each device. If you use the same pinout across multiple devices, you may consider importing that definition from a python library elsewhere.
`xlr_pinout = {`
`    "pos": 2,`
`    "neg": 3,`
`    "chassis": 1`
`}`
        1. Define your connector part numbers. Default convention is this dictionary, where you can resolve the part number by finding the connector name. `mpn_for_connector(connector_name)` will search your definition dictionary for a connector name and return its part number.
`connector_mpns = {`
`    "XLR3F": ["in1", "in2"],`
`    "XLR3M": ["out1", "out2"]`
`}`

        1. `signals_list.new()` will overwrite the existing signals list with a blank one, which will be repopulated while the rest of this script is executed.
        2. Bespoke logic should be written in python for the remainder of this script, making use of patterns and naming conventions of this specific device. 
        3. I'd recommend you use a python editor on your screen at the same time as a csv editor that automatically refreshes (vscode, easycsveditor on the mac store) so that you can update your python, run builds frequently, and watch the updates in realtime on your csv