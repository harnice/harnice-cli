from harnice import fileio
from harnice.lists import instances_list
from harnice.utils import library_utils
import os

conductor_documentation_description = "A conductor is a piece of copper"
circuit_documentation_description = 'A circuit is the requirement that there must exist an electrical path between two signals of connected devices. You can assign conductors or other electrical elements along it. Instances assigned along the circuit have "circuit ids" which represent the order in which the circuit passes through them.'

def end_ports_of_circuit(circuit_id):
    """
    Returns the instance names at the end ports (port 0 and maximum port) of a circuit.

    Finds and returns the instance names connected to port 0 and the maximum port number
    in the specified circuit. These represent the endpoints of the circuit.

    Instances that carry the `circuit_id` but no `circuit_port_number` span the circuit
    instead of sitting at a port on it, and are ignored.

    **Args:**
    - `circuit_id` (str): Circuit ID to look up.

    **Returns:**
    - `tuple`: A tuple of `(zero_port, max_port)` instance dicts. Either may be an empty
        dict if not found.
    """

    instances = instances_list.read()

    # find the highest port number in the circuit. instances with no port number span
    # the circuit rather than sitting at a port on it (the circuit itself, and the
    # conductors and cables assigned along it), so they are never an end.
    max_port_number = 0
    for instance in instances:
        if instance.get("circuit_id") != circuit_id:
            continue
        if instance.get("circuit_port_number") == "":
            continue
        max_port_number = max(
            max_port_number, int(instance.get("circuit_port_number"))
        )

    zero_port_instance = {}
    max_port_instance = {}
    for instance in instances:
        if str(instance.get("circuit_id")) == str(circuit_id):
            if str(instance.get("circuit_port_number")) == str(0):
                zero_port_instance = instance
            if str(instance.get("circuit_port_number")) == str(max_port_number):
                max_port_instance = instance
    return zero_port_instance, max_port_instance


def squeeze_instance_between_ports_in_circuit(
    instance_name, circuit_id, new_circuit_port_number
):
    """
    Inserts an instance into a circuit by shifting existing port numbers.

    Assigns the specified instance to a port number in the circuit, incrementing
    the port numbers of all instances that were at or after that port number.
    Circuit instances (`item_type=="circuit"`) are skipped and not renumbered.

    **Args:**
    - `instance_name` (str): Name of the instance to insert into the circuit.
    - `circuit_id` (str): Circuit ID to insert the instance into.
    - `new_circuit_port_number` (int): Port number to assign to the instance. All
        instances at this port number or higher will have their port numbers
        incremented by 1.
    """
    instances = instances_list.read()
    for instance in instances:
        if instance.get("instance_name") == instance_name:
            continue
        if instance.get("circuit_id") == circuit_id:
            if instance.get("item_type") == "circuit":
                continue
            old_port_number = instance.get("circuit_port_number")
            if int(instance.get("circuit_port_number")) < new_circuit_port_number:
                continue
            else:
                instances_list.modify(
                    instance.get("instance_name"),
                    {"circuit_port_number": int(old_port_number) + 1},
                )
    for instance in instances:
        if instance.get("instance_name") == instance_name:
            instances_list.modify(
                instance_name,
                {
                    "circuit_id": circuit_id,
                    "circuit_port_number": new_circuit_port_number,
                },
            )


def instances_of_circuit(circuit_id):
    """
    Returns all instances in a circuit, sorted by port number.

    Finds all instances (excluding circuit instances themselves) that belong to
    the specified circuit and returns them sorted numerically by their `circuit_port_number`.
    Instances with missing port numbers are sorted last (treated as `999999`).

    **Args:**
    - `circuit_id` (str): Circuit ID to search for instances.

    **Returns:**
    - `list`: List of instance dictionaries, sorted by `circuit_port_number` in ascending order.
    """
    instances = []
    for instance in instances_list.read():
        if instance.get("circuit_id") == circuit_id:
            if instance.get("item_type") == "circuit":
                continue
            instances.append(instance)

    # sort numerically by circuit_port_number, treating missing as large number
    instances.sort(key=lambda x: int(x.get("circuit_port_number") or 999999))

    return instances


