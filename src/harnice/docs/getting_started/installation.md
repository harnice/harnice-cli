# Installation

!!! warning "Beta"
    Harnice is currently in **beta**. We do **not** guarantee backwards compatibility with your project files, libraries, or build instructions when you update. Prefer **git** (or another VCS) so you can roll back if a release changes formats.

## :material-key: Buy and activate

Harnice is sold as a **subscription at $50 per seat per month**. One seat = one activated machine. Increase quantity at checkout for more seats. If you believe you have a special case for a pricing exception, **[send me an email](mailto:kenyon@harnice.io)**. I would love to hear about your project and help the world never design harnesses ever again, especially if you're not using the app to make money.

1. **[Buy a license](https://buy.stripe.com/dRmaER6AK2Eh5hs2KFb7y00)** (Stripe Checkout).
2. Check the email you used at checkout for your **license key** (sent by Keyforge after payment).
3. Download Harnice (links below), install, and open it.
4. Paste the key on the activation screen. Activation needs the internet once; afterward this machine can work offline for a long stretch (see below).

To free a seat for another computer, open the gear menu (bottom right) → **Release seat…**.

### Offline use

**Harnice is a fully offline app.** Your projects live as ordinary files on disk. It is intended to be used with **git** (or any VCS you prefer): you version-control your own design files in your own way — Harnice does not host your data or require a cloud workspace.

Prove it to yourself: turn on **airplane mode** and build a project. Design, edit, and compile still work.

The **only** routine need for internet is an occasional **license check-in**. After activation (or a successful refresh), Harnice verifies a signed license token on the machine and does **not** phone home on every launch:

| Period | Behavior |
| --- | --- |
| About **30 days** after the last successful activate/refresh | Fully offline; no network required |
| Last **~3 days** of that window | If the machine is online, Harnice quietly refreshes the token and resets the clock |
| **14 more days** after the token expires | Offline **grace** — still allowed if you have not reconnected yet |
| After that (~**44 days** total with no refresh) | Needs internet to refresh or re-activate |

Coming online every few weeks is enough to keep the license current indefinitely. You also need the internet for first activation, seat release, and after a cancelled or unpaid subscription once the cached token and grace period end.

---

## :material-download: Download

Download Harnice for [Mac](https://github.com/harnice/harnice-app-releases/releases/latest/download/Harnice-macOS.dmg) or [Windows](https://github.com/harnice/harnice-app-releases/releases/latest/download/Harnice-windows.zip). On a Mac, open the DMG and drag Harnice into Applications. On Windows, unzip and run `Harnice.exe` (keep the unzipped folder together).

Open Harnice. On first launch it creates the files it needs on this computer (your name and library locations).

---

## :material-folder-open: Open or create a project

Use **File → Open Project…** or **File → New Project…** (same as the buttons in the console), or click those buttons in the left panel. **Window → New Window** opens another Harnice window with its own Python process so you can work on a different project at the same time.

---

## :octicons-arrow-switch-16: Configure Library Paths

Harnice finds libraries through **Library locations** (in the left panel). Each row maps a **repository URL** (the `lib_repo` you write in build instructions) to the **local path** of that library on your machine:

```csv
repo_url,local_path
https://github.com/harnice/harnice-aerospace-library,/path/to/harnice-aerospace-library
https://github.com/harnice/harnice-av-library,/path/to/harnice-av-library
```

- `local_path` may use `~` (it is expanded)
- Add one row for every library you use. Connector choosers (D38999, Mighty Mouse, D-sub) look up `https://github.com/harnice/harnice-aerospace-library` with `library_utils.get_local_path()`
- The URL must match exactly what you pass as `lib_repo` (lookup is case-insensitive)

If `fileio.path("repository locations")` is missing the first time you run Harnice, it is created for you.

See [Libraries](libraries.md) for more.
