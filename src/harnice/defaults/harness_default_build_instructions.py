import math
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

available_network = available_network.load()

# Assign nodes to any segments that may not have nodes attached
available_network = chosen_network.end_all_segments_in_nodes(available_network)

# Gather the collection of all instances with item_type == node
needed_nodes = []
for instance in instances_list.read():
    if instance.get("item_type") == "node":
        name = instance.get("instance_name")
        if name not in needed_nodes:
            needed_nodes.append(name)

# Ensures that every node in the list is present in the network.
missing_nodes = chosen_network.ensure_nodes_exist(
    input_network=available_network,
    set_of_required_nodes=needed_nodes,
)

# Generate geometry for required nodes that the available network did not provide.
# Set to False to raise an error instead.
if True:
    for missing_node in missing_nodes:
        existing_nodes = available_network.get("nodes") or []

        # Empty network: park at the origin. Otherwise sprout a short random
        # leg off the first existing node.
        new_node_location = [0, 0, 0]
        if existing_nodes:
            hub = existing_nodes[0]
            new_node_distance_from_hub = random.randint(6, 18)
            new_node_angle_from_x_axis = math.radians(random.randint(0, 359))
            new_node_location = [
                hub.get("location")[0] + new_node_distance_from_hub * math.cos(new_node_angle_from_x_axis),
                hub.get("location")[1] + new_node_distance_from_hub * math.sin(new_node_angle_from_x_axis),
                hub.get("location")[2],
            ]

        available_network = bundle_network_utils.new_node(
            available_network,
            new_id=missing_node,
            new_location=new_node_location,
        )

        # Connect back to the hub so the new node is not floating.
        if existing_nodes:
            available_network.setdefault("segments", []).append({
                "segment_id": f"{missing_node}_leg",
                "location_at_end_a": list(hub.get("location") or [0, 0, 0]),
                "location_at_end_b": new_node_location,
                "spline_control_points": [],
            })
else:
    if len(missing_nodes) > 0:
        raise ValueError(f"Missing node(s) {missing_nodes}")

# Find any possible solution within the network
found_solutions = chosen_network.calculate_possible_sub_networks(
    input_network=available_network,
    set_of_required_nodes=needed_nodes,
)

# Optionally prefer a solution containing particular imported segments. Leave
# these empty unless the parent system provides stable IDs worth selecting on.
preferred_segment_ids = []  # example: ["segment-1", "segment-2"]
preferred_node_ids = []  # example: ["branch-node"]
if len(found_solutions) > 1 and (preferred_segment_ids or preferred_node_ids):
    sorted_solutions = chosen_network.find_network_with(
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
        formboard_detail_instances.append(
            note_utils.make_bom_flagnote(
                instance, f"flagnote-{detail_flag_note_counter}"
            )
        )
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
#                  BUILD HARNESS OUTPUTS
# ===========================================================================
instances = instances_list.read()
scales = {"A": 0.25, "B": 0.3, "C": 1}

build_utils.run_macro(
    "bom_exporter_bottom_up",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="bom-1",
)
build_utils.run_macro(
    "tooling_list_exporter",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="tool_list-1",
)
build_utils.run_macro(
    "standard_harnice_formboard",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="formboard-overview",
    dimension=0,
    scale=scales.get("A"),
    input_instances=formboard_overview_instances,
)
build_utils.run_macro(
    "standard_harnice_formboard",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="formboard-detail",
    scale=scales.get("C"),
    input_instances=formboard_detail_instances,
)
build_utils.run_macro(
    "trace_layout_visualizer",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="conductor_layout-1",
    trace_item_types=["conductor"],
    scale=scales.get("A"),
)
build_utils.run_macro(
    "trace_layout_visualizer",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="cable_layout-1",
    trace_item_types=["cable"],
    scale=scales.get("A"),
)
build_utils.run_macro(
    "circuit_visualizer",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="circuitviz-1",
    input_instances=instances_list.read(),
)
build_utils.run_macro(
    "revision_history_table",
    "library/macros/harness_artifacts",
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
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="build_notes_table-1",
    input_instances=build_notes_list_instances,
)
build_utils.run_macro(
    "wirelist_exporter",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="wirelist-1",
    input_instances=instances_list.read(),
)
build_utils.run_macro(
    "harness_step_builder",
    "library/macros/harness_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="harness-step-1",
    chosen_network=bundle_network,
    input_instances=instances_list.read(),
)
# Each run_macro call is one PDF drawing (switch instances in the console to edit layout).
# page_setup is the list of pages; edit it here, not in the PDF editor.
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
                "tblock_lib_subpath": "library/titleblocks/",
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
                "tblock_lib_subpath": "library/titleblocks/",
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
