
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

Repositories that depend locally on packages developed here need a way to specify which worktree they depend on. A dependent repo's tracked `pyproject.toml` is identical across all of its worktrees, so it cannot hardcode a path to one specific pithy worktree. The solution is a gitignored `deps/` directory in the dependent repo, holding one symlink per dependency repo, each pointing at a worktree root of that repo. Package paths then reach through the link, e.g. `deps/pithy/pithy_`.

Linking whole worktree roots rather than individual packages respects the intended synchrony between packages in a single repo and keeps the link script generic.

Because packages in this repo source their siblings via `{ workspace = true }` (e.g. `pithy` sources `tolkien`), the dependent repo must declare a workspace of its own; uv refuses to resolve a `workspace = true` source from outside an actual workspace. For example:

```toml
[tool.uv.workspace]
members = ["deps/pithy/pithy_", "deps/pithy/tolkien_", "deps/pithy/utest_"]

[tool.uv.sources]
pithy = { workspace = true }
tolkien = { workspace = true }
utest = { workspace = true }
```

Each dependent repo carries a `sh/deps.sh` that takes a repo name and branch, validates them, and sets the symlink. A `deps` justfile rule sets all of the repo's dependency symlinks to the same branch, defaulting to `main`; a `develop` rule runs `deps` and then `uv sync`. See `sh/deps.sh` in the inish repo for the reference implementation.

A minimal version, assuming the dependency and dependent repo dirs are siblings:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo=$1
branch=$2
target=../../$repo/$branch
[[ -d $target ]] || { echo "error: no $repo worktree for branch '$branch'." 1>&2; exit 1; }

mkdir -p deps
ln -sfn "$(cd "$target" && pwd -P)" "deps/$repo"
```


# Repos That Are Both Dependents and Dependencies

uv does not support nested workspaces: a workspace member may not itself declare a `[tool.uv.workspace]` table. Consequently, a repo that places its package pyproject at the repo root and declares its workspace there cannot be consumed as a workspace member by a repo that depends on it. Such a repo can instead be consumed as a path source, e.g. `b = { path = "deps/b", editable = true }`, but uv ignores the `tool.uv.sources` of a path dependency that is not a workspace member, so any local dependency of the path dep that the consuming repo does not also pin itself silently resolves from the registry instead.

Therefore, any repo that other repos consume must use the virtual-root layout of this repo: packages live in `*_` subdirectories, and the root `pyproject.toml` declares only the workspace not a package. Dependent repos then list the `*_` package dirs as members, e.g. `deps/b/b_`. Member sources are honored, so a member's `{ workspace = true }` sources resolve within the consuming repo's workspace, and a missing member is a hard error at lock time rather than a silent registry fallback. Only application repos that nothing else consumes should place their package at the repo root.
