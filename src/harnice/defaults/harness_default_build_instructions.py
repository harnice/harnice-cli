import copy
import math
import os
import random

# ===========================================================================
#                 pull harness definition from system
# ===========================================================================

system_utils.import_harness_from_harnice_system(
    system_pn=rev_history.info().get("source_part_number"),
    system_rev=rev_history.info().get("source_revision"),
    system_lib_repo=rev_history.info().get("source_lib_repo"),
    system_lib_subpath=rev_history.info().get("source_subpath"),
    target_harness=rev_history.info().get("source_refdes"),
)
rev_history.overwrite(
    {
        "desc": f"HARNESS '{rev_history.info().get('source_refdes')}' FROM SYSTEM '{rev_history.info().get('source_part_number')}-{rev_history.info().get('source_revision')}'",
    }
)

# ===========================================================================
#                  HARNESS BUILD RULES
# ===========================================================================

# Connector policy lives on the parent system.
build_utils.run_instruction_from_relative(
    "connector_chooser",
    rev_history.info().get("source_part_number"),
    rev_history.info().get("source_lib_repo"),
    rev_history.info().get("source_subpath"),
    rev_history.info().get("source_revision"),
)

# If you want to define build rules local to this harness, write them here.
# Don't forget to rely on pre-defined functions and examples in the ribbon toolbar above.

# After assigning parts to instances, import them into this harness's file tree.

instances_list.raise_error_on_unassigned_connectors()

for instance in instances_list.read():
    if instance.get("item_type") in ["harness_connector", "backshell"]:
        library_utils.pull(instance)

# ===========================================================================
#          PROCESS AVAILABLE NETWORK DOWN INTO A CHOSEN NETWORK
# ===========================================================================

# available network (cad or manual) -> chosen network (modified subset) -> flattened network (visually arranged in 2D)
#
# Every node and segment has a "source_of_truth": "gui" (drawn in the
# available network editor, or added below for you to edit) or the id of the
# routing context it was read from. The available network editor shows
# exactly what is in available.json, so anything this build adds to the
# available network is saved there.

# Load available.json with every node and segment already in it.
available = available_network.load()

# Drop every node and segment whose source of truth is not "gui", then
# load them again, fresh from their contexts. Today the only context with
# nodes and segments is the source system's physical model: a node at each
# mating connector ("<device_refdes>.<mating_connector_id>") and each segment
# routed there.
available = available_network.keep_only_gui(available)
for mating_connector in physical_assembly.list_mating_connectors(rev_history.info()):
    # To leave one out, skip it here, for example:
    # if mating_connector["node_id"].startswith("RACK-2."):
    #     continue
    available["nodes"].append(mating_connector)
for segment in physical_assembly.list_segments(rev_history.info()):
    # To leave one out, skip it here, for example:
    # if segment["segment_id"] == "S1":
    #     continue
    available["segments"].append(segment)
available_network.save(available)

# The chosen network starts as a copy of the whole available network.
chosen = copy.deepcopy(available)

# A node named after the device mating connector a harness connector plugs
# into ("<device_side_refdes>.<device_side_connector_id>"), whatever its
# source of truth, becomes that connector's "<connector_group>.node", turned
# 180 degrees to face the device.
chosen = bundle_network_utils.adopt_mating_connector_nodes(chosen, replace_existing=False)

# Two nodes with the same name, whatever their source of truth, is an error.
bundle_network_utils.raise_on_duplicate_node_ids(chosen)

# Give every segment end that is not on a node a node.
chosen = bundle_network_utils.end_all_segments_in_nodes(chosen)

# Gather the collection of all instances with item_type == node
needed_nodes = []
for instance in instances_list.read():
    if instance.get("item_type") == "node":
        name = instance.get("instance_name")
        if name not in needed_nodes:
            needed_nodes.append(name)

