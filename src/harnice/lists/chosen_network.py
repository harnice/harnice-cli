import json

from harnice import fileio


def save(network):
    """
    Use this when a harness build has finished changing the chosen network and needs that dict written to disk.

    Replace the chosen-network file with this network dict.

    ## Args

    - **network** — Network dict to write. Replaces the chosen-network file.
    """
    with open(fileio.path("chosen network"), "w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)
