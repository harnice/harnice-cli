# Harnice command line

The `harnice` command builds a project from a terminal. It runs the same build as **Build** in the desktop app. You need Python 3.8 or newer.

## :material-download: Install

Install the command with pip or with uv.

### pip

```bash
python -m pip install harnice
```

That installs `harnice` into the Python you ran it with. If that Python is a virtual environment, activate the environment before you install, and activate it again in any new terminal before you build.

On a Homebrew Python, and on some Linux Pythons, pip refuses to install into that environment and says it is externally managed. Use uv there.

### uv

[uv](https://docs.astral.sh/uv/) is a Python package manager. `uv tool install` keeps Harnice in its own environment and puts the `harnice` command on your `PATH`, so a build works from any terminal.

Install uv if it is not already installed.

=== "macOS and Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    In PowerShell:

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "Homebrew"

    ```bash
    brew install uv
    ```

Open a new terminal so `uv` is on your `PATH`, then install Harnice:

```bash
uv tool install harnice
```

If uv prints that its bin directory is not on your `PATH`, run the command it shows, then open a new terminal.

## :octicons-terminal-16: Build

Open a terminal and go to the revision folder. That folder is named `rev1`, `rev2`, `revA`, and so on. It sits inside the part-number folder, and it is the folder that contains `build.py`.

```bash
cd path/to/ABC-123/rev1
```

From inside that folder, run:

```bash
harnice -b
```

`harnice -b` builds the folder the terminal is in. Change into `rev1` (or whichever revision you want) before you run it. If the terminal is in the part-number folder, `ABC-123`, Harnice prints that this is a part folder and tells you to `cd` into a revision folder.

The first time you build from a terminal, Harnice asks for your drawn-by name and saves it on this computer. Type the name and press Enter. Later builds use that name.

Harnice prints `Loaded PN: …, Rev: …`, then the rest of the build. An error is printed there. Fix the file it names and run `harnice -b` again from the same folder.
