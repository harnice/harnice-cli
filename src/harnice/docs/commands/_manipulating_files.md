# Keeping Track of Files

The `fileio` module keeps files organized. With the tools described in this page, you should never need to reference a file by constructing a path from scratch.

## Part number and revision folders

Harnice requires a revision folder and a part number folder to be able to build any project.

```python
# suppose your part number is "123456" and your revision is "A"

|-- A123456/
    L--   revA/
```

If you're starting a new project, click **New project…** in Harnice. Harnice creates the part-number folder, the first revision folder, and the right file structure.

Revision history data will be stored automatically inside the part number folder. That is the file that tells Harnice what kind of project you're currently working on, among other things. 

If you need to make a new revision of a project, right-click the project and choose **New rev…**.

## Project file structures

Projects and macros have their own pre-defined **file structure**. It's stored as a function inside the Harnice source code. Here's an example of the **Harness** one:

```python
def file_structure(): # example of a file structure of a project
    return {
        "build.py": "build instructions",
        "instances.tsv": "instances list",
        "libhist.tsv": "library history",
        "flat.csv": "flattened network",
        "available.json": "available network",
        "chosen.json": "chosen network",
        "entities.json": "chosen entity list",
    }
```

A file structure is defined for each project or macro. It is automatically passed into the code when that project or macro is ran. 

Here's the basics of how to read a file structure dictionary:

- **Files**: each file is a key–value pair where the **key** is the filename and the **value** is a short, human-readable **file key** (e.g. `"myfile.tsv": "signals list"`). You use the file key with `fileio.path("signals list")`.
- **Directories**: a directory is a key whose **value** is another dict (empty `{}` or more key–value pairs). The **key** is the directory name and is what you pass to `fileio.dirpath("dirname")`.

## Quick-start: accessing default files


??? info "`fileio.path(target_value, structure_dict=None, base_directory=None)`"

    Return the full path to a file identified by its file key.
    
    * file structure dict (`state.file_structure`, or **structure_dict** if provided) is searched for a *value* equal to **target_value**. The path is built from the rev directory + **base_directory** (if any) + the key path to that value.
    
    **Special Target Values:**
    
    - **`revision history`:** the revision history file of the project you're currently working on
    - **`repository locations`:** the repository locations file on your computer (`repository_locations.csv`)
    - **`drawnby`:** the text file on your computer that stores your name
    - **`rev directory`:** the revsion directory of the project you're currently working on
    - **`part directory`:** the part directory of the project you're currently working on
    
    **Args:**
    
    - **target_value** — File key to look up (e.g. `"signals list"`, `"build instructions"`).
    - **structure_dict** — Optional. Override the default structure (e.g. for a macro).
        If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory to use as
        the root for structure paths. If `None` or `""`, paths are under the rev directory only.
    
    **Returns:** Absolute path to the file (`str`).
    
    **Raises:** `TypeError` if **target_value** is not found in the structure (for non-special keys).
    
    **First run**
    - If `repository locations` is missing, Harnice creates an empty CSV without
      prompting. If `drawnby.json` is missing, the CLI (`harnice -b`,
      `--newrev`, `--newpn`) asks for your name when stdin is a terminal and
      writes it there. The desktop app asks from Settings (gear) → Drawn by…
      instead. The name is never guessed.

??? info "`fileio.dirpath(target_key, structure_dict=None, base_directory=None)`"

    Return the full path to a directory identified by its key in the file structure.
    
    Searches the file structure (`state.file_structure` or **structure_dict**) for a
    *key* equal to **target_key** (directory names are keys; file keys are values).
    The path is built from the rev directory + **base_directory** (if any) + the path to that key.
    
    **Special Target Keys:**
    
    - **`part directory`:** part directory of the project you're currently working on
    - **`rev directory`:** rev directory of the project you're currently working on
    
    **Args:**
    
    - **target_key** — Directory name in the structure (e.g. `"lists"`, `"maps"`).
        Pass `None` to get the rev directory (or rev + **base_directory**).
    - **structure_dict** — Optional. Override the default structure. If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory. If `None` or `""`,
        paths are under the rev directory only.
    
    **Returns:** Absolute path to the directory (`str`).
    
    **Raises:** `TypeError` if **target_key** is not `None` and not found in the structure.



