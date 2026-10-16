import argparse
import os
import sys
import shutil
import traceback
from time import sleep

try:
    from colorama import Fore, Style, just_fix_windows_console
except ImportError:
    class _PlainColor:
        YELLOW = ""
        RED = ""
        RESET_ALL = ""

    Fore = Style = _PlainColor()

    def just_fix_windows_console():
        return None

from harnice.lists import rev_history
from harnice import state
from harnice import fileio


def _colored(text, color):
    just_fix_windows_console()
    return "\n".join(
        f"{color}{line}{Style.RESET_ALL}" for line in str(text).splitlines()
    )


def warn(message):
    """Print ``Warning: {message}`` to stdout in yellow.

    **Args:**
    - `message`: Warning text (the ``Warning:`` prefix is added).
    """
    print(_colored(f"Warning: {message}", Fore.YELLOW), flush=True)


def fatal(message, code=1):
    """Print an error to stdout in red and exit."""
    print(_colored(f"Error: {message}", Fore.RED), flush=True)
    raise SystemExit(code)


def _excepthook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    print(
        _colored("".join(traceback.format_exception(exc_type, exc, tb)).rstrip(), Fore.RED),
        file=sys.stderr,
        flush=True,
    )

logo = [
    r"__/\\\_______________________________________________________________________________________        ",
    r" _\/\\\_______________________________________________________________________________________       ",
    r"  _\/\\\_____________________________________________________/\\\______________________________      ",
    r"   _\/\\\__________/\\\\\\\\\_____/\\/\\\\\\\___/\\/\\\\\\___\///______/\\\\\\\\_____/\\\\\\\\__     ",
    r"    _\/\\\\\\\\\\__\////////\\\___\/\\\/////\\\_\/\\\////\\\___/\\\___/\\\//////____/\\\/////\\\_    ",
    r"     _\/\\\/////\\\___/\\\\\\\\\\__\/\\\___\///__\/\\\__\//\\\_\/\\\__/\\\__________/\\\\\\\\\\\__   ",
    r"      _\/\\\___\/\\\__/\\\/////\\\__\/\\\_________\/\\\___\/\\\_\/\\\_\//\\\________\//\\///////___  ",
    r"       _\/\\\___\/\\\_\//\\\\\\\\/\\_\/\\\_________\/\\\___\/\\\_\/\\\__\///\\\\\\\\__\//\\\\\\\\\\_ ",
    r"        _\///____\///___\////////\//__\///__________\///____\///__\///_____\////////____\//////////__"
]

high_contrast_logo = [
    r"  /\\\                                                                                               ",
    r"  \/\\\                                                                                              ",
    r"   \/\\\                                                     /\\\                                    ",
    r"    \/\\\          /\\\\\\\\\     /\\/\\\\\\\   /\\/\\\\\\   \///      /\\\\\\\\     /\\\\\\\\       ",
    r"     \/\\\\\\\\\\  \////////\\\   \/\\\/////\\\ \/\\\////\\\   /\\\   /\\\//////    /\\\/////\\\     ",
    r"      \/\\\/////\\\   /\\\\\\\\\\  \/\\\   \///  \/\\\  \//\\\ \/\\\  /\\\          /\\\\\\\\\\\     ",
    r"       \/\\\   \/\\\  /\\\/////\\\  \/\\\         \/\\\   \/\\\ \/\\\ \//\\\        \//\\///////     ",
    r"        \/\\\   \/\\\ \//\\\\\\\\/\\ \/\\\         \/\\\   \/\\\ \/\\\  \///\\\\\\\\  \//\\\\\\\\\\  ",
    r"         \///    \///   \////////\//  \///          \///    \///  \///     \////////    \//////////  "
]

favicon = [
    r"  /\\\                  ",
    r"  \/\\\                 ",
    r"   \/\\\                ",
    r"    \/\\\               ",
    r"     \/\\\\\\\\\\       ",
    r"      \/\\\/////\\\     ",
    r"       \/\\\   \/\\\    ",
    r"        \/\\\   \/\\\   ",
    r"         \///    \///   "
]

