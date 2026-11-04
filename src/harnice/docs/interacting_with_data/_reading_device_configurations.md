# Reading Device Configurations

A configuration records how to set up the hardware. Use a field for any reason. A field the build never reads is still worth storing: the instance keeps the answer, and another program can read it from the BOM.

A value can be read in three places. The device's own build instructions see it as a dict. The system build that placed the device reads it from the BOM. A program outside Harnice reads that same BOM file.

## From the device's build instructions

Read `configuration["field_id"]` for any reason. One example is a signals list that follows the answers. Harnice builds the placed device before the system script runs, and injects `configuration` into that device's `fileio.path("build instructions")` (`build.py`). The key is the field `id` from `fileio.path("configuration setup")`.

```python
input_type = configuration["input_type"]
phantom = configuration["phantom_power"]
presets = configuration["presets"]   # dict, list, or scalar, from a json, yaml, or toml field
labels = configuration["labels"]     # list of strings
```

On a standalone device build, `configuration` is the setup defaults. On a system rebuild of a placed device, it is that instance's answers, with setup defaults filling any missing keys.

Harnice parses `json`, `yaml`, and `toml` text before the script runs.

| Field type | Value of `configuration["field_id"]` |
| ---------- | ------------------------------------ |
| text, textarea, select, radio, channel type, IP address, MAC address, URL, matrix | string |
| number, slider, scale, rating | number |
| boolean | `True` or `False` |
| a field left unset | `None` |
| list, multiselect | list of strings |
| json, yaml, toml | the loaded data: a `dict`, a `list`, a string, a number, a boolean, or `None`. Empty text is `None`. |

Field types, validation, `show_if`, and a YAML example are on [Device Configurations](../fragments/configurations.md).

## From the system build instructions

Read a placed device's answers for any reason. One example is choosing which channels to map. By the time the system script runs, Harnice has written the BOM and rebuilt each placed device. Harnice does not inject `configuration` into the system script. Read the placed device from the BOM:

```python
import json

text = ""
for row in fileio.read_tsv("bom"):
    if row["device_refdes"] == "A1":
        text = (row.get("configuration") or "").strip()
        break

answers = json.loads(text) if text else {}

if answers.get("pairing") == "crossed":
    channel_map.map(("A1", "out1"), ("B1", "in1"))
else:
    channel_map.map(("A1", "out1"), ("B1", "in2"))
```

`device_refdes` is the instance name on the block diagram. `answers` is the saved object for that instance. An empty cell is no saved answers, and `answers` is `{}`.

`answers[field_id]` matches the table in "Reading one variable". A `json`, `yaml`, or `toml` field is still the document text on this path. Inside the device build, that same field is already parsed.

The `channel_map.map` calls above are one example. Use `answers` for whatever the system script needs. The channel id in that example is a channel on the signals list that device build wrote.

## From another program

`fileio.path("bom")` is `lists/bom.tsv` under the system revision. The file is tab-separated. One row is one placed device or harness. Find the device by `device_refdes`, the instance name on the block diagram.

| Column | Description |
|--------|-------------|
| `device_refdes` | Instance name on the block diagram. This is the row key. |
| `configuration` | One compact JSON object of that device's answers. An empty cell means the instance has no saved answers. Harness rows leave this cell empty. |

The other BOM columns (`MFG`, `MPN`, `lib_repo`, `lib_subpath`, `rev`, `harness`, `system`) identify the part. A configuration field id is a key inside the `configuration` cell.

After a system build, the instances list copies that same JSON string into `device_configuration`. Parse that cell the same way.

## Reading one variable

```python
import csv
import json

with open(bom_path, newline="", encoding="utf-8") as f:
    rows = csv.DictReader(f, delimiter="\t")
    row = next(r for r in rows if r["device_refdes"] == refdes)

value = json.loads(row["configuration"])[variable]
```

`value` is the stored answer. `json.loads` turns JSON `true`, `false`, and `null` into `True`, `False`, and `None`.

| Field type | Value after `json.loads` |
| ---------- | ------------------------ |
| text, textarea, select, radio, channel type, IP address, MAC address, URL, matrix | string |
| number, slider, scale, rating | number |
| boolean | `True` or `False` |
| a field left unset | `None` |
| list, multiselect | list of strings |
| json, yaml, toml | the document text, still a string |

A `json`, `yaml`, or `toml` field needs a second parse to get the data inside the document. `document` is the string from the step above.

| Field type | Second parse |
| ---------- | ------------ |
| json | `json.loads(document)` |
| yaml | `yaml.safe_load(document)` |
| toml | `tomllib.loads(document)` (Python 3.11+) |

An empty `configuration` cell has no object to parse. Skip that row, or treat it as no saved answers.
