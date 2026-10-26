# Building with AI

An agent clones the public command-line repository, [harnice-cli](https://github.com/harnice/harnice-cli), and follows a skill there. A chatbot pastes one of the prompts below and reads the skill from the raw URL in that prompt.

File formats and project layout are in this documentation. `harnice --docs` prints the folder. The same pages are at [harnice.io](https://harnice.io/).

---

## Harnice skill for agents

Open your project in the agent (Claude Code, Cursor, and the rest). Paste this. It shows the agent where the skills are, and tells it to ask what to do next before it follows one.

<details class="prompt" markdown="1">
<summary>Harnice</summary>

````markdown
# Harnice

The skills are in the Harnice command-line repository. They are not in this message.

https://github.com/harnice/harnice-cli

Clone that repository. Read the description at the top of each `skills/*/SKILL.md`. Ask me what to do next: one line per skill, then wait. Follow the skill I name. Documentation is in that clone at `src/harnice/docs/`. Start with `index.md`.
````

</details>

---

## Prompts for chatbots

Paste one of these into a chatbot. The chatbot opens the raw URL in the prompt and reads the whole file.

1. [Device signals list](#device-signals-list-buildpy) — turn any pinout, ICD, or datasheet into device `build.py`
2. [Part family](#part-family-library-skus) — encode a catalog into library SKUs
3. [System build instructions](#system-build-instructions) — write or edit a system `build.py`
4. [Harness build instructions](#harness-build-instructions) — write or edit a harness `build.py`, including layout
5. [CAD](#cad) — write a device body, or arrange those bodies in a system

### Device signals list (`build.py`)

Attach the pinout, ICD, datasheet, spreadsheet, screenshot, schematic note, vendor table, or netlist, or say where that file is. Name the channel types if you already know them. Attach `channel_types.tsv` and give the library URL, for example: `Channel types are the attached TSV. lib_repo is https://github.com/my-org/my-library.` That URL is the key in `repository_locations.csv`. The TSV does not contain it. At build time Harnice reads the channel types from the library path for that URL.

The engineering decisions stay yours: which channel type to use, whether a ground is chassis, what a connector plugs into. The skill tells the model to ask, with the context in front of you, and to wait for your answer.

<details class="prompt" markdown="1">
<summary>Harnice device signals list</summary>

````markdown
# Harnice device signals list

The procedure is a skill in the Harnice command-line repository. It is not in this message.

The pinout, ICD, datasheet, spreadsheet, screenshot, or a path to that file is already in this chat, or it is already in the device revision folder. If it is not, say so and stop. Do not read the skill until it is.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/device-signals-list/SKILL.md`. The documentation is in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open this URL, read the entire file, and follow it:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/device-signals-list/SKILL.md

If you cannot read the whole file, say so and ask me to paste it. Do not write `build.py` until you have read the skill.
````

</details>

### Part family (library SKUs)

Attach the how-to-order PDF (and a drawing or photo if overall length and max diameter are not tabulated). Add one sentence of intent, for example: `Family is Neutrik powerCON TRUE1 chassis connectors. Write into neutrik/.`

Review the catalog count before letting it emit thousands of folders. Run the generator with `--svg-only` first.

<details class="prompt" markdown="1">
<summary>Harnice part family</summary>

````markdown
# Harnice part family

The procedure is a skill in the Harnice command-line repository. It is not in this message.

The how-to-order page, drawing, photo, or a path to that file is already in this chat, or it is already in the library repository. If it is not, say so and stop. Do not read the skill until it is.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/part-family/SKILL.md`. The documentation is in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open this URL, read the entire file, and follow it:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/part-family/SKILL.md

If you cannot read the whole file, say so and ask me to paste it. Do not write the part family until you have read the skill.
````

</details>

### System build instructions

Paste this when the revision is a system. A harness uses the next prompt. A device pinout uses the device signals list prompt. A catalog uses the part-family prompt. Name the revision and what the script should do.

<details class="prompt" markdown="1">
<summary>Harnice system build instructions</summary>

````markdown
# Harnice system build instructions

The procedure is a skill in the Harnice command-line repository. It is not in this message.

This message says the revision is a system, and what the script should do, or that revision is already open. If it does not, say so and stop. Do not read the skill until it does. A harness is a different skill. A device signals list is a different skill. A part family is a different skill.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/system/SKILL.md`. The calls and how to use them are in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open this URL, read the entire file, and follow the skill:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/system/SKILL.md

If you cannot read a whole file, say so and ask me to paste it. Do not write `build.py` until you have read the skill.
````

</details>

### Harness build instructions

Paste this when the revision is a harness. A system uses the prompt above. Name the revision and what the script should do. A node move and a backshell clock are this skill.

<details class="prompt" markdown="1">
<summary>Harnice harness build instructions</summary>

````markdown
# Harnice harness build instructions

The procedure is a skill in the Harnice command-line repository. It is not in this message.

This message says the revision is a harness, and what the script should do, or that revision is already open. If it does not, say so and stop. Do not read the skill until it does. A system is a different skill. A device signals list is a different skill. A part family is a different skill.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/harness/SKILL.md`. The calls and how to use them are in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open this URL, read the entire file, and follow the skill:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/harness/SKILL.md

If you cannot read a whole file, say so and ask me to paste it. Do not write `build.py` until you have read the skill.
````

</details>

### CAD

Paste this when the device needs a body, or when devices in a system need to be posed and fastened. Name the shape and the dimensions, or name which connector fastens to which. A pinout uses the device signals list prompt. A system `build.py` uses the system prompt.

<details class="prompt" markdown="1">
<summary>Harnice CAD</summary>

````markdown
# Harnice CAD

The procedure is a skill in the Harnice command-line repository. It is not in this message.

This message says the device body to write, or which devices to fasten, or that revision is already open. If it does not, say so and stop. Do not read the skill until it does. A device signals list is a different skill. A system build.py is a different skill.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/cad/SKILL.md`. The documentation is in the same clone at `src/harnice/docs/cad.md`.

If you cannot clone the repository, open this URL, read the entire file, and follow it:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/cad/SKILL.md

If you cannot read the whole file, say so and ask me to paste it. Do not write a body until you have read the skill.
````

</details>