Use these two functions to access fils of any project. For most purposes, you can omit `structure_dict` and `base_directory`.

## The other arguments in `fileio.path()` and `fileio.dirpath()`

You can see from the above two functions that there are two optional arguments: `structure_dict` and `base_directory`. Here's what those mean:

**`structure_dict`:**

 - This is the file structure dictionary that is actually parsed to find the file path.
 - By default, the file structure of the project that's currently being run by Harnice is passed in at runtime.
 - Alternatively, if you need to pass a special structure dict in, you can do that here. You can do this, for example, if you have a custom macro or a custom file structure preference for an existing project.

**`base_directory`:**

 - This is the directory from which the relative paths from the file structure dictionary originates. 
 - By default, this is set to the revision folder of the project you're working on. This means that the file structure dictionary of the project is in reference to, or added on top of, the revision file of the current project.
 - If you need to reference files in another project, for example, or recursively with a macro that's called as an instance, that has its own sub-instances, you can change the base directory of the file structure dictionary to point to wherever you want with this. 

## Parametric file names in your folder structure

You can add extra arguments to `file_structure()` (and pass a custom dict into fileio) for more complex layouts. For example, maybe you need a filename that is controlled by a variable, like in this example:

```python
def macro_file_structure(page_name=None, page_counter=None):
    return {
        f"{artifact_id}-mastercontents.svg": "master contents svg",
        f"{artifact_id}.pdf": "output pdf",
        "page_svgs": {
            f"{page_counter}-{page_name}-user-editable.svg": "user editable page svg"
        },
    }
```

## Accessing the current part number and rev

Behind the scenes, Harnice stores the current part number and revision number in the module `state`. You can query it in any format you may need. 

??? info "`state.partnumber(format)`"

    Return the current part number and/or revision in the requested format.
    
    Assumes `state.pn` and `state.rev` are set (e.g. by `fileio.verify_revision_structure()`).
    For a part `"mypart"` and rev `1`:
    
    **Args:**
    
    - **format** — One of:
        - `"pn-rev"`: full part-rev string, e.g. `"mypart-rev1"`
        - `"pn"`: part number only, e.g. `"mypart"`
        - `"rev"`: revision label, e.g. `"rev1"`
        - `"R"`: revision number only, e.g. `"1"`
    
    **Returns:** The requested substring of `"pn-revRev"` (e.g. `"mypart-rev1"`) (`str`).
    
    **Raises:** `ValueError` if **format** is not one of the options above.


---
##Commands
*These functions are already available in build instructions as `fileio`. Use them as written.*
??? info "`state.partnumber(format)`"

    Return the current part number and/or revision in the requested format.
    
    Assumes `state.pn` and `state.rev` are set (e.g. by `fileio.verify_revision_structure()`).
    For a part `"mypart"` and rev `1`:
    
    **Args:**
    
    - **format** — One of:
        - `"pn-rev"`: full part-rev string, e.g. `"mypart-rev1"`
        - `"pn"`: part number only, e.g. `"mypart"`
        - `"rev"`: revision label, e.g. `"rev1"`
        - `"R"`: revision number only, e.g. `"1"`
    
    **Returns:** The requested substring of `"pn-revRev"` (e.g. `"mypart-rev1"`) (`str`).
    
    **Raises:** `ValueError` if **format** is not one of the options above.

??? info "`fileio.path(target_value, structure_dict=None, base_directory=None)`"

    Return the full path to a file identified by its file key.
    
    * file structure dict (`state.file_structure`, or **structure_dict** if provided) is searched for a *value* equal to **target_value**. The path is built from the rev directory + **base_directory** (if any) + the key path to that value.
    
    **Special Target Values:**
    
    - **`revision history`:** the revision history file of the project you're currently working on
    - **`repository locations`:** the repository locations file on your computer (`repository_locations.csv`)
    - **`drawnby`:** the text file on your computer that stores your name
    - **`rev directory`:** the revsion directory of the project you're currently working on
    - **`part directory`:** the part directory of the project you're currently working on
    
    **Args:**
    
    - **target_value** — File key to look up (e.g. `"signals list"`, `"build instructions"`).
    - **structure_dict** — Optional. Override the default structure (e.g. for a macro).
        If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory to use as
        the root for structure paths. If `None` or `""`, paths are under the rev directory only.
    
    **Returns:** Absolute path to the file (`str`).
    
    **Raises:** `TypeError` if **target_value** is not found in the structure (for non-special keys).
    
    **First run**
    - If `repository locations` is missing, Harnice creates an empty CSV without
      prompting. If `drawnby.json` is missing, the CLI (`harnice -b`,
      `--newrev`, `--newpn`) asks for your name when stdin is a terminal and
      writes it there. The desktop app asks from Settings (gear) → Drawn by…
      instead. The name is never guessed.

