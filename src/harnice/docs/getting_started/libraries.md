# Libraries

Libraries are repositories of reusable parts, macros, titleblocks, flagnotes, and other components that can be shared across projects. Instead of recreating the same connector, device, or macro for every project, you can define it once in a library and reference it wherever needed.

==**Parts, macros, titleblocks, flagnotes, etc., should be re-used and referenced for any future use.**==

Users are heavily encouraged to contribute to the Harnice repo for your COTS parts. The less work we all have to do, the better!

---

## :material-folder-network: Library Structure

Libraries are organized by item type and manufacturer part number (MPN). Here's the typical structure:

```
library_public/
├── Connector/
│   ├── D38999_26ZA98PN/
│   │   ├── rev1/
│   │   │   ├── fileio.path("attributes")
│   │   │   ├── fileio.path("drawing")
│   │   │   ├── fileio.path("drawing png")
│   │   │   └── fileio.path("model")
│   │   └── fileio.path("revision history")
│   └── ...
├── Device/
├── Cable/
├── Macro/
│   ├── harness_artifacts/
│   └── system_artifacts/
├── Titleblock/
├── Flagnote/
└── ...
```

Each part has:
- **Revision folders**: `rev{N}`
- **Part files**: Look them up with `fileio.path(...)` — attributes, drawings, signals lists, build instructions, and so on
- **Revision history**: `fileio.path("revision history")`

---

## :octicons-arrow-switch-16: Configuring Library Paths

You can define paths to as many library repositories as you want. This allows you to:
- Use the public Harnice library
- Maintain your own private library
- Reference libraries from different repositories or local directories

### Setting Up Repository Locations

Open **Library locations** in Harnice. Each row maps a library repository URL to a local filesystem path:

```csv
repo_url,local_path
https://github.com/harnice/harnice-general-library,/Users/kenyonshutt/Documents/GitHub/harnice-general-library
https://github.com/mycompany/our-library,/Users/kenyonshutt/Documents/GitHub/our-library
```

**Important notes:**
- The `repo_url` should be traceable by your collaborators (use a GitHub/GitLab URL)
- The `local_path` points to where the library files live on your computer
- Paths can use `~` which will be expanded to your home directory
- This file is typically ignored by git since each user will have different local paths

If `fileio.path("repository locations")` doesn't exist, Harnice will automatically create it with a default entry pointing to the public library.

---

## :material-import: Importing Parts from Libraries

Parts are imported from libraries using `library_utils.pull()` in your build instructions. This function:

1. Validates required fields (`lib_repo`, `mpn`, `item_type`)
2. Determines which revision to use (specified or latest available)
3. Copies the library revision to `lib` (read-only reference)
4. Copies editable files to the instance directory (only if not already present)
5. Updates the instances list with library metadata
6. Records the import in library history

### Basic Import Example

```python
# Import a connector from the library
library_utils.pull({
    "instance_name": "X1.B.conn",
    "lib_repo": "https://github.com/harnice/harnice-general-library",
    "mpn": "D38999_26ZA98PN",
    "item_type": "connector"
})
```

### Importing with Specific Revision

```python
# Import a specific revision
library_utils.pull({
    "instance_name": "X1.B.conn",
    "lib_repo": "https://github.com/harnice/harnice-general-library",
    "mpn": "D38999_26ZA98PN",
    "item_type": "connector",
    "lib_rev_used_here": "1"  # or "rev1"
})
```

### Importing from Subdirectories

Some libraries organize parts into subdirectories:

```python
# Import a device from a subdirectory
library_utils.pull({
    "instance_name": "X1",
    "lib_repo": "https://github.com/harnice/harnice-general-library",
    "mpn": "tascam-db25",
    "item_type": "device",
    "lib_subpath": "audio"  # subdirectory under the library root
})
```

### Using Local Library

For parts stored locally in your project:

```python
library_utils.pull({
    "instance_name": "local-part-1",
    "lib_repo": "local",  # Use "local" for project-local library
    "mpn": "MY-PART-123",
    "item_type": "connector"
})
```

### Batch importing in build instructions

A common pattern is to import all parts of certain types from your instances list:

