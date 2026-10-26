import json
import os
from harnice import fileio, cli, state
from harnice import build_sandbox
from harnice.lists import instances_list, library_history, rev_history
from harnice.utils import build_utils

# Persisted in harnice_console_state.json (repo root); most recent first
_CONSOLE_STATE_FILENAME = "harnice_console_state.json"
_HARNESS_SYSTEM_HISTORY_KEY = "harness_system_references"
_HARNESS_SYSTEM_HISTORY_CAP = 50

default_desc = "HARNESS, DOES A FOR B"

button_color = "#ffa58a"


def _console_state_path():
    """Path to harnice_console_state.json in the Harnice repo root."""
    return os.path.join(fileio.harnice_root(), _CONSOLE_STATE_FILENAME)


def _load_console_state():
    """Load console state JSON as a dict. Returns {} if missing or invalid."""
    path = _console_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_console_state(data):
    """Write console state JSON, preserving other keys."""
    path = _console_state_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _pairs_from_history_value(raw):
    """Parse stored history into a list of (system_name, revision)."""
    out = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            system_name = str(item[0]).strip()
            revision = str(item[1]).strip()
        elif isinstance(item, dict):
            system_name = str(
                item.get("system_name") or item.get("part_number") or ""
            ).strip()
            revision = str(item.get("revision") or item.get("rev") or "").strip()
        else:
            continue
        if system_name and revision:
            out.append((system_name, revision))
    return out


def _load_system_ref_history():
    """Load list of (system_name, revision), most recent first. Returns [] if missing/invalid."""
    data = _load_console_state()
    return _pairs_from_history_value(data.get(_HARNESS_SYSTEM_HISTORY_KEY))


def _save_system_ref_history(history):
    """Write list of (system_name, revision) into console state, most recent first."""
    data = _load_console_state()
    data[_HARNESS_SYSTEM_HISTORY_KEY] = [
        [system_name, revision] for system_name, revision in history
    ]
    _save_console_state(data)


def _revision_for_system_name(history, system_name):
    """Return the revision stored with this system name (first/match = most recent), or last-used rev."""
    for sn, rev in history:
        if sn == system_name:
            return rev
    return history[0][1] if history else ""


def _prompt_system_pn_rev():
    """Prompt for system name (Tab cycles history) then revision (auto-filled from selection). Returns (system_pn, system_rev)."""
    import sys

    history = _load_system_ref_history()
    # prompt_toolkit needs a real TTY; console Build uses pipes — fall back to plain prompts.
    use_plain = (not history) or (not sys.stdin.isatty())
    if use_plain:
        default_pn = history[0][0] if history else None
        default_rev = history[0][1] if history else None
        system_pn = cli.prompt("Enter the system part number", default=default_pn)
        suggested_rev = (
            _revision_for_system_name(history, system_pn) if history and system_pn else default_rev
        )
        system_rev = cli.prompt(
            "Enter the system revision id (ex. rev1)",
            default=suggested_rev,
        )
        system_pn = (system_pn or "").strip()
        system_rev = (system_rev or suggested_rev or "").strip()
        if system_pn and system_rev:
            if history:
                _prepend_and_save(history, system_pn, system_rev)
            else:
                _save_system_ref_history([(system_pn, system_rev)])
        return system_pn, system_rev

    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.key_binding import KeyBindings

    # Tab cycles through system names only; each entry has an associated revision for the second prompt
    system_names = [sn for sn, _ in history]
    current_index = [0]

    def get_current_system_name():
        return system_names[current_index[0]]

    kb = KeyBindings()

    @kb.add("tab")
    def _(event):
        current_index[0] = (current_index[0] + 1) % len(system_names)
        event.app.current_buffer.text = get_current_system_name()

    @kb.add("s-tab")
    def _(event):
        current_index[0] = (current_index[0] - 1) % len(system_names)
        event.app.current_buffer.text = get_current_system_name()

    prompt_message = "Enter the system part number (Tab to cycle previous): "
    initial = get_current_system_name()
    system_pn = pt_prompt(
        prompt_message,
        default=initial,
        key_bindings=kb,
    ).strip()
    if not system_pn:
        system_pn = get_current_system_name()

    # Revision is cued from the selected system name (no Tab cycling on rev)
    suggested_rev = _revision_for_system_name(history, system_pn)
    system_rev = cli.prompt(
        "Enter the system revision id (ex. rev1)",
        default=suggested_rev,
    )
    system_rev = (system_rev or suggested_rev).strip()

    _prepend_and_save(history, system_pn, system_rev)
    return system_pn, system_rev


def _prepend_and_save(history, system_name, revision):
    """Prepend (system_name, revision) to history (avoid duplicate at front), keep finite size, save."""
    new = [(system_name, revision)]
    rest = [(s, r) for s, r in history if (s, r) != (system_name, revision)]
    _save_system_ref_history((new + rest)[:_HARNESS_SYSTEM_HISTORY_CAP])


documentation_description = "A harness is an assembly of connectors, cables, and other electrical components that connect multiple devices together. It is the physical item that is built and installed in a system."


