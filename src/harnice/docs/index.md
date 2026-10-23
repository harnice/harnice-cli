# Welcome to Harnice

**Harnice** is a Python-based, electrical system CAD package.

It designs harnesses for you... and does so much more... *nicely*!


!!! note "Beta"
    **Harnice is in beta.** File formats, build instructions, and project layout can still change. Backwards compatibility with your existing files across updates is not yet assured. It's super close, but I can't guarantee it yet.

 --- 
## :octicons-rocket-16: Links

**Buy a license:** [Purchase Harnice](https://buy.stripe.com/dRmaER6AK2Eh5hs2KFb7y00) — **$50/seat/month** (subscription; set quantity at checkout for multiple seats)

Download Harnice: [Mac](https://github.com/harnice/harnice-app-releases/releases/latest/download/Harnice-macOS.dmg) · [Windows](https://github.com/harnice/harnice-app-releases/releases/latest/download/Harnice-windows.zip)

After purchase, check your email for a license key. Open Harnice and paste it on the activation screen (internet needed once per machine). Each seat covers one activated machine. See [Installation](getting_started/installation.md#offline-use) for how long a machine can stay offline between license refreshes.

**Harnice is a fully offline app.** Your files stay on your machine; use **git** to version them however you like. Prove it: build projects in **airplane mode**. The only routine need for internet is an occasional [license check-in](getting_started/installation.md#offline-use) (about every few weeks; details on the Installation page).

Submit bugs, feature requests: [`new issue`](https://github.com/harnice/Harnice/issues/new)

Send me an email: [`harnice.io@gmail.com`](mailto:harnice.io@gmail.com)


---
## :material-elevator-up: What's the elevator pitch?

Let's face it: designing harnessing sucks. Managing how your devices talk to each other in one software, and building stuff against that in another is terrible. Calculating voltage drops, naming stuff, keeping track of device interface configurations, software input lists, is almost always done manually, in error-prone, expensive, clunky, contradictory, time-wasting ways. 

==...*not anymore!!!*==

I developed Harnice because **it's time for something new.** We, the people, deserve better. Harnice is my attempt to consolidate all electrical-system related design tasks into one comprehensive, full-featured tool. 

With Harnice, you can consolidate all your electrical design problems into consistent, infinitely configurable, reusable data structures, where you can define what you need. From there, the software can help you derive any imaginable output directly from your design content.

---

## :material-file-question-outline: How does it work?

Harnice was developed with one goal in mind: 

==***delete redundant sources of truth** in your electrical system definition.*==

As a system designer, your time is most valuably spent thinking about exactly what you want, not how to actually implement it. 

If your electrical system can be implemented by simple logic statements, Harnice can help you record those design intents as rules, then compile them against libraries of devices and COTS items that you're trying to use, and give you ==**one fully compiled solution**== to your system.

---

## :fontawesome-regular-pen-to-square: What's the workflow?
1. **Define your devices once.** Pins, connectors, channels, parts, and behavior all live in reusable libraries.

1. **Draw what connects.** Turn system intent into a clear, editable block diagram.

    ![Editing a harness block diagram in Harnice](index_images/Xnip2026-09-24_18-45-25.png)

1. **Write the rules.** Use straightforward Python for checks, part selection, channel mapping, naming, colors, and anything unique to your process.

1. **Click Build.** Harnice compiles the whole design—and every output—from the same source of truth.

---

## :fontawesome-solid-warning: What do you get?
- **Production-ready drawing packages.** Multi-page PDFs—with tables, details, and title blocks—generated directly from the design.

![A generated harness drawing open in Harnice](index_images/Xnip2026-09-24_19-54-52.png)

- **A live map of the whole system.** Trace channels through devices, connectors, and passthroughs, then inspect the data behind every connection.

![Interactive system-wide channel map and connection data](index_images/Xnip2026-09-24_18-43-26.png)

- **Real routing, in context.** Lay out harnesses around your hardware in 3D, with lengths calculated from the route.

![A harness routed around a device in the 3D layout](index_images/Xnip2026-09-24_19-49-48.png)

- **Clean flat layouts.** Arrange branches and nodes for the drawing without losing the underlying design data.

![Editing the same harness as a flat 2D layout](index_images/Xnip2026-09-24_19-52-40.png)

- **Complete, consistent data.** Bills of materials, cable lengths, instance lists, netlists, mappings, and more—all compiled together.
- **Coming next:** full-system behavior simulation and device-provisioning reports.

---

## :material-import: Can it do what I need?
Probably. Harnice gives you Python at the center of the build, so your own rules, checks, naming, calculations, and outputs are first-class—not workarounds.

![Writing harness build rules in Harnice's built-in Python editor](index_images/Xnip2026-09-24_19-44-00.png)

Need something bigger? Build a **[Macro](project_types/_macro.md)**: a revision-controlled mini-project with its own files and history. Use one that ships with Harnice or write exactly what your workflow needs.

---

## :octicons-x-circle-16: What doesn't Harnice do?
- Harnice is not intended to **make engineering decisions** for you. This is a platform that lets you use your brain to focus on the hard stuff, while the computers produce a determinite, predictable output of the rules you've defined. 

- Harnice is currenlty set up to link as-intended systems to as-designed. It does not yet have the ability to track as-built. 

- Harnice does not read your mind. If you are receiving results that you don't expect (unless it's a bug), you may need to rethink how you are communicating or organizing your thought process. **This is a feature!** Complete, explicit definition makes your designs easier to understand by both humans and machines alike. 

- Harnice does not invent catalog parts for you. Libraries are still the barrier to entry. The way through is a **part family**: Python that encodes a how-to-order table and emits every legal SKU. The [Building with AI](ai_prompts.md) page points at the part-family skill in the command-line repository.

- Harnice does not type your device pinout for you. The same [Building with AI](ai_prompts.md) page points at the device signals-list skill. Give it an ICD, datasheet, or spreadsheet. 