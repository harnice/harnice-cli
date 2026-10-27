the first time you build after updating your signals list, you may get an error like `The following pin(s) exist in SVG symbol but not in Signals List: in1, in2, out1, out2`. Harnice keeps the block diagram symbol in sync with your signals list. Delete or edit the SVG so its pins match, then rebuild—missing pins are appended automatically when possible.

Before you polish the symbol, name your connectors in the signals list and build once more so the pins that appear in the SVG match what you intend.

1. Open the Harnice console on your device and open the **block diagram symbol** editor.
1. Arrange the symbol the way you want it to look. Do not rename pin identifiers that must match the signals list; you can change placement and appearance.
1. Text on the symbol is a Python f-string. `{refdes}` becomes the instance name, and `{configuration.get("field_id")}` reads a configuration field, when a system builds this device. The result is written into that system's diagram. `\n` starts a new line. Text with no `{...}` and no `\n` stays as written.
1. Save the symbol and click **Build** again to confirm the SVG still matches the signals list.

When you build a device from its Signals List, Harnice creates or updates a block diagram symbol SVG in the revision directory. That symbol contains ports that match the connectors in your Signals List.
