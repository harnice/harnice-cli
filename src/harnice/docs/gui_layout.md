# Harnice console GUI layout

## Architecture

Single-window editor with one layout for all file types. No structural difference between editing build instructions and editing network files—only the toolbar contents and the main content change.

## Structure

```
#app
├── #main (flex row)
│   ├── #left-panel (fixed width)
│   │   ├── #left-panel-header   [Build button, part number]  (always visible)
│   │   ├── #file-navigator     [Project files list]
│   │   └── #projects-section   [Projects list]
│   └── #right-area (flex column, fills rest)
│       ├── #top-toolbar        (one strip; contents depend on view mode)
│       └── #content-section   (one area; contents depend on view mode)
```

## View modes

- **build instructions** — Toolbar: save indicator and insert dropdowns. On a device, a configuration variables dropdown sits with those buttons and lists each configuration-setup field. Choosing one inserts `configuration["field_id"]` at the cursor. Content: textarea + output.
- **design in 3d** — One 3D viewport for the harness. Ribbon row 1: **Mode:** dropdown and **View:** overlay checkboxes. Row 2 (available-network mode): Select, Add Node, Add Segment as separate buttons. Delete and step size live in the properties panel. Chosen-network and STEP-macro modes are view only.
- **flattened network** — Toolbar: Fit View. Content: graph editor (flattened panel).
- **system list panes** (system project only) — Instances Lists, Devices, Circuits, Channel Map, Passthrough Map appear as project files. Selecting one shows the in-DOM system list view (table, filters, column dropdown, SSE, device/signals expand). Toolbar: search, clear filters, row count badge, sort dropdown; content: system list panel (no iframe).
- **subsystem symbols** (system project only) — Same symbol editor as a device, plus a tool that drops the current system block diagram (contents only, no trace overlays) as a scaled primitive. Bottom tabs are one per `subsystem_symbol` `run_macro` call in build instructions. Default pins come from unique ICD connectors; the macro also runs device signals-list checks against that ICD (pin mismatches warn, they do not fail the build). Because the ICD is written after build instructions, a second build is required after ICD changes. Toolbar: symbol ribbon. Content: symbol-editor iframe (`?mode=system`).
- **pdf drawings** (harness and system) — Page browser, sheet layout, titleblock properties, and master clones. Same editor for both project types. Toolbar: master chips and save indicator. Content: pdf-drawings iframe.
- **physical model** (device project only) — Shows `fileio.path("body")` (`body.step`). The solid is written in inches by a device-artifact macro (`build_rectangular_physical_model`, `build_rackmount_physical_model`, `build_rackmount_enclosure`, or `build_physical_model_from_step`): sketch, extrude, attach images, save. Face images live in `body_images/` and are linked from the STEP file. Click a face and paste a screenshot onto it. The paste warns that a later macro run replaces `body.step` and drops that link unless the macro's `images` argument names the file, or that macro is commented out. The PNG stays in `body_images/`. Two selected faces show the distance or the angle between them. Mate connectors are edited like harness 3D nodes: select one, drag the triad, and edit its id, pose, and source in the properties card that floats over the viewport. Every signals-list connector id needs a mate with that same id once `attributes.json` has `mate_connectors`. Content: physical-model panel (no iframe).
- **physical model** (system project only) — Every placed device that has `body.step` is posed in the system and written into `assembly.step`. Poses, fasten mates, and grounded devices are stored in `physical.json` (`fileio.path("physical assembly")`). Mode **Place**: the ribbon has **Fix** and **Mate**. Fix grounds the selected devices: their pose stays put, and dragging their arrows does nothing. Click adds a device or mate to the selection. Shift-click removes it. Pick one mate connector on each of two devices and Mate; the card chooses which device moves onto the other. Face to face flips the moving connector 180° about its X axis. A device can be held by one mate. A grounded device cannot be the one that moves. Mode **Route** edits `available_network.json` in the same viewport. The Context menu shows a STEP file from `contexts/`. Content: system-physical panel (no iframe).
- **cable layout** (cable project only) — Read-only view of the nesting in `fileio.path("attributes")`, in three panes at once: cross section (2D circle packing) on the left, isometric cut-away (the same packing extruded along the cable with each layer cut back) in the middle, and the containment tree with each member's properties on the right. No toolbar. Drag the dividers to resize the panes. Content: cable layout panel (no iframe). Cable has no build instructions file, so this view also shows the Build output.

