# cs-plugin

Pin a project's Claude Code plugins in one `plugins.toml`, from any number of
plugin repos, and install exactly that.

```sh
uvx cs-plugin add cap-tools remote-h5ad-obs
uvx cs-plugin sync
```

**Using it:** see [`packages/cs-plugin/README.md`](packages/cs-plugin/README.md),
which is also the page on [PyPI](https://pypi.org/project/cs-plugin/).

The rest of this file is for maintaining it.

## Layout

| Path | What |
|---|---|
| `packages/cs-plugin/` | the package: `sources.py` reads the plugin repos, `project.py` owns plugins.toml and the generated files, `cli.py` the commands |
| `scripts/versions.py` | release bookkeeping, shared with the plugin repos |
| `.github/workflows/` | `test`, `release`, `publish` |

The default source repos are `DEFAULT_SOURCES` in
`packages/cs-plugin/src/cs_plugin/sources.py`. Changing them is a package change:
bump the version.

## Develop

```sh
./dev.sh            # tests, lint, release-tooling tests, sdist/wheel build check
```

The unit tests are offline. The real `claude` and GitHub were exercised by hand
in throwaway Claude configs (`CLAUDE_CONFIG_DIR=$(mktemp -d)`), which keeps your
own plugins untouched; do the same when changing `sync`.

## Release and publish

Bump `packages/cs-plugin/pyproject.toml` **and** `__version__` in
`src/cs_plugin/__init__.py`, open a PR, merge. Never tag by hand.

| Workflow | When | What |
|---|---|---|
| `test` | every PR and push | lint; tests on Python 3.11–3.13; build, `twine check`, and run the wheel; install from git; on PRs, `version-bumps` |
| `release` | after `test` passes on main | tags `pkg-cs-plugin--v<version>` if that version has no tag, and writes a GitHub Release |
| `publish` | after `release` cuts a tag | uploads that tag to **TestPyPI**, then installs it back from there |
| `publish` | by hand | `gh workflow run publish.yml -f index=pypi` uploads the newest tag to **PyPI**; add `-f tag=pkg-cs-plugin--v0.1.0` for another |

Real PyPI is by hand only: a version uploaded there can never be uploaded again,
even after it is deleted. Let TestPyPI show it installs first:

```sh
uvx --default-index https://test.pypi.org/simple/ cs-plugin@0.1.0 --version
```

### One-time setup

Publishing uses trusted publishing (OIDC), so no token is stored anywhere. Each
index needs a *pending publisher* registered by its account owner before the
first upload, which also reserves the name:

| | TestPyPI | PyPI |
|---|---|---|
| Page | https://test.pypi.org/manage/account/publishing/ | https://pypi.org/manage/account/publishing/ |
| PyPI project name | `cs-plugin` | `cs-plugin` |
| Owner | `ubyndr` | `ubyndr` |
| Repository name | `cs-plugin` | `cs-plugin` |
| Workflow name | `publish.yml` | `publish.yml` |
| Environment name | `testpypi` | `pypi` |

The GitHub environments `testpypi` and `pypi` are created on first use. To make
a PyPI upload need a second pair of eyes, add a required reviewer to the `pypi`
environment under Settings → Environments.
