"""Which plugins exist: read live from the plugin repos' own marketplaces.

Each source repo keeps a .claude-plugin/marketplace.json at its root, and that
file is the only list of its plugins -- nothing is copied anywhere. A plugin a
source lists by relative path is seen from outside as a `git-subdir` entry
pointing back into its repo. Versions are not read here: releases come from
each repo's `<plugin>--v<version>` tags, when they are needed.

A project names its sources in plugins.toml; without that, DEFAULT_SOURCES.
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from .remote import RemoteError

DEFAULT_SOURCES = (
    "Cellular-Semantics/cap_skills",
    "ubyndr/atlas-skills-release-test",
)
# Plugin manifest fields worth showing in `list`; the rest stay in the source.
CARRIED = ("description", "homepage", "category")


class SourceError(Exception):
    pass


def marketplace_url(repo: str) -> str:
    ref = "HEAD"
    if "@" in repo:
        repo, ref = repo.split("@", 1)
    return (f"https://raw.githubusercontent.com/{repo}/{ref}/"
            ".claude-plugin/marketplace.json")


def entry_source(repo: str, marketplace: dict, source: str | dict) -> dict:
    """A plugin's source as seen from outside its repo."""
    if isinstance(source, dict):
        return dict(source)
    root = marketplace.get("metadata", {}).get("pluginRoot", "")
    rel = source if source.startswith("./") else posixpath.join(root or ".", source)
    return {"source": "git-subdir", "url": f"https://github.com/{repo.split('@')[0]}.git",
            "path": posixpath.normpath(rel)}


def index(repos: list[str], fetch: Callable[[str], dict]) -> dict[str, dict]:
    """Every plugin in every source, by name: {name, source, repo, description...}."""
    def one(repo: str) -> tuple[str, dict]:
        try:
            return repo, fetch(marketplace_url(repo))
        except RemoteError as e:
            raise SourceError(f"source {repo}: {e}") from e

    with ThreadPoolExecutor(max_workers=8) as pool:
        markets = list(pool.map(one, repos))
    plugins: dict[str, dict] = {}
    for repo, market in markets:
        for p in market.get("plugins", []):
            name = p["name"]
            if name in plugins:
                # Not fatal for the other plugins: only using this name is.
                plugins[name].setdefault("also_in", []).append(repo)
                continue
            entry = {"name": name, "repo": repo,
                     "source": entry_source(repo, market, p["source"])}
            entry.update({k: p[k] for k in CARRIED if k in p})
            plugins[name] = entry
    return plugins


def ambiguity(entry: dict) -> str | None:
    """Why a plugin name cannot be pinned by name alone, or None."""
    if not entry.get("also_in"):
        return None
    repos = " and ".join([entry["repo"], *entry["also_in"]])
    return (f"{entry['name']} is in both {repos}; pin it with an explicit repo in "
            f"plugins.toml, e.g. {entry['name']} = {{ repo = \"{entry['repo']}\", "
            f"path = \"{entry['source'].get('path', '.')}\", version = \"...\" }}")
