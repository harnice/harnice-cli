Harnice treats a part number as the unique identity of a component's design. If a released or otherwise established part changes in **form, fit, or function**, that change needs a new part number. Drawing revisions and documentation updates do not.

Electrical behavior can change without changing the physical build. Those usage choices are **configurations**: they describe **how** an item is used, not **what** the item is.

Examples:

- Power supply with multiple output voltage settings
- Audio preamplifier that works for both balanced or unbalanced inputs
- Digitally configurable analog-to-digital converter input
- Antenna used as a transmitter or a receiver

In those cases the same part is used differently without rebuilding or rewiring it, so Harnice keeps one device part number and records the usage as a configuration.

A configuration does **not** filter alternate rows out of a signals list. Build instructions write **one** signals list for the answers currently in `configuration` (a dict). Validation only sees that list.

Do not use configuration to change the physical part. If connectors, cavities, or the hardware build change, that is a new part number. Unused signals that are still on the connector should stay in the list.

### Where configuration lives

A new device gets a blank `fileio.path("configuration setup")`. Add fields only when the device actually has usage choices.

| Place | File | Role |
| ----- | ---- | ---- |
| Device revision | `fileio.path("configuration setup")` | Declares the form: field ids, types, defaults, validation, and `show_if` rules |
| Device build | `fileio.path("build instructions")` | Reads `configuration["field_id"]` and writes the signals list for those answers |
| Device symbol | `fileio.path("block diagram symbol")` | Optional attribute-text nodes whose `data-attribute-name` matches a field id |
| System block diagram | `<configuration>` under the placed device `<g>` | Instance answers as JSON |
| System BOM | `configuration` column | Compact JSON copied from that SVG child |
| System instances list | `device_configuration` | The same answers after the BOM is imported |
| Placed instance copy | that instance's `fileio.path("configuration setup")` | The device's setup form, used to render the instance editor |

When you build a device on its own, Harnice fills `configuration` from each field's `default` in `fileio.path("configuration setup")`. When a system rebuilds a placed device, instance answers from the diagram / BOM override those defaults. Missing keys are still filled from the setup defaults so `fileio.path("build instructions")` always sees a complete dict.

`show_if` only controls whether a field is visible in the form. Hidden fields still contribute their defaults.

### Editing the form

Open the device in the Harnice console and select **configuration setup**. The visual editor lets you drop field types, set id / label / default / required, add options, and write `show_if` rules. Saving writes `fileio.path("configuration setup")`.

You can also edit `fileio.path("configuration setup")` directly. A comment-only or empty file is valid and means the device has no configuration fields.

### YAML shape

Top level must be a mapping with a `fields` list. Each field is a mapping.

Required on every field:

- `id` — unique string. This is the key in the `configuration` dict.
- `type` — one of the field types below.
- `label` — text shown in the form.
- `default` — required even when there is no useful value; use `null` in that case.

Optional on every field:

- `required` — boolean.
- `validation` — type-specific constraints (see below).
- `show_if` — show this field only when another field matches a condition.
- `options` — required for `select`, `radio`, and `multiselect`; not allowed on other types.

`select` / `radio` defaults must be one of the declared option `value`s (or `null`). A `multiselect` default must be a list of option values (often `[]`).

#### Field types

| `type` | Typical default | Notes |
| ------ | --------------- | ----- |
| `text` | `""` | Short string |
| `textarea` | `""` | Long string |
| `url` | `""` | Use `validation.format: uri` |
| `number` | a number | |
| `select` | one option `value` | Dropdown; requires `options` |
| `radio` | one option `value` | Requires `options` |
| `multiselect` | `[]` | Checkboxes; requires `options` |
| `boolean` | `false` | |
| `slider` | a number in range | Also accept `scale` and `rating` |
| `scale` | a number in range | |
| `rating` | a number in range | |
| `ip_addr` | `""` | Use `format: ipv4` or `ipv6` |
| `mac_addr` | `""` | Use `format: mac` |
| `channel_type` | a channel-type tuple string | Use `format: channel_type` |
| `matrix` | | No extra validation keys |