??? info "`fileio.dirpath(target_key, structure_dict=None, base_directory=None)`"

    Return the full path to a directory identified by its key in the file structure.
    
    Searches the file structure (`state.file_structure` or **structure_dict**) for a
    *key* equal to **target_key** (directory names are keys; file keys are values).
    The path is built from the rev directory + **base_directory** (if any) + the path to that key.
    
    **Special Target Keys:**
    
    - **`part directory`:** part directory of the project you're currently working on
    - **`rev directory`:** rev directory of the project you're currently working on
    
    **Args:**
    
    - **target_key** — Directory name in the structure (e.g. `"lists"`, `"maps"`).
        Pass `None` to get the rev directory (or rev + **base_directory**).
    - **structure_dict** — Optional. Override the default structure. If `None`, uses `state.file_structure`.
    - **base_directory** — Optional. Subdirectory under the rev directory. If `None` or `""`,
        paths are under the rev directory only.
    
    **Returns:** Absolute path to the directory (`str`).
    
    **Raises:** `TypeError` if **target_key** is not `None` and not found in the structure.

??? info "`fileio.silentremove(filepath)`"

    Remove a file or directory and its contents if it exists.
    
    No-op if the path does not exist. Removes symlinks as files (does not follow).
    
    **Args:**
    
    - **filepath** — Path to the file or directory to remove.

??? info "`fileio.get_git_hash_of_harnice_src()`"

    Return the git commit hash of the Harnice source repo (HEAD).
    
    Used for version/attribution in outputs. Returns `"UNKNOWN"` if git is
    unavailable or the repo cannot be read.

??? info "`fileio.read_tsv(filepath, delimiter='\t')`"

    Read a TSV file and return a list of row dicts (one dict per row, keys from header).
    
    If **filepath** is an existing file path, that file is read. If not, **filepath** is
    treated as a file key and `fileio.path(filepath)` is used to resolve the path
    (e.g. `"instances list"` or `"signals list"`).
    
    **Args:**
    
    - **filepath** — Path to a TSV file, or a file key (e.g. `"instances list"`).
    - **delimiter** — Column delimiter; default `"\t"`.
    
    **Returns:** List of dicts, one per data row, with keys from the header row (`list`).
    
    **Raises:** `FileNotFoundError` if the path does not exist or the resolved path does not exist.

??? info "`fileio.drawnby()`"

    Load and return the contents of the drawnby file (path from `fileio.path("drawnby")`).
    
    The drawnby file stores author/credits info on this computer.
    
    That file should be structured like this, and this function will return exactly the same as a json object:
    ```json
    {
        "name": "K SHUTT"
    }
    ```
    Use case:
    ```python
    name = fileio.drawnby().get("name")
    ```
    
    The CLI asks for this name on a terminal when the file does not exist yet.
    The desktop app asks from Settings (gear) → Drawn by….

??? info "`fileio.today()`"

    Return today's date as a short string: `M/D/YY` (e.g. `2/12/25`).

This one happens behind the scenes, but here's how it knows you're in the right folder structure:

??? info "`fileio.verify_revision_structure()`"

    Ensure the current directory is a valid revision folder and set `state.pn` and `state.rev`.
    
    Called before building and when the console opens a project.
    
    **Behavior:**
    
    - If cwd is a `rev<N>` folder: sets `state.pn` and `state.rev` from the path.
    - If cwd is a part folder that contains rev folders: prints a message and exits.
    - Otherwise: fails — create new projects from the Harnice console (**New project…**).
    
    Ensures revision_history exists and that the revision status is blank (Harnice only
    builds revisions with blank status). Updates revision_history library_repo /
    library_subpath from the current path. Does not change ``datemodified``; that
    is stamped when the project is built.

