# Chosen Network
``networks/chosen.json`` is the one route Build kept. It uses the same node and segment shape as the available network. A move that must survive the next build is applied to that dict after one solution is chosen and before ``save``. Every ``bundle_network_utils`` call returns a new dict.

---
##Commands
*These functions are already available in build instructions as `chosen_network`. Use them as written.*
??? info "`chosen_network.save(network)`"

    Use this when a harness build has finished changing the chosen network and needs that dict written to disk.
    
    Replace the chosen-network file with this network dict.
    
    **Args**
    
    - **network** — Network dict to write. Replaces the chosen-network file.

