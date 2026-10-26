??? note "Default system build instructions"
    ```python

    # ===========================================================================
    #                CHANNEL AND PASSTHROUGH MAPPING
    # ===========================================================================
    # system.build() already called channel_map.new() - one row per channel endpoint.
    #
    # A patch is two endpoints. Each key is:
    #   (device_refdes, channel_id)                        # one endpoint
    #   (device_refdes, channel_id, repeat_channel_id)     # two endpoints (a face)
    # 3-tuple on a single-instance channel is an error; omitting the repeat on a
    # two-instance channel is an error.
    # Both endpoints (and any route() hop) must be in the same group of connected
    # harnesses. Unmated terminating connectors are in no group.
    #
    # channel_map.map(from_key, to_key=None, multi_ch_junction_key="")
    #
    # endpoint -> endpoint:
    # channel_map.map(("MIC1", "out1"), ("PRE1", "in1"))
    #
    # map onto one passthrough face. That face must have no harness, or the
    # last hop must be that harness that your channel is routed through
    # channel_map.map(("MIC1", "out1"), ("X1", "ch0", "A"))
    #
    # dual-map: two map() calls to the two faces of the same passthrough.
    # consumes both as patch ends; does not write a passthrough-map row.
    # channel_map.map(("MIC1", "out1"), ("X1", "ch0", "A"))
    # channel_map.map(("SNK1", "in1"), ("X1", "ch0", "B"))
    #
    # map a channel endpoint to a shared multi_ch_junction_key
    # channel_map.map(("MIC1", "out1"), multi_ch_junction_key="jcn1")
    
    # force a 1:1 patch regardless of channel-type compatibility.
    # Same signal names compile by name (pos still meets pos).
    # Different signal names stay pending until circuits_list.force()
    # pairs every from-side signal and drops every unused to-side signal.
    # The circuit keeps the from-side name. A from-side signal cannot be dropped;
    # swap the endpoints so the extra name is on the to side, then drop it.
    # channel_map.force(("MIC1", "out1"), ("PWR1", "in1"))
    # circuits_list.force(
    #     ("MIC1", "out1"),
    #     {"pos": "live", "neg": "neutral"},
    #     drop=["earth"],
    # )
    
    # remaining single-endpoint channels in the same group of connected harnesses,
    # compatible types, alphabetical. Skips every channel with more than one endpoint.
    channel_map.map_unmapped_compatibles_alphabetically()
    
    # this system's channel map, plus the channel map imported with every child
    # subsystem (recursive). Unmapped rows are omitted. A passthrough with both
    # faces mapped as patch ends becomes one row between the outer devices.
    # Inside a subsystem, refdes,
    # harness groups, junction ids, and connector/harness chains are prefixed:
    # subsystem.name, or subsystem.subsystem.name. Channel ids are not.
    channel_map.flatten()
    
    # one row per passthrough channel, plus routing context (availables per
    # group / from->to type / directionality). Dual-mapped passthroughs are omitted.
    passthrough_map.new()
    
    # add manual hops here (after new, before resolve).
    # passthrough_map.route(
    #     to_from_channel_device_refdes,  # either end of an already-mapped patch
    #     to_from_channel_id,
    #     intended_device_refdes,         # the passthrough device
    #     intended_channel_id=None,       # omit to pick any available channel
    #     repeat_channel_id=None,         # face the from-side arrives on; omit to infer
    # )
    # passthrough_map.route("MIC1", "out1", "X1")
    # passthrough_map.route(
    #     "MIC1", "out1", "X1", intended_channel_id="ch0", repeat_channel_id="A"
    # )
    
    # shortest remaining path; writes chain_of_connectors / chain_of_harnesses
    passthrough_map.resolve()
    
    # expand every mapped patch (and its passthrough path) into conductor circuits.
    # multi-ch junction rows become from_channel.signal -> mcj.signal (first type's signals)
    circuits_list.new()
    
    # ===========================================================================
    #        SEED THE INSTANCES LIST FROM CIRCUITS THAT EXIST SO FAR
    # ===========================================================================
    system_utils.create_instances_from_circuits_list()
    
    
    # ===========================================================================
    #                 RUN SYSTEM DESIGN CHECKS
    # ===========================================================================
    connector_list = fileio.read_tsv("system connector list")
    circuits = circuits_list.read()
    
    # check for circuits with no connectors
    system_utils.find_connector_with_no_circuit(connector_list, circuits)
    
    # TODO: HARNESS VALIDATION (imported harnesses contain conductors that match the required circuits)
    
    # ===========================================================================
    #              ADD APPEARANCES TO CHANNEL TYPES AND CIRCUITS
    # ===========================================================================
    # Channel traces use channel_default_appearance from the channel type's
    # channel_types.tsv. Circuit traces use signal_default_appearances for
    # signal_of_channel_type. The maps below write an instance appearance, and
    # an instance appearance that includes base_color replaces that default.
    # color -> channel types that should use that color
    channel_type_colors = {
        "#D59A10": [
            (1, "https://github.com/harnice/harnice-general-library"),
            (2, "https://github.com/harnice/harnice-general-library"),
        ],
        "#4039A1": [
            (5, "https://github.com/harnice/harnice-general-library"),
        ],
    }
    
    # channel type -> signal -> color
    circuit_signal_colors = {
        (1, "https://github.com/harnice/harnice-general-library"): {
            "pos": "#E24B4A",
            "neg": "#2E6B9F",
        },
        (2, "https://github.com/harnice/harnice-general-library"): {
            "pos": "#E24B4A",
            "neg": "#2E6B9F",
        },
        (5, "https://github.com/harnice/harnice-general-library"): {
            "chassis": "#4039A1",
        },
    }
    
    # apply the above appearances in the instances list as a simple base-color.
    for instance in instances_list.read():
        color = None
        channel_type = instance.get("this_channel_from_channel_type")
        if instance.get("item_type") == "circuit":
            for mapped_channel_type, signals in circuit_signal_colors.items():
                if channel_type == str(mapped_channel_type):
                    color = signals.get(instance.get("signal_of_channel_type"))
                    break
        if not color:
            for mapped_color, channel_types in channel_type_colors.items():
                if channel_type in [str(t) for t in channel_types]:
                    color = mapped_color
                    break
        if color:
            instances_list.modify(
                instance.get("instance_name"),
                {"appearance": {"base_color": color}},
            )
    
    # If you need more specific appearances, you can assign a full appearance dict to an instance like this:
    # {
    #     "base_color": "#E24B4A",          # required fill
    #     "outline_color": "black",         # optional path outline
    #     "parallelstripe": ["white"],      # optional stripes along the path
    #     "perpstripe": ["red", "white"],   # optional stripes across the path
    #     "twisted": "RH",                  # optional "RH", "LH", or None
    # }
    # example: twisted red/white pos conductor for channel type 1
    # circuit_signal_colors[(1, "https://github.com/harnice/harnice-general-library")]["pos"] = {
    #     "base_color": "#E24B4A",
    #     "outline_color": "black",
    #     "parallelstripe": ["white"],
    #     "twisted": "RH",
    # }
    # instances_list.modify(
    #     instance.get("instance_name"),
    #     {"appearance": circuit_signal_colors[(1, "https://github.com/harnice/harnice-general-library")]["pos"]},
    # )
    
    # ===========================================================================
    #              RECOMMEND CABLES ON CIRCUITS
    # ===========================================================================
    # Write rules at the system level based on system metrics to suggest information that is later consumed by
    # downstream harness projects about what cables to apply onto what conductors.
    
    # this_channel_from_channel_type -> library cable fields for instances_list.modify
    circuit_cable_mpns = {
        (1, "https://github.com/harnice/harnice-general-library"): {
            "mpn": "M27500-22SB2T23",
            "lib_repo": "https://github.com/harnice/harnice-aerospace-library",
            "lib_subpath": "M27500",
        },
        (2, "https://github.com/harnice/harnice-general-library"): {
            "mpn": "M27500-22SB2T23",
            "lib_repo": "https://github.com/harnice/harnice-aerospace-library",
            "lib_subpath": "M27500",
        },
    }
    
    # signal_of_channel_type -> cable identifier (must be unique in the cable JSON)
    circuit_cable_identifiers = {
        "pos": "black",
        "neg": "white",
        "chassis": "drain_wire",
    }
    
    # modify the instances list per the above
    cable_counter = 1
    channel_to_cable = {}  # keep every channel inside its own sequentially-counted cable
    for instance in instances_list.read():
        if instance.get("item_type") != "circuit":
            continue
    
        channel_type = chtype.parse(instance.get("this_channel_from_channel_type"))
        if channel_type in circuit_cable_mpns:
            channel_group = instance.get("channel_group")
            if channel_group not in channel_to_cable:
                channel_to_cable[channel_group] = f"cable-{cable_counter}"
                cable_counter += 1
            instances_list.modify(
                instance.get("instance_name"),
                {
                    **circuit_cable_mpns[channel_type],
                    "cable_group": channel_to_cable[channel_group],
                    "cable_identifier": circuit_cable_identifiers.get(
                        instance.get("signal_of_channel_type")
                    ),
                },
            )
    
    
    # ===========================================================================
    #              SUBSYSTEM SYMBOLS
    # ===========================================================================
    # Each run_macro call is one symbol (switch instances in the console to edit it).
    # scale is applied to the system block diagram primitive in the symbol.
    # Connector pins come from unique ICD connectors. The ICD is written after
    # build instructions, so a second build is required after ICD changes.
    # This macro also runs device signals-list / symbol-pin verification on the ICD.
    scale = 0.1
    
    build_utils.run_macro(
        "subsystem_symbol",
        "library/macros/system_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="subsystem-symbol-1",
        scale=scale,
    )
    
    # Orthographic drawing of the physical assembly. One view per call.
    # scale here is the drawing scale, not the symbol scale above.
    build_utils.run_macro(
        "physical_model_drawing",
        "library/macros/system_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="physical-1",
        scale=1,
        hidden_instances=[],
        orientation="front",
    )
    
    # Each run_macro call is one PDF file.
    build_utils.run_macro(
        "pdf_generator",
        "library/macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="pdf_drawing-1",
        page_setup={
            "pages": [
                {
                    "tblock_mpn": "harnice_tblock",
                    "tblock_lib_repo": "https://github.com/harnice/harnice-general-library",
                    "tblock_lib_subpath": "library/titleblocks/",
                    "page_size_in": [11.0, 8.5],
                    "tblock_anchor": "bottom-right",
                    "tblock_offset_px": [40.0, 40.0],
                    "text_replacements": {
                        "tblock-key-pagedesc": "block_diagram",
                        "tblock-key-desc": rev_history.info(field="desc"),
                        "tblock-key-pn": state.partnumber("pn"),
                        "tblock-key-drawnby": rev_history.info(field="drawnby"),
                        "tblock-key-rev": state.partnumber("R"),
                        "tblock-key-scale": scale,
                        "tblock-key-sheet": "autosheet",
                    },
                },
            ],
        },
    )
    
    
    # ===========================================================================
    #              FEATURES FOR RELATIVES
    # ===========================================================================
    # Any other harnice project can import and these functions using build_utils.run_instruction_from_relative().
    # The following functions are defaults. Adjust, remove, duplicate them as needed. Features for relatives are
    # intended to be used as a cohesive set of rules by any child part such that anything derived from this sytem
    # follows the same set of rules.
    
    
    def connector_chooser():
        # if the device-side connector MPN is x, assign mating connector y
        mating_connector_lookup_table = {
            #       x  :   y
            "XLR3M": {
                "mpn": "NC3FXX",  # Neutrik 3-pin female cable
                "lib_repo": "https://github.com/harnice/harnice-av-library",
                "lib_subpath": "neutrik",
                "lib_rev_used_here": None,
            },
            "XLR3F": {
                "mpn": "NC3MXX",  # Neutrik 3-pin male cable
                "lib_repo": "https://github.com/harnice/harnice-av-library",
                "lib_subpath": "neutrik",
                "lib_rev_used_here": None,
            },
            "DB25F": {
                "mpn": "M24308_4-3T",  # MIL-DTL-24308 25-pin crimp plug, nickel fluorocarbon
                "lib_repo": "https://github.com/harnice/harnice-aerospace-library",
                "lib_subpath": "dsub",
                "lib_rev_used_here": None,
            },
            "DB25M": {
                "mpn": "M24308_2-3T",  # MIL-DTL-24308 25-pin crimp receptacle, nickel fluorocarbon
                "lib_repo": "https://github.com/harnice/harnice-aerospace-library",
                "lib_subpath": "dsub",
                "lib_rev_used_here": None,
            },
        }
    
        # if the harness connector instance is named x, assign mating connector y
        # regardless of the device-side part number. leave empty unless you mean it.
        connector_by_instance_name = {
            #       x  :   y
            # "J1": {
            #     "mpn": "NC3FXX",
            #     "lib_repo": "https://github.com/harnice/harnice-av-library",
            #     "lib_subpath": "",
            #     "lib_rev_used_here": None,
            # },
        }
    
        for instance in instances_list.read():
            if instance.get("item_type") != "harness_connector":
                continue
    
            instance_name = instance.get("instance_name")
    
            mate = mating_connector_lookup_table.get(
                instance.get("device_side_connector_mpn")
            )
            if mate:
                instances_list.modify(
                    instance_name=instance_name,
                    instance_data=mate,
                )
                continue
    
            mate = connector_by_instance_name.get(instance_name)
            if mate:
                instances_list.modify(
                    instance_name=instance_name,
                    instance_data=mate,
                )
                continue
    
            # per-position rules (state.harness is the child's system position name):
            # if state.harness == "H01" and instance_name == "P1":
            #     instances_list.modify(
            #         instance_name,
            #         {
            #             "mpn": "NC3FXX",
            #             "lib_repo": "https://github.com/harnice/harnice-av-library",
            #             "lib_subpath": "neutrik",
            #             "lib_rev_used_here": None,
            #         },
            #     )
            #     continue
    
            # family choosers (D38999, Mighty Mouse, ...) are in the connector-choosing
            # examples ribbon - insert them here, then continue if they assign an mpn.
    
            # No rule matched. Keep the harness building with a placeholder.
            # Artwork goes in the general library at
            # connectors/example/EXAMPLE_CONNECTOR/rev1/drawing.svg.
            cli.warn(
                f"connector_chooser could not find a solution for {instance_name}; "
                "using EXAMPLE_CONNECTOR"
            )
            instances_list.modify(
                instance_name=instance_name,
                instance_data={
                    "mpn": "EXAMPLE_CONNECTOR",
                    "lib_repo": "https://github.com/harnice/harnice-general-library",
                    "lib_subpath": "connectors/example",
                    "lib_rev_used_here": None,
                },
            )
    
    ```