Mode is determined by the selected item in Project files (`selectedFile`). Toolbar and content are updated from a single place when the selection changes.

## Data flow

1. **EditorShell** (or equivalent) holds: `selectedFile`, `editorFiles`, `productType`. It is the single source of truth for "what is shown."
2. **Toolbar** is rendered from a spec keyed by mode (e.g. `TOOLBAR_SPEC[selectedFile]`). Build-instructions mode uses native controls (save, dropdowns); network modes use buttons that either call into the graph API (postMessage to iframe) or, in a future in-process refactor, call a graph module directly.
3. **Content** switches between the build-instructions editor (textarea + output) and the graph editor. The graph editor currently runs in an iframe and receives actions via postMessage; the parent never duplicates toolbar buttons inside the iframe (they live only in the shell toolbar).

## Files

- **harnice_console.html** — Single entry point for Harnice console. Markup is the shell (left panel, right area, one toolbar, one content). Script drives toolbar and content from view state.
- **system_physical_view.js** — System physical model. Loads every placed device body, poses them from `physical.json`, and fastens mate connectors. Mounts inside #system-physical-panel. Exposes SystemPhysicalView.load(), reload(), hide().
- **console_server.py** — Serves the editor, /api/* for code and run; /api/available, /api/chosen_list, /api/design_3d/models, /api/design_3d/step, etc. for the Design in 3D page; /system-list-view.js and /api/files, /api/sse, etc. for system list panes (system project). Uses **system_viewer_core** for tab list and file watcher; uses **system_viewer_server** for system API handlers.
- **graph_editor.html** — Loaded in the content area (iframe) when the view is a network file. When embedded it hides its own tabs and main toolbar; the shell toolbar is the only one. It handles postMessage for setTool and fitView.
- **system_list_view.js** — In-DOM system list view: table, viewer headers (instances/channel/passthrough/circuits), column filter/sort dropdown, SSE, device row → signals list expand, channel-type display. Loaded by the Harnice console; mounts inside #system-list-panel when a system list pane is selected. Exposes SystemListView.loadPane(), setSearch(), clearFilters(), setSort(), getState(), setOnStateChange().
- **cable_layout_view.js** — In-DOM cable layout view: packs each member of the attributes JSON hierarchy into its container as a circle, paints jacket/insulation color and stripes from `properties` and `appearance`, and renders the containment tree. A member with nothing to draw it from is a boundary circle with no fill, and is omitted from the isometric. Lays out the three panes with drag splitters, and owns the packing, the paint spec, the tree and the selection for both drawings. Neither drawing pans or zooms; each frames itself to its pane. Mounts inside #cable-layout-panel; reads /api/cable_layout. Exposes CableLayoutView.load(), reload(), fit() (frames the cross section).
- **cable_3d_view.js** — Isometric cut-away pane for the cable layout view, built with the three.js already loaded for the graph editor. Takes the packed tree and per-member paint spec from cable_layout_view.js and extrudes it along the cable: members run straight, each layer is cut one tier further back than the one outside it, and members fan out clear of each other, insulated conductors ending stripped, trimmed into a staircase with the near ones shortest. Orthographic camera fixed at the isometric angle with no orbit, zoom or pan — it reframes itself to the pane on resize — and unlit flat materials, so a member is painted exactly as the cross section paints it and cut faces carry the cross section as a texture. Click picking only; renders on demand. Exposes Cable3DView.mount(host, opts), setSelected(), dispose().
- **system_viewer_core.py** — Shared data and logic for system lists: tab order/labels, get_all_files(), get_tab_list(), file watcher, SSE queues, signals-list content. Used by console_server and system_viewer_server handlers.
- **system_viewer_server.py** — Thin HTTP layer: serve_files, serve_sse, serve_channel_type_*, serve_signals_list. Used by console_server for system project API routes (/api/files, /api/sse, etc.).

## Launch

Open Harnice. Graph and system list panes are view modes inside the window; there are no separate standalone graph or system viewer windows.

## Future: graph in process

To remove the iframe, the graph editor would be initialized into a mount node (e.g. `#graph-editor-root`) in the same document: load graph HTML fragment + graph JS, then call `HarniceGraphEditor.init(mount)`. The shell toolbar would call `HarniceGraphEditor.setTool()` / `fitView()` / `switchTab()` directly. That requires extracting the graph editor script to a root-scoped or mount-scoped module (e.g. `document.getElementById('graph-main')` with the fragment using `id="graph-main"`).