# Add every needed node the chosen network does not have yet, to both the
# available and the chosen network. It goes 6 to 18 inches from the average
# location of the chosen nodes, at a random angle in the XY plane. Its 
# source of truth is "gui", so it is saved in available.json and the next 
# build reuses it.
center = bundle_network_utils.average_location(chosen["nodes"])
for node_id in needed_nodes:

    # Skip a needed node if the chosen network already contains that node
    already_in_chosen = False
    for node in chosen["nodes"]:
        if node["node_id"] == node_id:
            already_in_chosen = True
            break
    if already_in_chosen:
        continue

    # Choose a random location for the new node
    distance = random.uniform(6.0, 18.0)
    angle = random.uniform(0.0, 2.0 * math.pi)
    location = [
        round(center[0] + distance * math.cos(angle), 3),
        round(center[1] + distance * math.sin(angle), 3),
        round(center[2], 3),
    ]
    while location in [node["location"] for node in chosen["nodes"]]:
        location[0] += 1.0
    new_node = {
        "node_id": node_id,
        "location": location,
        "alpha": None,
        "beta": None,
        "gamma": None,
        "source_of_truth": "gui",
    }

    # Add it to the chosen and available networks at the same time
    chosen["nodes"].append(dict(new_node))
    if node_id not in [node["node_id"] for node in available["nodes"]]:
        available["nodes"].append(dict(new_node))

# Join every needed node into one route. A harness with fewer than two needed
# nodes (a single connector) has nothing to join, so it skips this.
if len(needed_nodes) > 1:

    # Look up chosen nodes by name.
    node_by_id = {}
    for node in chosen["nodes"]:
        node_by_id[node["node_id"]] = node
    segment_ids = [segment["segment_id"] for segment in available["segments"] + chosen["segments"]]

    # With more than three connectors and no segments in the available
    # network yet, add a "hub" node first, at the average location of the
    # needed nodes, to both networks. Its source of truth is "gui".
    connector_count = 0
    for instance in instances_list.read():
        if instance.get("item_type") == "harness_connector":
            connector_count += 1
    if "hub" not in node_by_id and connector_count > 3 and len(available["segments"]) == 0:
        location = bundle_network_utils.average_location(
            [node_by_id[node_id] for node_id in needed_nodes]
        )
        location = [round(value, 3) for value in location]
        # if the average location is already taken, move it along +X until it is free
        while location in [node["location"] for node in chosen["nodes"]]:
            location[0] += 1.0
        hub = {
            "node_id": "hub",
            "location": location,
            "alpha": None,
            "beta": None,
            "gamma": None,
            "source_of_truth": "gui",
        }
        chosen["nodes"].append(dict(hub))
        available["nodes"].append(dict(hub))
        node_by_id["hub"] = chosen["nodes"][-1]

    # connected_nodes is the list of needed nodes that one route already joins.
    # It starts with "hub" when there is one, otherwise with one needed node
    # picked at random. The rest are shuffled and added one at a time below.
    order = []
    for node_id in needed_nodes:
        if node_id != "hub":
            order.append(node_id)
    random.shuffle(order)
    if "hub" in node_by_id:
        connected_nodes = ["hub"]
    else:
        connected_nodes = [order.pop(0)]

    # Add the needed nodes to connected_nodes one at a time. After each one,
    # if calculate_possible_sub_networks finds no route that joins every node
    # in connected_nodes, add a segment to the new node from "hub" when there
    # is one, otherwise from the nearest node already in connected_nodes. The
    # segment goes into both the available and the chosen network, named
    # "<new node>_leg" ("_leg-2", "_leg-3", ... when taken). Its source of
    # truth is "gui", so it is saved in available.json and the next build
    # reuses it.
    for node_id in order:

        # Add the next needed node to connected_nodes.
        connected_nodes.append(node_id)

        # If existing segments already make a route that touches every node
        # in connected_nodes, the new node is connected. Nothing to add; move on.
        if len(bundle_network_utils.calculate_possible_sub_networks(chosen, connected_nodes)) > 0:
            continue

        # The new node is not connected to the others yet. Pick the node the
        # new segment starts from: "hub" when there is one.
        if "hub" in node_by_id:
            from_id = "hub"

        # Otherwise, the node already in connected_nodes that is closest to
        # the new node. connected_nodes[:-1] is every node in the list except
        # the new one.
        else:
            from_id = None
            shortest = None
            for other in connected_nodes[:-1]:
                distance = math.dist(node_by_id[other]["location"], node_by_id[node_id]["location"])
                if shortest is None or distance < shortest:
                    shortest = distance
                    from_id = other

        # Name the segment "<new node>_leg". If that name is already used in
        # either network, try "<new node>_leg-2", "-3", ... until one is free.
        segment_id = f"{node_id}_leg"
        index = 2
        while segment_id in segment_ids:
            segment_id = f"{node_id}_leg-{index}"
            index += 1

        # Remember the name so a later segment in this loop can't reuse it.
        segment_ids.append(segment_id)

        # A straight segment from the start node to the new node. Its source of
        # truth is "gui", so it is saved in available.json and the next build
        # finds it there instead of adding it again.
        new_segment = {
            "segment_id": segment_id,
            "type": "line",
            "location_at_end_a": list(node_by_id[from_id]["location"]),
            "location_at_end_b": list(node_by_id[node_id]["location"]),
            "spline_control_points": [],
            "source_of_truth": "gui",
        }

        # Add it to both networks right away, so the route check for the next
        # node in the loop sees this segment.
        chosen["segments"].append(dict(new_segment))
        available["segments"].append(dict(new_segment))