def instance_of_circuit_port_number(circuit_id, circuit_port_number):
    """
    Finds the instance name at a specific port number in a circuit.

    Searches the instances list for an instance that matches both the `circuit_id`
    and `circuit_port_number`. The comparison is done after stripping whitespace
    and converting to strings.

    **Args:**
    - `circuit_id` (str): Circuit ID to search.
    - `circuit_port_number` (str or int): Port number to search for.

    **Returns:**
    - `str`: The `instance_name` of the instance at the specified port number.

    **Raises:**
    - `ValueError`: If `circuit_id` or `circuit_port_number` is blank, or if no instance
        is found matching both the `circuit_id` and `circuit_port_number`.
    """
    if circuit_id in ["", None]:
        raise ValueError("Circuit ID is blank")
    if circuit_port_number in ["", None]:
        raise ValueError("Circuit port number is blank")

    for instance in instances_list.read():
        if instance.get("circuit_id").strip() == str(circuit_id).strip():
            if (
                instance.get("circuit_port_number").strip()
                == str(circuit_port_number).strip()
            ):
                return instance.get("instance_name")

    raise ValueError(
        f"No instance found for circuit {circuit_id} and port number {circuit_port_number}"
    )


def circuit_instance_of_instance(instance_name):
    """
    Returns the circuit instance dictionary for an instance that belongs to a circuit.

    Finds the circuit instance (`item_type=="circuit"`) that corresponds to a given
    instance. The circuit instance has the same `circuit_id` as the instance's `circuit_id`.

    **Args:**
    - `instance_name` (str): Name of the instance to find the circuit instance for.

    **Returns:**
    - `dict`: The circuit instance dictionary.

    **Raises:**
    - `ValueError`: If the circuit instance cannot be found for the given instance.
    """
    circuit_instance_name = ""
    instance_rows = instances_list.read()
    for instance in instance_rows:
        if instance.get("instance_name") == instance_name:
            circuit_instance_name = instance.get("circuit_id")
            break
    for instance in instance_rows:
        if instance.get("circuit_id") == circuit_instance_name:
            if instance.get("instance_name") == instance_name:
                return instance
    raise ValueError(
        f"Circuit instance {circuit_instance_name} of instance {instance_name} not found"
    )


