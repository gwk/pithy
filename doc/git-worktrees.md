
# Git Bare Repositories with Worktrees

This approach to git creates an outer management dir that is not the checked out repo, a "bare" dir that is for git internal data,
and then multiple worktree directories that can have different branches checked out simultaneously.

Some reasons to work this way:
* We can leave work-in-progress in one worktree without committing or branching, and attend to a different branch.
* We can have agents work in different worktrees simultaneously.
* We can put sensitive material, e.g. secrets and data, in the outer dir where it cannot possibly get checked in by accident.

Many guides suggest using `.bare` for the bare dir, but I am using `_git_${PROJECT}`.
This makes it visible, puts it at the top of a directory listing, and is a unique name for 

```
git clone --bare git@github.com:org/repo.git _bare # Clone git data into _bare without setting it up as a usable repo root.
echo "gitdir: ./_bare" > .git # This allows us to issue git commands from the outer management directory

# Configure the remote manually and fetch.
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch origin

# Create a 'main' worktree.
 git worktree add main main
 cd main
```


# Local Package Sources for Repositories dependent on pithy

Repositories that depend locally on packages developed here need a way to specify which wokrtree they depend on. A dependent repo's tracked `pyproject.toml` is identical across all of its worktrees, so it cannot hardcode a path to one specific pithy worktree. The solution is a gitignored `deps/` directory in the dependent repo, holding symlinks to the packages it needs, set up per worktree.

Because packages in this repo source their siblings via `{ workspace = true }` (e.g. `pithy` sources `tolkien`), the dependent repo must declare a workspace of its own; uv refuses to resolve a `workspace = true` source from outside an actual workspace. For example:

```toml
[tool.uv.workspace]
members = ["deps/pithy", "deps/tolkien", "deps/utest"]

[tool.uv.sources]
pithy = { workspace = true }
tolkien = { workspace = true }
utest = { workspace = true }
```

The link script should default to pairing with the pithy worktree of the same name as the dependent repo's current
worktree, falling back to `main` if no matching branch exists; an environment variable lets you override the pairing
for one-off cases.

A minimal version, assuming the pithy and dependent worktrees are siblings:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Pair with the pithy worktree of the same name, falling back to 'main'.
worktree=$(basename "$PWD")
pithy=../../pithy/$worktree
[[ -d $pithy ]] || pithy=../../pithy/main

mkdir -p deps
ln -sfn "$pithy/pithy_" deps/pithy
ln -sfn "$pithy/utest_" deps/utest
```