```python
# Import all connectors and backshells from the instances list
for instance in instances_list.read():
    if instance.get("item_type") in ["connector", "backshell"]:
        if instance.get("lib_repo"):  # Only import if library info exists
            library_utils.pull(instance)
```

---

## :octicons-git-branch-16: Library Version Control

All parts in a library are version controlled using revisions. This ensures you can:
- Track changes to parts over time
- Use specific revisions when needed
- Update to newer revisions when available

### How Revisions Work

When you import a part:
- **If you specify a revision**: Harnice uses that exact revision
- **If you don't specify a revision**: Harnice automatically uses the latest available revision
- **If a newer revision exists**: Harnice will warn you in the import status

### Revision Selection

```python
# Use latest revision (default)
library_utils.pull({
    "instance_name": "connector-1",
    "lib_repo": "https://github.com/harnice/harnice-general-library",
    "mpn": "D38999_26ZA98PN",
    "item_type": "connector"
    # No lib_rev_used_here → uses latest
})

# Pin to specific revision
library_utils.pull({
    "instance_name": "connector-1",
    "lib_repo": "https://github.com/harnice/harnice-general-library",
    "mpn": "D38999_26ZA98PN",
    "item_type": "connector",
    "lib_rev_used_here": "1"  # Always use rev1
})
```

### Imported Part Structure

When a part is imported, it's organized like this:

```
fileio.dirpath("instance_data")
└── connector/
    └── X1.B.conn/
        ├── lib/     # Read-only reference copy
        │   └── rev1/
        │       ├── fileio.path("attributes")
        │       ├── fileio.path("drawing")
        │       └── fileio.path("model")
        └── fileio.path("drawing")        # Editable copy (if needed)
```

The `lib` folder contains the exact version imported from the library and should not be modified. Editable files (like drawings) are copied to the instance directory only if they don't already exist, allowing you to customize them for your project.

---

## :material-share-variant: Contributing to Libraries

Contributing parts to the public library benefits everyone! Here's what you can contribute:

- **COTS Parts**: Commercial off-the-shelf connectors, cables, devices
- **Macros**: Reusable Python scripts for common tasks
- **Titleblocks**: Standard drawing title blocks
- **Flagnotes**: Standardized note templates
- **Channel Types**: Standard signal/channel definitions

### What Makes a Good Library Part?

1. **Complete information**: Include all necessary attributes, drawings, and metadata
2. **Proper revision control**: Use revision history files to track changes
3. **Clear naming**: Use standard MPNs or descriptive names
4. **Documentation**: Include any special notes or usage instructions in attributes

### Contributing Process

1. Create your part in the appropriate library directory
2. Follow the standard library structure and naming conventions
3. Include revision history
4. Submit a pull request to the Harnice repository

If you are adding a **whole catalog** (every D-sub, every NEMA plug, every portable-cord type), do not hand-draw SKUs. Encode a part family. See [Building with AI](../ai_prompts.md). That page points at the part-family skill.

---

## :material-book-open-variant: Library Utilities Reference

For detailed information about library functions, see the [Library Utilities](../commands/_library_utils.md) documentation.

Key functions:
- `library_utils.pull()` - Import parts from libraries
- `library_utils.get_local_path()` - Look up local filesystem paths for library repos

---

## :material-lightbulb-on: Best Practices

1. **Always use libraries for reusable parts**: Don't recreate parts that already exist
2. **Pin revisions for production**: Use specific revisions for released projects
3. **Use latest for development**: Let Harnice use the latest revision during development
4. **Check library history**: Review what was imported using the library history file
5. **Contribute back**: Share your COTS parts with the community
6. **Organize with subpaths**: Use `lib_subpath` to organize related parts

---

## :material-help-circle: Troubleshooting

**Part not found?**
- Check that the library path is correctly configured in `fileio.path("repository locations")`
- Verify the MPN matches exactly (case-sensitive)
- Ensure the item type folder exists in the library

**Wrong revision imported?**
- Check what revisions are available in the library
- Verify your `lib_rev_used_here` parameter
- Review the import status messages

**Can't edit imported files?**
- Editable files are copied to the instance directory
- Files in `lib` are read-only by design
- Modify files in the instance directory, not the library_used folder