def file_structure():
    return {
        "networks": {
            "flat.csv": "flattened network",
            "chosen.json": "chosen network",
            "available.json": "available network",
            "entities.json": "chosen entity list",
            # Reference CAD dropped in from the file browser. .step/.stp files
            # are drawn on the available and chosen network 3D pages. A harness
            # whose source system has a physical model also draws that
            # assembly.step, without copying it into this folder.
            "contexts": {},
        },
        "generated_svgs": {
            "flat.svg": "flattened network svg",
            "circuits.svg": "circuits overlay",
            "cable.svg": "cable overlay",
        },
        "build.py": "build instructions",
        "instances.tsv": "instances list",
        "libhist.tsv": "library history",
        "instance_data": {},
    }


def ensure_contexts_dir():
    """Create ``networks/contexts/`` so reference STEP files can be dropped in."""
    os.makedirs(fileio.dirpath("contexts"), exist_ok=True)


def generate_structure():
    os.makedirs(fileio.dirpath("networks"), exist_ok=True)
    ensure_contexts_dir()
    os.makedirs(fileio.dirpath("generated_svgs"), exist_ok=True)
    os.makedirs(fileio.dirpath("instance_data"), exist_ok=True)


def set_up_build_instructions_with_cli():
    """Prompt for the source system and write starting build instructions."""
    system_pn, system_rev = _prompt_system_pn_rev()
    if not system_pn or not system_rev:
        raise ValueError("System part number and revision are required")
    system_lib_repo = (cli.prompt("Enter the system library repo URL") or "").strip()
    if not system_lib_repo:
        raise ValueError(
            "System library repo URL is required "
            "(system must live in a repository_locations.csv library)"
        )
    system_lib_subpath = (
        cli.prompt("Enter the system library subpath (blank if none)", default="")
        or ""
    ).strip()
    target_harness = (
        cli.prompt("Enter the harness name you want to build this harness from") or ""
    ).strip()
    if not target_harness:
        raise ValueError("Source system harness reference designator is required")
    set_up_build_instructions_from_system_definition(
        system_pn,
        system_rev,
        target_harness,
        source_system_repository=system_lib_repo.strip(),
        source_system_subpath=system_lib_subpath.strip(),
    )


def set_up_build_instructions_from_system_definition(
    source_system_part_number,
    source_system_revision,
    source_system_harness_reference_designator,
    source_system_repository,
    source_system_subpath="",
):
    """Write default harness build instructions and stamp source_* on revision history.

    Requires ``state.pn`` / ``state.rev`` and cwd to be the harness revision folder
    (so ``fileio.path("build instructions")`` resolves). System revision is normalized
    to ``rev…`` form. The system is found via ``repository_locations.csv`` (repo URL)
    plus lib subpath. Import itself happens at build from ``rev_history.read()``.
    """
    system_pn = (source_system_part_number or "").strip()
    system_rev = (source_system_revision or "").strip()
    target_harness = (source_system_harness_reference_designator or "").strip()
    system_lib_repo = (source_system_repository or "").strip()
    system_lib_subpath = (source_system_subpath or "").strip()
    if not system_pn or not system_rev or not target_harness:
        raise ValueError(
            "source system part number, revision, and harness refdes are required"
        )
    if not system_lib_repo:
        raise ValueError(
            "source_system_repository is required "
            "(system must live in a repository_locations.csv library)"
        )
    if not system_rev.lower().startswith("rev"):
        system_rev = f"rev{system_rev}"

    structure = file_structure()
    state.set_file_structure(structure)

    build_instructions_text = build_utils.default_contents(
        "harness_default_build_instructions.py",
    )
    with open(
        fileio.path("build instructions", structure_dict=structure),
        "w",
        encoding="utf-8",
    ) as f:
        f.write(build_instructions_text)

    _prepend_and_save(_load_system_ref_history(), system_pn, system_rev)

    rev_history.overwrite(
        {
            "source_part_number": system_pn,
            "source_revision": system_rev,
            "source_lib_repo": system_lib_repo,
            "source_subpath": system_lib_subpath,
            "source_refdes": target_harness,
        }
    )


def build():
    # ======================================================================
    # 1. Build instructions file does not exist: prompt user and create it
    # ======================================================================
    if not os.path.exists(
        fileio.path("build instructions", structure_dict=file_structure())
    ):
        set_up_build_instructions_with_cli()

    # ======================================================================
    # 2. Init library + instances list
    # ======================================================================
    library_history.new()
    instances_list.new()
    instances_list.new_instance(
        "origin",
        {
            "instance_name": "origin",
            "item_type": "origin",
            "location_type": "node",
        },
    )

    # ======================================================================
    # 3. Run build instructions
    # ======================================================================
    from harnice.utils import pdf_drawings_utils

    pdf_drawings_utils.reset_pdf_generator_runs()
    try:
        build_sandbox.run_path(fileio.path("build instructions"), run_name="__main__")

        # Persist Analyze overlays (same role as system block-diagram applied-traces).
        from harnice.lists import flattened_network

        flattened_network.write_trace_overlays_svg()
    except Exception:
        pdf_drawings_utils.watermark_existing_pdfs_incomplete_rebuild()
        raise

    print(f"Harnice: harness {state.partnumber('pn')} built successfully!\n")