A `channel_type` default is the same `(id, repo)` tuple string used elsewhere, for example `"(1, 'https://github.com/harnice/harnice-general-library')"`.

#### Validation

Only these keys are allowed under `validation`, and only on the types listed. `errorMessages` and `custom` may sit alongside them.

| Field type | Allowed validation keys |
| ---------- | ----------------------- |
| `text`, `textarea` | `minLength`, `maxLength`, `pattern`, `format` |
| `url` | `format` |
| `number` | `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf` |
| `multiselect` | `minItems`, `maxItems`, `uniqueItems` |
| `slider`, `scale`, `rating` | `minimum`, `maximum`; `slider` also allows `multipleOf` |
| `ip_addr` | `pattern`, `format` |
| `mac_addr`, `channel_type` | `format` |
| `select`, `radio`, `boolean`, `matrix` | none |

Valid `format` values: `email`, `uri`, `date`, `date-time`, `time`, `uuid`, `ipv4`, `ipv6`, `hostname`, `mac`, `channel_type`.

`pattern` must be a valid regular expression. `minimum` may not exceed `maximum` (same for `minLength` / `maxLength` and `minItems` / `maxItems`).

#### Conditional fields (`show_if`)

```yaml
show_if:
  field: "other_field_id"
  operator: equals
  value: "some_answer"
```

`field` must be another field `id`. `value` is required unless the operator is `is_empty` or `is_not_empty`.

Operators: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `is_empty`, `is_not_empty`, `starts_with`, `ends_with`.

### Field type reference

Copy a block into `fields:` and change `id`, `label`, and `default`.

```yaml
# --- short text ---
- id: "device_name"
  type: text
  label: "Device name"
  required: true
  default: ""
  validation:
    minLength: 2
    maxLength: 60
    pattern: "^[A-Za-z0-9\\- ]+$"

# --- long text ---
- id: "install_notes"
  type: textarea
  label: "Installation notes"
  default: ""
  validation:
    maxLength: 500

# --- url ---
- id: "firmware_url"
  type: url
  label: "Firmware update URL"
  default: ""
  validation:
    format: uri

# --- number ---
- id: "port"
  type: number
  label: "Communication port"
  default: 502
  validation:
    minimum: 1
    maximum: 65535
    multipleOf: 1

# --- ip address ---
- id: "device_ip"
  type: ip_addr
  label: "Device IP address"
  default: ""
  validation:
    format: ipv4          # or: ipv6

# --- mac address ---
- id: "device_mac"
  type: mac_addr
  label: "Device MAC address"
  default: ""
  validation:
    format: mac

# --- channel type ---
- id: "channel_type"
  type: channel_type
  label: "Channel type"
  required: true
  default: "(1, 'https://github.com/harnice/harnice-general-library')"
  validation:
    format: channel_type

# --- single choice, dropdown ---
- id: "input_type"
  type: select
  label: "Input type"
  required: true
  default: "xlr"          # must be one of the option values below
  options:
    - value: "xlr"
      label: "XLR (Balanced)"
    - value: "trs"
      label: "TRS (Balanced)"
    - value: "rca"
      label: "RCA (Unbalanced)"

# --- single choice, radio buttons ---
- id: "state"
  type: radio
  label: "Device state"
  default: "standby"
  options:
    - value: "active"
      label: "Active"
    - value: "standby"
      label: "Standby"
    - value: "disabled"
      label: "Disabled"

# --- multiple choice, checkboxes ---
- id: "enabled_outputs"
  type: multiselect
  label: "Enabled outputs"
  default: []
  options:
    - value: "main"
      label: "Main"
    - value: "monitor"
      label: "Monitor"
    - value: "aux"
      label: "Aux"
  validation:
    minItems: 1
    maxItems: 3

# --- yes/no toggle ---
- id: "phantom_power"
  type: boolean
  label: "48V phantom power"
  default: false

# --- linear scale / slider ---
- id: "gain"
  type: slider              # or: scale / rating
  label: "Input gain (dB)"
  default: 0
  validation:
    minimum: -12
    maximum: 12
    multipleOf: 0.5

# --- only show based on a previous answer ---
# add this block under any field:
#   show_if:
#     field: "other_field_id"
#     operator: equals
#     value: "some_answer"
```

