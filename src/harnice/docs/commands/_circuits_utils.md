# Circuit Utilities
---
##Commands:
*These functions are already available in build instructions as `circuit_utils`. Use them as written.*
??? info "`circuit_utils.end_ports_of_circuit(circuit_id)`"

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

??? info "`circuit_utils.squeeze_instance_between_ports_in_circuit(instance_name, circuit_id, new_circuit_port_number)`"

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

??? info "`circuit_utils.instances_of_circuit(circuit_id)`"

    Returns all instances in a circuit, sorted by port number.
    
    Finds all instances (excluding circuit instances themselves) that belong to
    the specified circuit and returns them sorted numerically by their `circuit_port_number`.
    Instances with missing port numbers are sorted last (treated as `999999`).
    
    **Args:**
    - `circuit_id` (str): Circuit ID to search for instances.
    
    **Returns:**
    - `list`: List of instance dictionaries, sorted by `circuit_port_number` in ascending order.

??? info "`circuit_utils.instance_of_circuit_port_number(circuit_id, circuit_port_number)`"

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

??? info "`circuit_utils.circuit_instance_of_instance(instance_name)`"

    Returns the circuit instance dictionary for an instance that belongs to a circuit.
    
    Finds the circuit instance (`item_type=="circuit"`) that corresponds to a given
    instance. The circuit instance has the same `circuit_id` as the instance's `circuit_id`.
    
    **Args:**
    - `instance_name` (str): Name of the instance to find the circuit instance for.
    
    **Returns:**
    - `dict`: The circuit instance dictionary.
    
    **Raises:**
    - `ValueError`: If the circuit instance cannot be found for the given instance.

??? info "`circuit_utils.assign_cable_conductor(cable_instance_name, cable_conductor_id, conductor_instance, library_info, harness)`"

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

