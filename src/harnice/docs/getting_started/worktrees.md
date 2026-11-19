# Worktrees

A worktree lets one project sit on its own git branch while every other project in the repository stays where it is.

Without worktrees, a repository has one folder and one checked-out branch. Switching branches for one harness switches every project in that folder at once. A worktree is another folder on your computer that is part of the same repository .git database, but is entirely independent from the main folder tree you usually interact with. It is checked out on a different branch, holding only the projects you move into it.

## Main folder and worktrees

**Main folder** is your repository folder itself, on whatever branch it has checked out. It never means the `main` branch.

**A branch worktree** holds only the projects you moved onto that branch. There is one per branch, and projects on the same branch share it. Harnice keeps worktrees in its app-data folder, out of your repository and out of any synced folder:

- macOS: `~/Library/Application Support/Harnice/worktrees/<repository>/<branch>/`
- Windows: `%APPDATA%\Harnice\worktrees\<repository>\<branch>\`

## When to use one

Use a worktree when you want to change one project on a branch while it keeps **referencing other projects on other branches**. A harness's source system and library parts are always read from the main folder, so a harness in a worktree builds against whatever branch the main folder has checked out.

If a build needs a referenced project's branch, check that branch out in the main folder instead: delete its worktree and choose **Yes, and check out the branch in the main folder** (below). When a build reads a system that is also checked out in a worktree, the build log says so:

```
harnice: S100 rev1 is also in worktree fix-connectors; this build used the main folder's copy (branch main). Delete the fix-connectors worktree and check out fix-connectors in the main folder to build against it.
```

## Opening or starting a project in a worktree

Right-click **Open project…** or **New project…** in the Projects panel:

- **Open project in a new worktree…** asks for a branch name first. Harnice makes a worktree for that branch: a new branch from the main folder's branch, or the branch itself when it already exists. The folder picker then opens at that worktree's root, with every folder checked out so you can pick any project. Once you pick one, the worktree keeps only that project, and it opens from there. Cancel the picker and the new worktree is removed, along with the branch if Harnice made it. A branch that already has a worktree is used as it is, and the project you pick joins the projects already in it.
- **New project in a new worktree…** opens the New project form with a branch name (it starts as the part number). Harnice makes that branch from the main folder's branch, puts a worktree for it in app data, and creates the project there. The main folder is not changed. If the project cannot be created, the new worktree and branch are removed again.

Below those, each menu lists the branch worktrees that already exist in the open project's repository:

- **Open project in the `<branch>` worktree…** opens the project you pick and moves it into that worktree, next to the projects already there. A project from a different repository stays open from its folder.
- **New project in the `<branch>` worktree…** opens the New project form without a branch name. Pick the parent folder in that worktree or in the main folder. Harnice adds the new project's folder to that worktree and creates the project there, on that branch. The main folder is not changed. If the project cannot be created, its folder is taken back out of the worktree, which stays as it was.

The folder picker for **Open project…** and **New project…** starts in the library root of the last project you selected, in the main folder. After an **…in the `<branch>` worktree…** item, it starts in that worktree's root folder instead.

## Deleting a worktree

**Delete worktree** first checks for uncommitted changes. If there are any, it lists them and offers **Commit…**, which opens the commit box for this project. Nothing is deleted.

Otherwise it asks:

| Answer | What happens |
| --- | --- |
| No | Nothing. |
| Yes | Deletes the worktree folder. The branch is kept, with all its commits, so you can check it out again later. The worktree's projects switch to the main folder, on whatever branch it has. |
| Yes, and check out the branch in the main folder | Deletes the worktree and checks its branch out in the main folder, so its projects carry on there on the same branch. Every other project in the main folder moves to that branch too. Nothing needs to be pushed. |

## What harnice will not do

Git checks a branch out in one place at a time, and harnice keeps your work safe, so some actions are refused. Each refusal prints git's own message in the command line, followed by a `harnice:` line saying what to do. When the refusal is about a branch already in use, a popup also offers the fix.

| You tried | What happens |
| --- | --- |
| Check out, in the main folder, a branch a worktree is using | Refused. A popup names the projects in that worktree and offers to delete that worktree and check the branch out here, or to move this project into it. |
| Move a project to the branch the main folder has | Refused. A popup offers **Switch to Main folder**, or to check out the repository's default branch (e.g. `main`) in the main folder and put this project in a worktree for its branch. The second needs the project committed; if the worktree cannot be made, the main folder goes back to the branch it had. Other projects in the main folder move to the default branch. |
| Move a project out of a worktree with uncommitted changes | Refused, listing the files. Commit or stash first. |
| Delete a worktree with uncommitted changes | Refused, listing the files, with an offer to commit. |
| Check a branch out in the main folder while the main folder has changes it would overwrite | Git refuses, and the worktree is left exactly as it was. |

A worktree folder deleted outside harnice is forgotten the next time the panel loads, and its projects fall back to the main folder.