# Overwrite networks/available.json with the whole available dict: the "gui"
# items already in it, the items just reloaded from the source system, and
# every node and segment added above. The chosen network is saved further
# down by chosen_network.save, once one route is picked.
available_network.save(available)

# Find any possible solution within the network
found_solutions = bundle_network_utils.calculate_possible_sub_networks(
    input_network=chosen,
    set_of_required_nodes=needed_nodes,
)

# Optionally prefer a solution containing particular imported segments. Leave
# these empty unless the parent system provides stable IDs worth selecting on.
preferred_segment_ids = []  # example: ["segment-1", "segment-2"]
preferred_node_ids = []  # example: ["branch-node"]
if len(found_solutions) > 1 and (preferred_segment_ids or preferred_node_ids):
    sorted_solutions = bundle_network_utils.find_network_with(
        input_networks=found_solutions,
        segment_ids=preferred_segment_ids,
        node_ids=preferred_node_ids,
    )
    found_solutions = sorted_solutions

# Ensure only one solution is found
number_of_found_solutions = len(found_solutions)
if number_of_found_solutions != 1:
    raise ValueError(f"Available network contains {number_of_found_solutions} solution(s)")
bundle_network = found_solutions[0]


# Clock a backshell towards the next nearest node in the chosen network
# bundle_network = bundle_network_utils.clock_backshell(
#     network=bundle_network,
#     connector_group="P1",
#     towards_node="incident",
#     round_to_nearest_angle=15,
# )

# Move chosen nodes around to keep the mating faces of the connectors at the same position as available based on the size of the assigned parts
for instance in instances_list.read():
    group = instance.get("connector_group")
    node_id = f"{group}.node"
    if instance.get("item_type") == "backshell":
        bundle_network = bundle_network_utils.clock_backshell(bundle_network, group)
    elif instance.get("item_type") == "harness_connector": # if it's a connector that has no backshell, move chosen node to the connector
        if instances_list.instance_in_connector_group_with_item_type( # backshell-doesn't-exist check
            instance.get("connector_group"), "backshell"
        ):
            continue
        bundle_network = bundle_network_utils.move_node(
            bundle_network,
            node_id,
            bundle_network_utils.output_offset(instance, "3d-mate"),
        )

# ===========================================================================
#                  FLATTEN THE CHOSEN NETWORK
# ===========================================================================

# Save the chosen network back to disk
chosen_network.save(bundle_network)

# Build the flattened network
flattened_network.derive(bundle_network)


# ===========================================================================
#                  ASSIGN CABLES AND CONDUCTORS
# ===========================================================================

