import os
import csv
import json
from harnice import cli, fileio, state


default_desc = "CABLE, FUNCTION, ATTRIBUTES, etc."

button_color = "#a38739"

documentation_description = "A cable is a COTS or custom physical item, purchased by length, that contains electrical conductors, and are physically installed inside harnesses."

def file_structure():
    return {
        "attributes.json": "attributes",
        "conductors.tsv": "conductor list",
    }


def generate_structure():
    pass


def build():
    # ========== Default JSON ==========
    default_attributes = {
        "jacket": {
            "properties": {
                "color": "gray",
                "material": "pvc",
                "od": "0.204in",
                "thickness": "0.028in",
            },
            "shield": {
                "properties": {"type": "foil", "coverage": "100%"},
                "drain_wire": {
                    "conductor": True,
                    "properties": {"gauge": "20AWG", "construction": "7x28"},
                    "appearance": {
                        "outline_color": "gray",
                        "slash_lines": {"direction": "RH", "color": "gray"},
                    },
                },
                "pair_1": {
                    "properties": {"twists": "12 per inch"},
                    "black": {
                        "conductor": True,
                        "properties": {
                            "insulation material": "polyethylene",
                            "od": "0.017in",
                            "gauge": "20AWG",
                            "construction": "7x28",
                            "material": "copper",
                        },
                        "appearance": {"base_color": "black"},
                    },
                    "white": {
                        "conductor": True,
                        "properties": {
                            "insulation material": "polyethylene",
                            "od": "0.017in",
                            "gauge": "20AWG",
                            "construction": "7x28",
                            "material": "copper",
                        },
                        "appearance": {"base_color": "white", "outline_color": "black"},
                    },
                },
            },
        }
    }

    attributes_path = fileio.path("attributes")

    # ========== Load or create attributes.json ==========
    if os.path.exists(attributes_path):
        try:
            with open(attributes_path, "r", encoding="utf-8") as f:
                attrs = json.load(f)
        except Exception as e:
            cli.warn(f"Could not load existing attributes.json: {e}")
            attrs = default_attributes
            with open(attributes_path, "w", encoding="utf-8") as f:
                json.dump(attrs, f, indent=4)
    else:
        attrs = default_attributes
        with open(attributes_path, "w", encoding="utf-8") as f:
            json.dump(attrs, f, indent=4)

    # ========== Traverse and build TSV ==========
    rows = []
    all_headers = {"appearance"}  # ensure it exists

    def recurse(obj, parent_chain=None):
        """Walk through nested dicts, recording conductor rows."""
        if parent_chain is None:
            parent_chain = []

        if isinstance(obj, dict):
            # Found conductor
            if obj.get("conductor") is True:
                props = obj.get("properties", {})
                appearance = obj.get("appearance", {})

                # Use previous parent chain to fill in context
                container = parent_chain[-2] if len(parent_chain) >= 2 else ""
                identifier = parent_chain[-1] if len(parent_chain) >= 1 else ""

                row = {"container": container, "identifier": identifier}

                for k, v in props.items():
                    row[k] = v
                    all_headers.add(k)

                # Convert appearance to JSON string (compact)
                row["appearance"] = (
                    json.dumps(
                        appearance, separators=(",", ":"), ensure_ascii=False
                    ).replace('"', "'")
                    if appearance
                    else ""
                )

                rows.append(row)

            # Continue traversing deeper
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    recurse(v, parent_chain + [k])

        elif isinstance(obj, list):
            for item in obj:
                recurse(item, parent_chain)

    recurse(attrs)

    if not rows:
        cli.warn("No conductor entries found.")
        return

    seen_identifiers = {}
    for row in rows:
        identifier = (row.get("identifier") or "").strip()
        if not identifier:
            raise ValueError(
                "Cable conductor identifier is blank. Each conductor node key "
                "in the attributes JSON must be non-empty."
            )
        if identifier in seen_identifiers:
            raise ValueError(
                f"Cable conductor identifier '{identifier}' is used more than once "
                f"(containers '{seen_identifiers[identifier]}' and "
                f"'{row.get('container')}'). Each conductor key must be unique "
                "across the cable; include the container or another namespace "
                "in the key if needed (for example pair_1_black and pair_2_black)."
            )
        seen_identifiers[identifier] = row.get("container")

    # Define header order
    headers = ["container", "identifier"] + sorted(all_headers)

    # Write to TSV
    conductor_list_path = fileio.path("conductor list")
    with open(conductor_list_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=headers, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"\ncable built successfully! wrote {len(rows)} rows to:\n{conductor_list_path}\n"
    )
