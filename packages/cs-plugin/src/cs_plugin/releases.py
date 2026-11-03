"""Which release of a plugin to use: read from its repo's tags, checked before pinning.

The commands that choose a release -- add, versions, outdated, upgrade -- all
decide here, so they agree on where a plugin lives and what counts as released.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import project, remote, sources


def newest_first(entries: list[dict]) -> dict[str, list[str] | None]:
    """Released versions per plugin, None where the source has no git tags."""
    def one(entry: dict) -> tuple[str, list[str] | None]:
        url = remote.git_url(entry["source"])
        return entry["name"], (remote.versions(url, entry["name"]) if url else None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(one, entries))


def entry(name: str, cat: dict[str, dict]) -> dict:
    """A plugin's index entry, when its name alone says where it is."""
    found = cat.get(name)
    if found is None:
        raise project.ProjectError(f"{name} is not in any source; see `cs-plugin list`")
    why = sources.ambiguity(found)
    if why:
        raise project.ProjectError(why)
    return found


def source_of(name: str, spec: dict, cat: dict[str, dict]) -> tuple[dict, str]:
    """Where a plugin's releases are read from, and the repo to name for it.

    A plugin pinned by its repo or url is read from there, as sync would.
    """
    if any(k in spec for k in project.SOURCE_KEYS):
        return project.pinned_source(name, spec, cat), spec.get("repo") or spec["url"]
    found = entry(name, cat)
    return found["source"], found["repo"]


def released(name: str, source: dict) -> list[str]:
    """A plugin's released versions, newest first; an error if there are none."""
    url = remote.git_url(source)
    found = remote.versions(url, name) if url else []
    if not found:
        raise project.ProjectError(
            f"{name} has no releases (no {name}--v* tags in its repo). Pin it to a commit "
            f"in {project.CONFIG} instead: {name} = {{ sha = \"<40-char commit>\" }}")
    return found


def resolve(name: str, version: str | None, cat: dict[str, dict]) -> str:
    """The release `add` pins: `version`, or the newest, checked to exist."""
    source = entry(name, cat)["source"]
    found = released(name, source)
    version = version or found[0]
    if version not in found:
        more = f"; all of them: `cs-plugin versions {name}`" if len(found) > 10 else ""
        raise project.ProjectError(f"{name} {version} is not released; releases: "
                                   + ", ".join(found[:10]) + more)
    deps = (remote.manifest(source, remote.tag_for(name, version)) or {}).get("dependencies")
    if deps:
        # Its dependencies name another marketplace, which Claude Code would
        # install from at whatever that marketplace holds -- unpinned, and shared
        # with every other project on the machine.
        names = [d if isinstance(d, str) else d["name"] for d in deps]
        names = [n.split("@", 1)[0] for n in names]
        raise project.ProjectError(
            f"{name} {version} is a bundle of {', '.join(names)}; its dependencies "
            f"would install outside this project's pins. Add those instead:\n"
            f"  cs-plugin add {' '.join(names)}")
    return version


def behind(cfg: project.Config, cat: dict[str, dict],
           names: list[str] | None) -> list[tuple[str, str, str]]:
    """(name, pinned, newest) for each version pin with a newer release."""
    pinned = {n: s for n, s in cfg.plugins.items() if "version" in s and (not names or n in names)}
    entries = [{"name": n, "source": project.pinned_source(n, s, cat)} for n, s in pinned.items()]
    found = newest_first(entries)
    return [(n, pinned[n]["version"], found[n][0]) for n in sorted(pinned)
            if found[n] and remote.semver(found[n][0]) > remote.semver(pinned[n]["version"])]