# Process usable cable recommendations from the system. Recommendations are
# optional, so incomplete or stale values should not make a new harness fail.
cable_recommendations = []
for instance in instances_list.read():
    if instance.get("item_type") != "conductor":
        continue

    cable_group = instance.get("cable_group")
    if cable_group not in ["", None]:
        recommendation = {
            "instance_name": instance.get("instance_name"),
            "cable_group": cable_group,
            "mpn": instance.get("mpn"),
            "lib_repo": instance.get("lib_repo"),
            "lib_subpath": instance.get("lib_subpath"),
            "cable_identifier": instance.get("cable_identifier"),
        }
        cable_recommendations.append(recommendation)
        cable_utils.prepare_for_conductor_assign(recommendation["instance_name"])

cables_created = [] # fill up with cable refdes's as they get processed
for recommendation in cable_recommendations:
    required_fields = ["mpn", "lib_repo", "cable_identifier"]
    missing_fields = [
        field
        for field in required_fields
        if recommendation.get(field) in ["", None]
    ]
    if missing_fields:
        cli.warn(
            f"Skipping incomplete cable recommendation for "
            f"'{recommendation['instance_name']}': missing "
            f"{', '.join(missing_fields)}"
        )
        continue

    cable_group = recommendation["cable_group"]
    if cable_group not in cables_created:
        cable_utils.new_cable(
            cable_group,
            recommendation["mpn"],
            recommendation["lib_repo"],
            recommendation["lib_subpath"],
        )
        cables_created.append(cable_group)

    try:
        cable_utils.assign_conductor_to_cable(
            recommendation["instance_name"],
            cable_group, # which cable instance name gets assigned
            recommendation["cable_identifier"], # which unique conductor within the cable goes here
        )
    except ValueError as error:
        cli.warn(
            f"Skipping unusable cable recommendation for "
            f"'{recommendation['instance_name']}': {error}"
        )


# assign a cable not recommended by the upstream system 
# cable_utils.new_cable(
#     "W1",
#     "M27500-22SB2T23",
#     "https://github.com/harnice/harnice-aerospace-library",
#     "M27500",
# )
# cable_utils.assign_conductor_to_cable("conductor-1", "W1", "black")
# cable_utils.assign_conductor_to_cable("conductor-2", "W1", "white")



# route conductors between their end nodes, then map each cable onto the
# segments shared by all of its conductors
cable_utils.map_cables_and_conductors_to_segments()

# ===========================================================================
#                  CALCULATE SEGMENT BUNDLE DIAMETERS
# ===========================================================================
for instance in instances_list.read():
    if instance.get("item_type") == "segment":
        cable_utils.calculate_bundle_diameter(instance.get("instance_name"))

# ===========================================================================
#                   ASSIGN BOM LINE NUMBERS
# ===========================================================================
for instance in instances_list.read():
    if instance.get("item_type") in ["harness_connector", "cable", "backshell"]:
        instances_list.modify(instance.get("instance_name"), {"bom_line_number": True})
instances_list.assign_bom_line_numbers()

# ===========================================================================
#                  ADD BUILD NOTES
# ===========================================================================
for rev_row in rev_history.read():
    if rev_history._revs_equivalent(rev_row.get("rev"), state.rev):
        note_utils.make_rev_history_notes(rev_row)

for instance in instances_list.read():
    for note in note_utils.get_lib_build_notes(instance):
        note_utils.new_note(
            "build_note", note, affectedinstances=[instance.get("instance_name")]
        )

note_utils.assign_buildnote_numbers()

# example: add notes to describe actions
# note_utils.new_note(
#     "build_note",
#     "do this",
#     affectedinstances=["X1.B.conn"]
# )
# note_utils.new_note(
#     "build_note",
#     "do that"
# )

# example: combine buildnotes if their texts are similar
# note_utils.combine_notes("Torque backshell to connector at 40 in-lbs","Torque backshell to connector at about 40 in-lbs")


# ===========================================================================
#                  PUT TOGETHER FORMBOARD SVG INSTANCE CONTENT
# ===========================================================================
instances = instances_list.read()
note_instances = []
for instance in instances:
    if instance.get("item_type") == "note":
        note_instances.append(note_utils.parse_note_instance(instance))