def main():
    sys.excepthook = _excepthook
    from harnice.runtime import apply_source_checkout_env

    apply_source_checkout_env()
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify-revision":
        from harnice import fileio as fileio_mod

        fileio_mod.verify_revision_structure()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--gui-server":
        _run_console_server_only()
        return

    if len(sys.argv) == 1:
        _run_console()
        return

    # Ensure cwd exists
    try:
        cwd = os.getcwd()
    except (FileNotFoundError, PermissionError):
        fatal(
            "The current working directory is invalid "
            "(it may have been deleted or you lack permission to access it)."
        )

    if not os.path.exists(cwd):
        fatal(f"The current working directory no longer exists: {cwd}")

    # -----------------------------
    # Argument parsing
    # -----------------------------
    parser = argparse.ArgumentParser(
        prog="harnice",
        description="Electrical system CAD",
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "-b", "--build", action="store_true", help="Build the project normally"
    )

    group.add_argument(
        "--newrev",
        action="store_true",
        help="Create a new revision in the current working directory",
    )

    group.add_argument(
        "--newpn",
        action="store_true",
        help="Create a new part number from the current revision",
    )

    args = parser.parse_args()

    # -----------------------------
    # Handle new revision / part number creation and exit
    # -----------------------------
    if args.newrev:
        newrev()
        return

    if args.newpn:
        newpn()
        return

    # -----------------------------
    # Ensure we are inside a revision folder
    # -----------------------------
    fileio.verify_revision_structure()
    item_type = rev_history.info(field="project_type")

    # -----------------------------
    # Load project type module
    # -----------------------------
    try:
        product_module = __import__(
            f"harnice.project_types.{item_type}", fromlist=[item_type]
        )
    except ModuleNotFoundError:
        fatal(f"Unknown project type: '{item_type}'")

    # -----------------------------
    # Set the default fileio structure dict to the project type's file_structure()
    # -----------------------------
    if hasattr(product_module, "file_structure"):
        structure = product_module.file_structure()
        state.set_file_structure(structure)
    else:
        fatal(f"Project type '{item_type}' must define file_structure()")

    # -----------------------------
    # Generate project type file structure
    # -----------------------------
    if hasattr(product_module, "generate_structure"):
        product_module.generate_structure()
    else:
        fatal(f"Project type '{item_type}' must define generate_structure()")

    # -----------------------------
    # Execute build logic
    # -----------------------------
    rev_history.update_datemodified()
    try:
        product_module.build()
    except SystemExit as e:
        code = e.code
        if code is None:
            failed = False
        elif isinstance(code, int):
            failed = code != 0
        else:
            failed = True
        rev_history.update_last_build("failed" if failed else "succeeded")
        raise
    except Exception:
        # Build errors belong in the console, not the GUI "failed to start" alert.
        try:
            rev_history.update_last_build("failed")
        except Exception:
            pass
        sys.excepthook(*sys.exc_info())
        raise SystemExit(1)

    rev_history.update_last_build("succeeded")
    return


def _require_desktop():
    """The window ships in the desktop app. The pip package is the build command."""
    try:
        import harnice.gui.console_server  # noqa: F401
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing == "harnice.gui" or missing.startswith("harnice.gui."):
            fatal(
                "This install of Harnice is the command-line package. "
                "Download the desktop app from https://harnice.io/."
            )
        raise


def _run_console(open_browser=False):
    """Launch the Harnice console (can be run from any directory)."""
    _require_desktop()
    from harnice.runtime import apply_source_checkout_env

    apply_source_checkout_env()
    # Ensure function_index.json is up to date for the editor dropdowns
    print("\n", flush=True)
    print("Launching Harnice console...", flush=True)
    print("\n", flush=True)
    sleep(0.3)
    for line in logo:
        print(line, flush=True)
    print("\n\n", flush=True)
    sleep(0.6)

    from harnice.runtime import is_standalone_app

    if not is_standalone_app():
        from harnice.gui.build_instructions_gui import build as build_function_index

        build_function_index()

    from harnice.gui.console_server import run_server

    run_server(port=0, open_browser=open_browser)


def _run_console_server_only():
    """HTTP console backend for an extra native window (no Dock icon / no window)."""
    _require_desktop()
    from harnice.runtime import (
        apply_source_checkout_env,
        hide_from_dock,
        is_standalone_app,
    )

    apply_source_checkout_env()

    if is_standalone_app():
        hide_from_dock()
    else:
        from harnice.gui.build_instructions_gui import build as build_function_index

        build_function_index()

    from harnice.gui.console_server import run_server

    # Same as the first window: do not mount process cwd; open the first
    # recent project if any, otherwise start with nothing mounted.
    run_server(
        rev_folder=None,
        port=0,
        open_browser=False,
        native_window=False,
        remember=False,
    )


def prompt(text, default=None):
    """Print a prompt and read a line from stdin.

    The prompt is written with a trailing newline and flushed so piped
    consumers (e.g. the Harnice console output panel, which reads line-by-line)
    can display it before the process blocks on input.
    """
    p = f"{text}"
    if default:
        p += f" [{default}]"
    p += ":"
    print(p, flush=True)
    try:
        line = input()
    except EOFError:
        return default
    return line.strip() or default


def _suggest_next_revision(current: str) -> str:
    """Suggest the next rev when current is all-digits or a single letter (A–Z / a–z)."""
    s = (current or "").strip()
    if not s:
        return "1"
    if s.isdigit():
        return str(int(s) + 1)
    if len(s) == 1:
        c = s
        if "A" <= c <= "Y":
            return chr(ord(c) + 1)
        if c == "Z":
            return "1"
        if "a" <= c <= "y":
            return chr(ord(c) + 1)
        if c == "z":
            return "1"
    return "1"


