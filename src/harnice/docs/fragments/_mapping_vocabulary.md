??? note "Mapping vocabulary"

    ![Vocabulary graphic](fragments_images/terminology.png)

    **Group of connected harnesses:**

    - Harnesses linked through passthroughs (or a single standalone harness) that must be considered together. Channel mapping only pairs channels that share the same group.

    **Channel endpoint:**

    - One complete instance of a channel on one connector.



    **Patch:**

    - A pair of channel endpoints created by `channel_map.map()`. Stored in the channel map.



    **Passthrough:**

    - A channel with exactly two channel endpoints on the same device.



    **Map** (verb):

    - Pair two channel endpoints.



    **Route** (verb):

    - Send a patch through a passthrough (`passthrough_map.route()`).



    **Harness:**

    - A harness is an assembly of connectors, cables, and other electrical components that connect multiple devices together. It is the physical item that is built and installed in a system.



    **Channel:**

    - A channel is a set of electrical signals in a device that together transmit or receive information, power, etc. They have "channel_types" which define their attributes and compatibility with other channels, and contain a list of required signals (pos, neg)



    **Mapped channel:**

    - A mapped channel is a connection from one channel on a device to another. They define the functional requirement of any harness, and form the basis of which circuits are generated and where they go. The channel map is the list of mapped channels (and any still-unmapped channels). The passthrough map then routes those mapped channels through passthrough devices.



    **Signal:**

    - A signal is a physical conductive part inside a connector of a device that facilitiates electrical interface with the outside world. A signal must be part of a channel and live inside a connector.



    **Circuit:**

    - A circuit is the requirement that there must exist an electrical path between two signals of connected devices. You can assign conductors or other electrical elements along it. Instances assigned along the circuit have "circuit ids" which represent the order in which the circuit passes through them.



    **Conductor:**

    - A piece of copper, sometimes contained in a cable. Has as many properties, appearances, as you need



    **Cable:**

    - A cable is a COTS or custom physical item, purchased by length, that contains electrical conductors, and are physically installed inside harnesses.



    ## Less important terms

    - **Contact:**

        - The metal parts of a connector that does the actual mating with the other connector, allows for termination to a wire. Can be pins, sockets, studs, terminals, etc.



    - **Cavity:**

        - The hole in a connector that physically holds a contact

