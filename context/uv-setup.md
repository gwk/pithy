# Pithy uv Setup

Pithy is a uv virtual workspace. Its root `pyproject.toml` lists the package directories, such as `pithy_`, `tolkien_`, and `utest_`, as workspace members. Package dependencies name other pithy packages normally in `[project.dependencies]`, then map them to the local workspace in `[tool.uv.sources]`:

```toml
[project]
dependencies = [
  'pithy',
]

[tool.uv.sources]
pithy = { workspace = true }
```

The root `uv.lock` records the complete version state of the workspace. AS package config changes, `uv run` and `uv sync` will update uv.lock; those generated changes should be committed together with whatever triggerd them. The commands in the justfile should use `uv` uniformly to keep everything synchronized.

to create or update `.venv`, and commit changes to `uv.lock`. Use `just check-uv-lock` and `just update-uv-lock` when dependency metadata changes.

# Dependent Repository Setup

Until pithy has versioned releases, dependent repositories use a local pithy checkout as an external uv workspace. Use this layout:

```text
dependent-repo/
  deps/pithy -> local pithy worktree
  pyproject.toml
  uv.lock
```

Ignore `deps/` in git. Provide a reproducible command that creates the link to the intended local worktree before any uv command. This makes pithy source changes immediately visible through uv's editable development installs, which is required for hot reloading.

Declare every directly used pithy package by its distribution name. Map each one to the external workspace root:

```toml
[project]
dependencies = [
  'pithy',
]

[dependency-groups]
dev = [
  'utest',
]

[tool.uv.sources]
pithy = { workspace = 'deps/pithy' }
utest = { workspace = 'deps/pithy' }
```

The path is relative to the dependent repository root. Do not list transitive pithy packages unless the repository imports or invokes them directly. After creating the link, run `uv lock` and `uv sync`. Commit `pyproject.toml` and `uv.lock`, but not the link.

# Developer Tools

A developer-only package needs no additional pithy pin. Its setup consists of the ignored `deps/pithy` link, external workspace sources, and the committed lockfile. A typical development recipe creates the link and runs `uv sync`. Checks should include `uv lock --check`.

This arrangement intentionally follows whichever pithy worktree the developer linked. Changing that worktree can change the pithy code without changing `uv.lock`.

# Deployed Web Apps

A deployed app must separately pin both kinds of input:

* `uv.lock` pins the complete resolved package set and exact third-party versions.
* A committed revision file, such as `pithy.rev`, pins the pithy git commit. A local workspace entry in `uv.lock` records a path, not the checkout's commit.

The development setup remains the same so edits in the linked pithy worktree are editable and visible to reloaders. Before updating the revision file, verify that the selected pithy commit is available from the remote used by the server.

A deployment must perform these steps in order:

1. Check out the app revision.
2. Fetch pithy and check it out at the exact revision recorded by the app.
3. Recreate `deps/pithy` so it points to that checkout.
4. Run `uv sync --locked` with the app's intended deployment groups. Use `--no-editable` when service users cannot read the source checkout or when deployment should run installed artifacts.

`--locked` is essential: the server must fail instead of resolving a different environment. `uv sync` also removes packages outside the selected locked groups, so do not depend on ad hoc installs.

Local workspace packages often retain the same package version while their source changes. A deployment that reuses an environment should therefore force-reinstall each local package. If build isolation is disabled for local packages, include the build backend, currently `flit-core`, in a selected deployment dependency group, let uv install the locked backend first, and pass `--no-build-isolation-package` for each local package. A project may choose to derive these per-package arguments from the editable entries in `uv export --locked` so the list stays aligned with the lockfile.

For a shared system interpreter, also set an explicit `UV_PROJECT_ENVIRONMENT`, prevent uv from downloading Python, compile bytecode during installation, and verify that installed files are readable by service users. These are server layout requirements, not requirements for ordinary virtual environments.

# Future Versioned Releases

Once pithy publishes versioned releases, ordinary package deployments should depend on released versions and let `uv.lock` pin them. At that point they will not need an external pithy workspace or a separate revision file in deployment. The local workspace mapping can remain as an explicit development override if simultaneous pithy development is still needed.
