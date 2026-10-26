# to access configuration information, use 'configuration' (a dictionary object).
# harnice will pass in defaults or the relevant refdes configs automatically.
# print(configuration)

# ---------------------------------------------------------------------------
# Device example: four XLR channels (two in, two out).
# Each channel has one instance, so repeat_channel_id stays blank.
# ---------------------------------------------------------------------------

ch_type_ids = {
    "in": (1, "https://github.com/harnice/harnice-general-library"),
    "out": (4, "https://github.com/harnice/harnice-general-library"),
    "chassis": (5, "https://github.com/harnice/harnice-general-library")
}

xlr_pinout = {
    "pos": 2,
    "neg": 3,
    "chassis": 1
}

connector_mpns = {
    "XLR3F": ["in1", "in2"],
    "XLR3M": ["out1", "out2"]
}

def mpn_for_connector(connector_name):
    for mpn, conn_list in connector_mpns.items():
        if connector_name in conn_list:
            return mpn
    return None

signals_list.new()

for connector_name in ["in1", "in2", "out1", "out2"]:
    if connector_name.startswith("in"):
        channel_type = ch_type_ids["in"]
    elif connector_name.startswith("out"):
        channel_type = ch_type_ids["out"]
    else:
        continue

    channel_name = connector_name
    connector_mpn = mpn_for_connector(connector_name)

    for signal in chtype.signals(channel_type):
        signals_list.append(
            channel_id=channel_name,
            signal=signal,
            connector_id=connector_name,
            cavity=xlr_pinout.get(signal),
            channel_type=channel_type,
            device_connector_mpn=connector_mpn
        )

    signals_list.append(
        channel_id=f"{channel_name}-shield",
        signal="chassis",
        connector_id=connector_name,
        cavity=xlr_pinout.get("chassis"),
        channel_type=ch_type_ids["chassis"],
        device_connector_mpn=connector_mpn
    )


# A passthrough is the same channel_id on exactly two connectors. Every row
# needs a repeat_channel_id, and the two repeats must differ. Use
# harness_connector_mpn when the harness owns that face.
#
#
# How to use the relevant signals list functions:
# signals_list.append(
#     channel_id="ch0",
#     repeat_channel_id="A",
#     signal="pos",
#     connector_id="A",
#     cavity=2,
#     channel_type=ch_type_ids["in"],
#     harness_connector_mpn="XLR3F",
# )
# signals_list.append(
#     channel_id="ch0",
#     repeat_channel_id="B",
#     signal="pos",
#     connector_id="B",
#     cavity=2,
#     channel_type=ch_type_ids["out"],
#     harness_connector_mpn="XLR3M",
# )
#
# Define the physical model of your device in this section. Choose from
# default macros or import your own STEP file. 
# Each macro saves with fileio.path("body"), the device's body.step.
# Rectangular sketch surface "front" is the face at y = 0.
# images = {
#     "front": os.path.join(fileio.dirpath("body_images"), "front.png"),
# }
# build_utils.run_macro(
#     "build_rectangular_physical_model",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     params={"width": 4, "height": 2, "depth": 6},
#     images=images,
# )
# Rack sketch surface "bottom" is the face at z = 0. The front ears are "front".
# images = {
#     "bottom": os.path.join(fileio.dirpath("body_images"), "bottom.png"),
# }
# build_utils.run_macro(
#     "build_rackmount_physical_model",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     params={"u": 2, "depth": 10},
#     images=images,
# )
# Rack enclosure. depth and units are the macro arguments. The front panel is
# 19 inches wide and the body is 19 inches wide. 1U is 1.75in tall. 
# build_utils.run_macro(
#     "build_rackmount_enclosure",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     depth=10,
#     units=2,
# )
# build_utils.run_macro(
#     "build_physical_model_from_step",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     path_to_step="vendor/chassis.step",
# )