### Worked example

A full electrical-device form. This is reference only; a new device starts blank.

```yaml
fields:

  - id: "device_name"
    type: text
    label: "Device name"
    required: true
    default: ""
    validation:
      minLength: 2
      maxLength: 60

  - id: "device_ip"
    type: ip_addr
    label: "Device IP address"
    required: true
    default: ""
    validation:
      format: ipv4

  - id: "device_subnet"
    type: ip_addr
    label: "Subnet mask"
    required: true
    default: "255.255.255.0"
    validation:
      format: ipv4

  - id: "device_mac"
    type: mac_addr
    label: "Device MAC address"
    required: false
    default: ""
    validation:
      format: mac

  - id: "port"
    type: number
    label: "Communication port"
    required: true
    default: 502
    validation:
      minimum: 1
      maximum: 65535
      multipleOf: 1

  - id: "input_type"
    type: select
    label: "Input type"
    required: true
    default: "xlr"
    options:
      - value: "xlr"
        label: "XLR (Balanced)"
      - value: "trs"
        label: "TRS (Balanced)"
      - value: "rca"
        label: "RCA (Unbalanced)"
      - value: "optical"
        label: "Optical (S/PDIF)"

  - id: "gain"
    type: slider
    label: "Input gain (dB)"
    required: false
    default: 0
    validation:
      minimum: -12
      maximum: 12
      multipleOf: 0.5

  - id: "phantom_power"
    type: boolean
    label: "48V phantom power"
    required: false
    default: false
    # only relevant for balanced mic-level inputs
    show_if:
      field: "input_type"
      operator: equals
      value: "xlr"

  - id: "state"
    type: select
    label: "Device state"
    required: true
    default: "standby"
    options:
      - value: "active"
        label: "Active"
      - value: "standby"
        label: "Standby"
      - value: "disabled"
        label: "Disabled"
```

### Using answers in build instructions

Harnice injects `configuration` into `fileio.path("build instructions")`. On a standalone device build it is the setup defaults. On a system rebuild of a placed device it is that instance's answers, with setup defaults filling any missing keys.

```python
# configuration is a dict keyed by field id
input_type = configuration["input_type"]
phantom = configuration["phantom_power"]

if input_type == "xlr":
    channel_type = ch_type_ids["balanced_in"]
else:
    channel_type = ch_type_ids["unbalanced_in"]
```

One field is enough for a device that is either balanced or unbalanced. A mixing console might have a field per input so automatic channel mapping sees the type you actually set, and the instance records how to set the hardware up.

### Filling answers in a system

1. Place the device on the system block diagram.
1. Select it. If `fileio.path("configuration setup")` defines fields, a **Configuration** section appears in the properties panel.
1. Set the values for that instance. They are stored as JSON in a `<configuration>` child of the device group.
1. On system build, those answers are written to the BOM `configuration` column and passed into that instance's device rebuild.

If the placed device has no `<configuration>` child yet, Harnice seeds it from the setup defaults so the BOM and the properties panel stay in sync.

### Showing values on the symbol

In the device **block diagram symbol** editor, add attribute text whose `data-attribute-name` is `REFDES` or a configuration field `id`. On the device symbol, matching field ids preview the field default. On the system diagram, they show that instance's answers (`true` / `false` for booleans, comma-separated lists for multiselect).
