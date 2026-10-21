# cs-plugin

Pin a project's Claude Code plugins in one `plugins.toml`, like `pyproject.toml`,
from any number of plugin repos, and install exactly that.

Two projects on one machine can use different releases of the same plugin, and a
teammate's whole setup after cloning is one command.

```sh
uvx cs-plugin list                           # what is available
uvx cs-plugin add cap-tools remote-h5ad-obs  # pin the newest releases
uvx cs-plugin sync                           # install them in this project
```

Needs [uv](https://docs.astral.sh/uv/) (or `pipx run cs-plugin`), `git`, and
Claude Code for `sync`. `uv tool install cs-plugin` puts `cs-plugin` on your PATH
so you can drop the `uvx`.

## See what is available

```sh
cs-plugin list           # every plugin in the source repos, and its newest release
cs-plugin list -l        # with descriptions
cs-plugin sources        # which repos those are
```

Plugins are read live from each source repo's own
`.claude-plugin/marketplace.json`, and releases from its `<plugin>--v<version>`
tags (what `claude plugin tag` writes). A release anywhere shows up at once.

## Set up a project

From the project's root:

```sh
cs-plugin add cap-tools remote-h5ad-obs     # newest releases
cs-plugin add onto-mapping@0.5.0            # or a specific one
cs-plugin sync                              # install them
git add plugins.toml .claude .gitignore && git commit -m "Pin Claude Code plugins"
```

`plugins.toml` is the file you read and edit:

```toml
[project]
name = "cap-report-hacking"

[plugins]
cap-tools = "0.4.1"
remote-h5ad-obs = "0.3.0"
```

A plugin with no release tags can be pinned to a commit instead, and a plugin
in no source repo by its repo:

```toml
some-plugin = { sha = "22a10275db2768304021549cd8300bc05a704b42" }
other = { repo = "someone/their-plugins", path = "plugins/other", version = "1.2.0" }
```

To read plugins from other repos than the defaults, list them all (this replaces
the defaults; `owner/name@ref` reads a branch or tag instead of the default
branch):

```toml
[sources]
repos = ["Cellular-Semantics/cap_skills", "your-org/your-plugins"]
```

After editing `plugins.toml` by hand, run `cs-plugin generate`.

## After cloning, or pulling a change to plugins.toml

```sh
cs-plugin sync
```

Then restart Claude Code in the project. `sync` reads no source repo: everything
it installs is already written in the committed files.

## Keep up to date

```sh
cs-plugin outdated          # pins with a newer release
cs-plugin upgrade           # move every pin to the newest release
cs-plugin upgrade cap-tools # or just one
cs-plugin remove cap-tools  # sync then uninstalls it here
```

Each of these rewrites the generated files; run `sync`, then commit.

## What it writes, and why

| File | What it is |
|---|---|
| `plugins.toml` | what you edit |
| `.claude/cs-plugin/.claude-plugin/marketplace.json` | the project's own marketplace, `<project>-plugins`: one entry per plugin, its `source` pinned to the release tag |
| `.claude/cs-plugin/<project>-set/` | a bundle plugin that depends on every pinned plugin, so one install brings in all of them |
| `.claude/settings.json` | declares the marketplace and enables its plugins; other settings are left alone |
| `.gitignore` | gains `.claude/settings.local.json`, where `sync` records this machine's path |

**A marketplace per project.** Claude Code keeps one registration per
marketplace name per machine. Pinning by putting a `ref` on a shared marketplace
means every project on the machine gets whichever pin registered last. A
marketplace named after the project is that project's alone.

**Pins on the entries, not version ranges.** Claude Code clones a marketplace
without its tags, so a dependency range like `~0.4.0` has nothing to resolve
against and silently installs the newest release (Claude Code 2.1.305).

**Bundles are refused.** A plugin such as `atlas-tools` that only depends on
others names their marketplace, so they would install from it unpinned and
shared. `add` refuses it and names the plugins to add instead.

**Browsing inside Claude Code.** Each source repo is itself a marketplace:
`claude plugin marketplace add Cellular-Semantics/cap_skills` lets `/plugin`
show its plugins. Browse there, but install with `cs-plugin`; installing from
the shared marketplace gives an unpinned plugin, shared by every project.
