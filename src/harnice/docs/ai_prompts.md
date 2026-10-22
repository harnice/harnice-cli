# AI Prompts

Paste one of these into an agent or a chatbot. The procedure is a skill in the public command-line repository, [harnice-cli](https://github.com/harnice/harnice-cli). An agent clones that repository and follows the skill. A chatbot opens the raw URL in the prompt and reads the whole file.

1. [Device signals list](#device-signals-list-buildpy) — turn any pinout, ICD, or datasheet into device `build.py`
2. [Part family](#part-family-library-skus) — encode a catalog into library SKUs
3. [System build instructions](#system-build-instructions) — write or edit a system `build.py`
4. [Harness build instructions](#harness-build-instructions) — write or edit a harness `build.py`

File formats and project layout are in this documentation. `harnice --docs` prints the folder. The same pages are at [harnice.io](https://harnice.io/).

---

## Device signals list (`build.py`)

Open your project's repository in the agent (Claude Code, Cursor, and the rest) so it can see your project, `channel_types.tsv`, and other projects. Copy the supporting docs into the revision folder, or attach them in the chat: a pinout, an ICD, a spreadsheet, a screenshot, a schematic note, a vendor table, or a netlist.

Paste the prompt below in the same message. Name the channel types if you already know them. Attach `channel_types.tsv` and give the library URL, for example: `Channel types are the attached TSV. lib_repo is https://github.com/my-org/my-library.` That URL is the key in `repository_locations.csv`. The TSV does not contain it. At build time Harnice reads the channel types from the library path for that URL.

The engineering decisions stay yours: which channel type to use, whether a ground is chassis, what a connector plugs into. The skill tells the model to ask, with the context in front of you, and to wait for your answer.

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

---

## Part family (library SKUs)

Paste the prompt below into a new chat in the **library** repo. Attach the how-to-order PDF (and a drawing or photo if overall length and max diameter are not tabulated). Add one sentence of intent, for example: `Family is Neutrik powerCON TRUE1 chassis connectors. Write into neutrik/.`

Review the catalog count before letting it emit thousands of folders. Run the generator with `--svg-only` first.

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

---

## System build instructions

Paste this when the revision is a system. A harness uses the next prompt. A device pinout uses the device signals list prompt. A catalog uses the part-family prompt. Open the system revision in the agent, or name it and what the script should do.

````markdown
# Harnice system build instructions

The procedure is a skill in the Harnice command-line repository. It is not in this message.

This message says the revision is a system, and what the script should do, or that revision is already open. If it does not, say so and stop. Do not read the skill until it does. A harness is a different skill. A device signals list is a different skill. A part family is a different skill.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/system/SKILL.md`. The functions it may call are `skills/build-api/reference.md`. The documentation is in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open these URLs, read each entire file, and follow the skill:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/system/SKILL.md

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/build-api/reference.md

If you cannot read a whole file, say so and ask me to paste it. Do not write `build.py` until you have read the skill.
````

---

## Harness build instructions

Paste this when the revision is a harness. A system uses the prompt above. Open the harness revision in the agent, or name it and what the script should do.

````markdown
# Harnice harness build instructions

The procedure is a skill in the Harnice command-line repository. It is not in this message.

This message says the revision is a harness, and what the script should do, or that revision is already open. If it does not, say so and stop. Do not read the skill until it does. A system is a different skill. A device signals list is a different skill. A part family is a different skill.

https://github.com/harnice/harnice-cli

Clone that repository. Follow `skills/harness/SKILL.md`. The functions it may call are `skills/build-api/reference.md`. The documentation is in the same clone at `src/harnice/docs/`. Start with `index.md`.

If you cannot clone the repository, open these URLs, read each entire file, and follow the skill:

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/harness/SKILL.md

https://raw.githubusercontent.com/harnice/harnice-cli/main/skills/build-api/reference.md

If you cannot read a whole file, say so and ask me to paste it. Do not write `build.py` until you have read the skill.
````
