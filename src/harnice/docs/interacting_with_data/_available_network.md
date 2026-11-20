# Available Network
The 3D page writes ``networks/available.json``. Build loads that file. A node is ``node_id``, ``location`` ``[x, y, z]``, and ``alpha``, ``beta``, ``gamma`` (ZYX degrees: α about X, β about Y, γ about Z). A segment is ``segment_id``, ``location_at_end_a``, ``location_at_end_b``, and ``spline_control_points``. Each control point is an offset from end A, in order from A to B. The console adds end A when it draws a control point. ``spline_points`` and ``spline_length`` place each stored triple in the Bezier polygon as written, in the same coordinate space as the two ends. An empty control list is a straight line.

---
##Commands
*These functions are already available in build instructions as `available_network`. Use them as written.*
??? info "`available_network.load()`"

    Use this when a harness build needs the available network already stored in this revision.
    
    Load the available network from disk.
    
    If the file does not exist yet, returns an empty network
    (``{"segments": [], "nodes": []}``) and writes nothing.

??? info "`available_network.save(network)`"

    Use this when a harness build has changed the available network and the change belongs in ``available.json``.
    
    Replace this revision's available network file with ``network``.
    
    Everything the available network editor shows comes from this file, so
    a node or segment a build adds is only visible there once it is saved.
    
    **Args**
    
    - **network** — Network dict with ``"nodes"`` and ``"segments"``.

??? info "`available_network.source_of_truth(item)`"

    Use this when a harness build needs to know where an available-network node or segment comes from.
    
    Return the ``source_of_truth`` of a node or segment: ``"gui"``, or the
    id of the routing context it was read from.
    
    An item with no ``source_of_truth`` is ``"gui"``, except a node that
    carries a ``mate`` tag, which came from the source system
    (``SOURCE_SYSTEM_CONTEXT``).

??? info "`available_network.tag_source_of_truth(items, source)`"

    Use this when a harness build adds nodes or segments read from a routing context to the available network.
    
    Return copies of ``items`` with ``source_of_truth`` set to ``source``.

??? info "`available_network.keep_only_gui(network)`"

    Use this when a harness build is about to reload every routing context into the available network.
    
    Return a copy of ``network`` without the nodes and segments whose
    ``source_of_truth`` is not ``"gui"``. The build then adds them again,
    fresh from their contexts.

??? info "`available_network.source_context_from_path(local_path=None, lib_repo=None, relative_path=None)`"

    Use this when a harness build needs a STEP file copied into networks/contexts/ as routing context for this harness.
    
    Copy a STEP file into this harness as routing context.
    
    Pass either ``local_path`` or both ``lib_repo`` and ``relative_path``.
    The file is written to ``networks/contexts/`` under its own filename,
    replacing a context file of that name. Other files already in
    ``contexts/`` are left in place. The 3D available and chosen network
    pages load ``.step`` and ``.stp`` files from that folder.
    
    **Args:**
    - ``local_path`` (str, optional): Filesystem path to a ``.step`` or ``.stp`` file.
    - ``lib_repo`` (str, optional): Library repository URL from ``repository_locations.csv``.
    - ``relative_path`` (str, optional): Path of the STEP file under that repository.
    
    **Returns:**
    - ``str``: Path of the context file written into this harness.
    
    **Raises:**
    - ``ValueError``: If both sources are given, neither source is complete, the
      relative path leaves the repository, or the file is not a STEP file.
    - ``FileNotFoundError``: If the source file does not exist.

??? info "`available_network.source_available_network_from_project(project_mpn, project_subpath, project_repo)`"

    Use this when a harness build should replace this revision's available network with the available network from another project.
    
    Copy another project's available network into this harness.
    
    The other project is the library tip (highest revision) of ``project_mpn``
    under ``project_repo`` and ``project_subpath``. Its available-network file
    replaces this harness's available network.
    
    **Args:**
    - ``project_mpn`` (str): Part-number folder of the source project.
    - ``project_subpath`` (str): Path under the repository that contains that
      part number. ``""`` when the part number sits at the repository root.
    - ``project_repo`` (str): Library repository URL from ``repository_locations.csv``.
    
    **Returns:**
    - ``dict``: The available network that was written.
    
    **Raises:**
    - ``ValueError``: If ``project_mpn`` or ``project_repo`` is blank, or the
      subpath leaves the repository.
    - ``FileNotFoundError``: If the part, its revision, or its available network
      file cannot be found.