formboard_overview_instances = []
formboard_detail_instances = []
for instance in instances:
    if instance.get("item_type") not in [
        "harness_connector",
        "backshell",
        "terminal",
        "segment",
        "node",
        "origin",
    ]:
        continue

    formboard_overview_instances.append(instance)
    formboard_detail_instances.append(instance)

    detail_flag_note_counter = 1
    overview_flag_note_counter = 1

    if instance.get("item_type") in ["harness_connector", "backshell"]:
        bom_flagnote = note_utils.make_bom_flagnote(
            instance, f"flagnote-{detail_flag_note_counter}"
        )
        if bom_flagnote is not None:  # None for parts kept off the BOM
            formboard_detail_instances.append(bom_flagnote)
            detail_flag_note_counter += 1

        formboard_detail_instances.append(
            note_utils.make_part_name_flagnote(
                instance, f"flagnote-{detail_flag_note_counter}"
            )
        )
        detail_flag_note_counter += 1

    if instance.get("item_type") == "harness_connector":
        formboard_overview_instances.append(
            note_utils.make_part_name_flagnote(
                instance, f"flagnote-{overview_flag_note_counter}"
            )
        )
        overview_flag_note_counter += 1

    for note_instance in note_instances:
        if note_instance.get("note_type") == "build_note":
            if instance.get("instance_name") in note_instance.get(
                "note_affected_instances"
            ):
                formboard_detail_instances.append(
                    note_utils.make_buildnote_flagnote(
                        note_instance, instance, f"flagnote-{detail_flag_note_counter}"
                    )
                )
                detail_flag_note_counter += 1

        if note_instance.get("note_type") == "rev_change_callout":
            if instance.get("instance_name") in note_instance.get(
                "note_affected_instances"
            ):
                formboard_detail_instances.append(
                    note_utils.make_rev_change_flagnote(
                        note_instance, instance, f"flagnote-{detail_flag_note_counter}"
                    )
                )
                detail_flag_note_counter += 1

# ===========================================================================
#                  GENERATE OUTPUTS
# ===========================================================================
instances = instances_list.read()
scales = {"A": 0.25, "B": 0.3, "C": 1}

# Store the default trace layout styles into a variable to be used later when
# generating the GUI block diagram layouts if desired.
default_trace_overlay_style = dict(svg_utils.trace_overlay_style)