conductor_documentation_description = "A piece of copper, sometimes contained in a cable. Has as many properties, appearances, as you need"
def assign_cable_conductor(
    cable_instance_name,  # unique identifier for the cable in your project
    cable_conductor_id,  # (container, identifier) tuple identifying the conductor in the cable being imported
    conductor_instance,  # instance name of the conductor in your project
    library_info,  # dict containing library info: {lib_repo, mpn, lib_subpath, used_rev}
    harness,  # which harness this cable belongs to
):
    """
    Assigns a conductor instance to a specific conductor in a cable.

    Links a conductor instance in the project to a specific conductor within a cable
    by importing the cable from the library (if not already imported) and updating
    the conductor instance with cable assignment information, including the conductor's
    appearance from the cable definition.

    The `cable_conductor_id` uses the `(container, identifier)` format from the cable
    conductor list. The cable is imported if it doesn't exist, and the conductor
    instance is updated with group, identifier, and appearance info.

    **Args:**
    - `cable_instance_name` (str): Unique identifier for the cable in the project.
    - `cable_conductor_id` (tuple): Tuple of `(container, identifier)` identifying the
        conductor in the cable being imported.
    - `conductor_instance` (str): Instance name of the conductor in the project.
    - `library_info` (dict): Dictionary containing library information with keys:
        `lib_repo`, `mpn`, `lib_subpath`, and optionally `used_rev`.
    - `harness` (str): Harness name that this cable belongs to.

    **Raises:**
    - `ValueError`: If the conductor has already been assigned to another instance,
        or if the `conductor_instance` has already been assigned to another cable.
    """
    # for cable_conductor_id, see (container, identifier) from the cable conductor list.
    # TODO: ensure cable_conductor_id has the right format.

    instances = instances_list.read()

    # --- Make sure conductor of cable has not been assigned yet
    for instance in instances:
        if instance.get("cable_group") == cable_instance_name:
            if instance.get("cable_identifier") == cable_conductor_id[1]:
                raise ValueError(
                    f"when assingning '{cable_conductor_id} of '{cable_instance_name}' to '{conductor_instance}', "
                    f"conductor '{cable_conductor_id}' of '{cable_instance_name}' has already been assigned to {instance.get('instance_name')}"
                )

    # --- Make sure conductor instance has not already been assigned to a cable
    for instance in instances:
        if instance.get("instance_name") == conductor_instance:
            if (
                instance.get("cable_group") not in ["", None]
                or instance.get("cable_identifier") not in ["", None]
            ):
                raise ValueError(
                    f"when assingning '{cable_conductor_id} of '{cable_instance_name}' to {conductor_instance}', "
                    f"instance '{conductor_instance}' has alredy been assigned to another cable"
                    f"to '{instance.get('cable_identifier')}' of cable '{instance.get('cable_group')}'"
                )

    cable_destination_directory = os.path.join(
        fileio.dirpath(None), "instance_data", "cable", cable_instance_name
    )

    conductor_row = None
    for instance in instances:
        if instance.get("instance_name") == conductor_instance:
            conductor_row = instance
            break

    from_device = (conductor_row or {}).get("this_channel_from_device_refdes") or ""
    from_ch_id = (conductor_row or {}).get("this_channel_from_device_channel_id") or ""
    to_device = (conductor_row or {}).get("this_channel_to_device_refdes") or ""
    to_ch_id = (conductor_row or {}).get("this_channel_to_device_channel_id") or ""
    cable_print_name = f"{cable_instance_name}:{from_device}.{from_ch_id}<->{to_device}.{to_ch_id}"

    instances_list.new_instance(
        cable_instance_name,
        {
            "harness": harness,
            "item_type": "cable",
            "location_type": "segment",
            "cable_group": cable_instance_name,
            "this_channel_from_device_refdes": from_device,
            "this_channel_from_device_channel_id": from_ch_id,
            "this_channel_to_device_refdes": to_device,
            "this_channel_to_device_channel_id": to_ch_id,
            "print_name": cable_print_name,
            "print_name_at_end_a": cable_print_name,
            "print_name_at_end_b": cable_print_name,
        },
        ignore_duplicates=True,
    )

    channel_group = (conductor_row or {}).get("channel_group")
    if channel_group:
        try:
            instances_list.modify(
                channel_group,
                {
                    "cable_group": cable_instance_name,
                    "print_name": cable_print_name,
                    "print_name_at_end_a": cable_print_name,
                    "print_name_at_end_b": cable_print_name,
                },
            )
        except ValueError:
            pass

    # --- Import cable from library ---
    library_utils.pull(
        {
            "lib_repo": library_info.get("lib_repo"),
            "lib_subpath": library_info.get("lib_subpath"),
            "item_type": "cable",
            "mpn": library_info.get("mpn"),
            "instance_name": cable_instance_name,
        },
        destination_directory=cable_destination_directory,
    )

    cable_attributes_path = os.path.join(
        cable_destination_directory, "conductors.tsv"
    )
    cable_attributes = fileio.read_tsv(cable_attributes_path)

    # --- assign conductor
    for instance in instances:
        if instance.get("instance_name") == conductor_instance:
            appearance = None
            for row in cable_attributes:
                if (
                    row.get("container") == cable_conductor_id[0]
                    and row.get("identifier") == cable_conductor_id[1]
                ):
                    appearance = row.get("appearance")
                    break

            instances_list.modify(
                conductor_instance,
                {
                    "cable_group": cable_instance_name,
                    "cable_identifier": cable_conductor_id[1],
                    "appearance": appearance,
                },
            )
            break