def newrev():
    from harnice import fileio

    """
    Create a new revision directory by copying the current revision's contents
    and updating filenames to reflect the new revision number.
    """
    # Ensure revision structure is valid and get context
    fileio.verify_revision_structure()

    current_r = state.partnumber("R")
    new_rev_number = prompt(
        f"Current rev number: {current_r}. Enter new rev number:",
        default=_suggest_next_revision(current_r),
    )

    new_rev_dir = os.path.join(
        fileio.part_directory(),
        fileio.revision_folder_name(new_rev_number),
    )

    # Ensure target directory does not already exist
    if os.path.exists(new_rev_dir):
        raise FileExistsError(f"Revision directory already exists: {new_rev_dir}")

    shutil.copytree(fileio.rev_directory(), new_rev_dir)

    # Walk the new directory and rename all files containing the old rev number
    for root, _, files in os.walk(new_rev_dir):
        for filename in files:
            new_suffix = f"rev{new_rev_number}"

            if state.partnumber("rev") in filename:
                old_path = os.path.join(root, filename)
                new_name = filename.replace(state.partnumber("rev"), new_suffix)
                new_path = os.path.join(root, new_name)

                os.rename(old_path, new_path)

    print(
        f"Successfully created new revision: {os.path.basename(new_rev_dir)}. Please cd into it."
    )


def newpn():
    """Create a new part-number directory by copying the current revision's contents
    and updating filenames to reflect the new part number (and optional new rev).
    """
    fileio.verify_revision_structure()

    current_pn = state.partnumber("pn")
    new_pn = prompt(
        f"Current part number: {current_pn}. Enter new part number:",
    )
    if not new_pn or not str(new_pn).strip():
        raise ValueError("New part number cannot be blank")
    new_pn = str(new_pn).strip()
    if any(c in new_pn for c in ("/", "\\")) or new_pn in (".", ".."):
        raise ValueError(f"Invalid part number: {new_pn}")

    current_r = state.partnumber("R")
    new_rev_number = prompt(
        f"Current rev number: {current_r}. Enter new rev number:",
        default="1",
    )
    if not new_rev_number or not str(new_rev_number).strip():
        raise ValueError("New rev number cannot be blank")
    new_rev_number = str(new_rev_number).strip()

    parent_dir = os.path.dirname(fileio.part_directory())
    new_pn_dir = os.path.join(parent_dir, new_pn)
    new_rev_dir = os.path.join(
        new_pn_dir,
        fileio.revision_folder_name(new_rev_number),
    )

    if os.path.exists(new_pn_dir):
        raise FileExistsError(f"Part number directory already exists: {new_pn_dir}")

    shutil.copytree(fileio.rev_directory(), new_rev_dir)

    old_rev_token = state.partnumber("rev")
    new_rev_token = f"rev{new_rev_number}"

    for root, _, files in os.walk(new_rev_dir):
        for filename in files:
            new_name = filename
            if current_pn in new_name:
                new_name = new_name.replace(current_pn, new_pn)
            if old_rev_token in new_name:
                new_name = new_name.replace(old_rev_token, new_rev_token)
            if new_name != filename:
                os.rename(os.path.join(root, filename), os.path.join(root, new_name))

    print(
        f"Successfully created new part number: {new_pn}/{os.path.basename(new_rev_dir)}. Please cd into it."
    )


def select_project_type():
    import sys

    from harnice.project_types import available_names

    available_types = available_names()
    if not available_types:
        fatal("No project types are available")
    type_map = {p.lower(): p for p in available_types}

    # prompt_toolkit needs a real TTY; console Build uses pipes — use plain prompts.
    if not sys.stdin.isatty():
        print(f"Valid project types: {', '.join(available_types)}")
        while True:
            value = (prompt("Select project type") or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in type_map:
                return type_map[key]
            warn(
                f"Unrecognized project type '{value}'. "
                f"Valid options: {', '.join(available_types)}"
            )

    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.completion import WordCompleter

    def show_completions_immediately():
        app = get_app()
        buf = app.current_buffer
        if buf.complete_state:
            buf.complete_next()
        else:
            buf.start_completion(select_first=False)

    completer = WordCompleter(
        available_types,
        ignore_case=True,
        sentence=True,
    )

    while True:
        value = pt_prompt(
            "Select project type: ",
            completer=completer,
            pre_run=show_completions_immediately,
        ).strip()

        if not value:
            continue

        key = value.lower()
        if key in type_map:
            return type_map[key]

        warn(
            f"Unrecognized project type '{value}'. "
            f"Valid options: {', '.join(available_types)}"
        )
