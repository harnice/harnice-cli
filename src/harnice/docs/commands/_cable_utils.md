# Cable Utilities
---
##Commands
*These functions are already available in build instructions as `cable_utils`. Use them as written.*
??? info "`cable_utils.new_cable(instance_name, mpn, lib_repo, lib_subpath)`"

    Use this when a harness build needs a library cable imported as a new cable instance.
    
    Imports a library cable into the project as a new cable instance.
    
    Creates an instances-list row named `instance_name` (the cable refdes) and
    pulls the matching library part into `instance_data/cable/{instance_name}/`,
    the same way connectors and backshells are imported.
    
    **Args:**
    - `instance_name` (str): Refdes / instance name for this cable in the project.
    - `mpn` (str): Manufacturer part number of the cable in the library.
    - `lib_repo` (str): Library repository URL, or `"local"` for the project library.
    - `lib_subpath` (str): Subpath within the library to the cable (may be `""`).
    
    **Raises:**
    - `ValueError`: If required arguments are blank, or an instance with
        `instance_name` already exists.
    - `FileNotFoundError`: If the library cable cannot be found.

??? info "`cable_utils.prepare_for_conductor_assign(instance_name)`"

    Use this when a harness build needs the system cable recommendation cleared on a conductor before that conductor is assigned to a chosen cable.
    
    Clears system cable-recommendation fields on a conductor so it can be assigned.
    
    System build writes `mpn`, `lib_repo`, `lib_subpath`, `cable_group`, and
    `cable_identifier` onto circuits as suggestions. Those fields are copied onto
    conductors when the harness is imported. `assign_conductor_to_cable` requires
    `cable_group` and `cable_identifier` to be blank, and the library identity
    belongs on the cable instance after `new_cable`, not on the conductor.
    
    **Args:**
    - `instance_name` (str): Instance name of the conductor to clear.

??? info "`cable_utils.assign_conductor_to_cable(instance_name, cable_instance_name, cable_identifier)`"

    Use this when a harness build needs a conductor instance assigned to one conductor of a cable that is already in the project.
    
    Assigns a conductor instance to one conductor inside an existing cable.
    
    Verifies that `cable_instance_name` exists as a cable, that `cable_identifier`
    is a conductor in that cable's conductor list, that the conductor instance
    has blank `cable_group` and `cable_identifier`, and that no instance already
    holds that cable-and-identifier pair. Then writes `cable_group`,
    `cable_identifier`, and `appearance` onto the conductor, and writes the
    cable's own appearance (from its attributes JSON) onto the cable instance.
    
    `cable_identifier` is the `identifier` column from the cable conductor list.
    Cable build requires that column to be unique, so it is sufficient on its own.
    
    **Args:**
    - `instance_name` (str): Instance name of the conductor to assign.
    - `cable_instance_name` (str): Instance name of the cable created with
        `new_cable`.
    - `cable_identifier` (str): Conductor in the cable (`identifier` column).
    
    **Raises:**
    - `ValueError`: If the conductor or cable is missing, the cable has no
        conductor list, `cable_identifier` is missing or not unique, the
        conductor is already assigned, or that cable conductor is already
        assigned to another instance.

??? info "`cable_utils.map_cables_and_conductors_to_segments()`"

    Use this when a harness build needs every cable and conductor routed onto the flattened network and their lengths written.
    
    Routes every conductor and cable onto the flattened network and writes lengths.
    
    Conductors are mapped from `node_at_end_a` to `node_at_end_b`. A conductor
    whose ends resolve to the same connector node is a loopback and is mapped
    out and back along that connector's free stub. Cables have no
    ends of their own: each cable is mapped onto the segments shared by every
    conductor assigned to it (the jacketed run before conductors break out to
    different nodes). Those shared-path ends are written onto the cable as
    `node_at_end_a` / `node_at_end_b`. Then writes `length` on each conductor
    (sum of its conductor-segment lengths) and on each cable (longest member
    conductor).
    
    **Raises:**
    - `ValueError`: If a conductor cannot be mapped. Each end must name a
        node, or a cavity whose connector group has one node. Both ends
        resolving to the same node travel out and back on that connector's
        free stub. No path between the ends raises.

??? info "`cable_utils.calculate_bundle_diameter(segment_instance_name)`"

    Use this when a harness build needs the outer diameter of one segment from the cables on that segment.
    
    Estimates the outer diameter of a segment from the cables it carries.
    
    Collects every cable mapped onto ``segment_instance_name`` (via
    ``cable-segment`` hops from ``map_cables_and_conductors_to_segments``) and
    reads each cable's jacket OD from its attributes JSON — a stated ``od``, or
    a pack of member ``od`` / AWG values when the jacket does not give one.
    Conductors on the segment that are not inside one of those cables (broken
    out, or never assigned) are included by their own conductor OD. If an
    unassigned conductor has no ``od``, ``diameter``, gauge, or attributes JSON,
    it is counted as 0.2 in and that assumption is printed.
    
    Bundle OD is ``d_av * β``: average member OD times Stringer's empirical
    bundle factor for that member count, linearly interpolated where the table
    has no exact entry. The result is written to the segment's ``diameter``
    column (inches) and returned.
    
    Stringer, E. J. (Rockwell International Corp.). "Calculating Wire-Bundle
    Diameter." NASA Tech Briefs 3, no. 1 (June 1978): 127. Tech Brief
    B78-10119. Report MSC-16378.
    https://ntrs.nasa.gov/citations/19780000119
    
    Call this after ``map_cables_and_conductors_to_segments``.
    
    **Args:**
    - `segment_instance_name` (str): Instance name of the segment to size.
    
    **Returns:**
    - `float`: Estimated bundle OD in inches.
    
    **Raises:**
    - `ValueError`: If the name is blank, the instance is missing or is not a
        segment, a cable on the segment has no usable OD, or an assigned
        conductor has no ``od`` / gauge.