generate_outputs = True  # change to False if you'd like to skip the outputs generation process
if generate_outputs:

    # Bill of materials. Each BOM line gets a total row. An instance listed
    # in bom_disclosure also gets its own row under it, with one column per key.
    bom_disclosure = {}
    for instance in instances_list.read():
        if instance.get("item_type") == "cable" and instance.get("length"):
            bom_disclosure[instance.get("instance_name")] = {
                "Length with margin": float(instance.get("length")) + 12,
            }
    build_utils.run_macro(
        "bom_table_bottom_up",
        "macros/drawing_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="bom-1",
        per_instance_disclosure=bom_disclosure,
    )
    build_utils.run_macro(
        "tooling_list_exporter",
        "macros/drawing_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="tool_list-1",
    )
    build_utils.run_macro(
        "standard_harnice_formboard",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="formboard-overview",
        dimension=0,
        scale=scales.get("A"),
        input_instances=formboard_overview_instances,
    )
    build_utils.run_macro(
        "standard_harnice_formboard",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="formboard-detail",
        scale=scales.get("C"),
        input_instances=formboard_detail_instances,
    )

    # Example of how to edit the trace layouts for various outputs. Copy and paste
    # svg_utils.regenerate_trace_overlays and modify the style dict before a macro 
    # to modify that macro's trace layout appearance. 
    svg_utils.regenerate_trace_overlays(
        style={
            "label_font_size": 0.5,
            "segment_spacing": 1.5,
            "stroke_width": 0.5 / 96,
            "min_label_segment_length": None,
            "network_segment_stroke_width": 1.8,
            "network_segment_font_size": 11,
            "network_node_radius": 2.2,
            "network_node_font_size": 10,
        },
    )
    build_utils.run_macro(
        "trace_layout_visualizer",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="conductor_layout-1",
        trace_item_types=["conductor"],
        scale=scales.get("A"),
    )
    build_utils.run_macro(
        "trace_layout_visualizer",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="cable_layout-1",
        trace_item_types=["cable"],
        scale=scales.get("A"),
    )
    build_utils.run_macro(
        "circuit_visualizer",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="circuitviz-1",
        input_instances=instances_list.read(),
    )
    build_utils.run_macro(
        "revision_history_table",
        "macros/drawing_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="revhistory-1",
    )

    build_notes_list_instances = []
    for instance in instances_list.read():
        if (
            instance.get("item_type") == "note"
            and instance.get("note_type") == "build_note"
        ):
            build_notes_list_instances.append(instance)

    build_utils.run_macro(
        "build_notes_table",
        "macros/drawing_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="build_notes_table-1",
        input_instances=build_notes_list_instances,
    )
    build_utils.run_macro(
        "wirelist_exporter",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="wirelist-1",
        input_instances=instances_list.read(),
    )
    build_utils.run_macro(
        "harness_step_builder",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="harness-step-1",
        chosen_network=bundle_network,
        input_instances=instances_list.read(),
    )
    # Each run_macro call is one PDF drawing (switch instances in the console to edit layout).
    # page_setup is the list of pages; edit it here, not in the PDF editor.
    build_utils.run_macro(
        "pdf_generator",
        "macros/drawing_artifacts",
        "https://github.com/harnice/harnice-general-library",
        artifact_id="pdf_drawing-1",
        page_setup={
            "pages": [
                {
                    "tblock_mpn": "harnice_tblock",
                    "tblock_lib_repo": "https://github.com/harnice/harnice-general-library",
                    "tblock_lib_subpath": "titleblocks/",
                    "page_size_in": [11.0, 8.5],
                    "tblock_anchor": "bottom-right",
                    "tblock_offset_px": [40.0, 40.0],
                    "text_replacements": {
                        "tblock-key-pagedesc": "overview",
                        "tblock-key-desc": rev_history.info(field="desc"),
                        "tblock-key-pn": state.partnumber("pn"),
                        "tblock-key-drawnby": rev_history.info(field="drawnby"),
                        "tblock-key-rev": state.partnumber("R"),
                        "tblock-key-scale": scales.get("A"),
                        "tblock-key-sheet": "autosheet",
                    },
                },
                {
                    "tblock_mpn": "harnice_tblock",
                    "tblock_lib_repo": "https://github.com/harnice/harnice-general-library",
                    "tblock_lib_subpath": "titleblocks/",
                    "page_size_in": [11.0, 8.5],
                    "tblock_anchor": "bottom-right",
                    "tblock_offset_px": [40.0, 40.0],
                    "text_replacements": {
                        "tblock-key-pagedesc": "to-from table",
                        "tblock-key-desc": rev_history.info(field="desc"),
                        "tblock-key-pn": state.partnumber("pn"),
                        "tblock-key-drawnby": rev_history.info(field="drawnby"),
                        "tblock-key-rev": state.partnumber("R"),
                        "tblock-key-scale": scales.get("A"),
                        "tblock-key-sheet": "autosheet",
                    },
                },
                {
                    "tblock_mpn": "harnice_tblock",
                    "tblock_lib_repo": "https://github.com/harnice/harnice-general-library",
                    "tblock_lib_subpath": "titleblocks/",
                    "page_size_in": [11.0, 8.5],
                    "tblock_anchor": "bottom-right",
                    "tblock_offset_px": [40.0, 40.0],
                    "text_replacements": {
                        "tblock-key-pagedesc": "channel map",
                        "tblock-key-desc": rev_history.info(field="desc"),
                        "tblock-key-pn": state.partnumber("pn"),
                        "tblock-key-drawnby": rev_history.info(field="drawnby"),
                        "tblock-key-rev": state.partnumber("R"),
                        "tblock-key-scale": scales.get("A"),
                        "tblock-key-sheet": "autosheet",
                    },
                },
            ],
        },
    )

# Reset the trace overlay style to default saved earlier to set the gui trace
# overlay style. 
svg_utils.trace_overlay_style.update(default_trace_overlay_style)

# ===========================================================================
#                  REMOVE UNUSED INSTANCE DATA
# ===========================================================================
# Drop instance_data folders whose refdes is no longer in this project.
build_utils.remove_unused_instance_data()
