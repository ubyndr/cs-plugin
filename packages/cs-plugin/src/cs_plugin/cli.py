"""cs-plugin: pin a project's Claude Code plugins in plugins.toml, install exactly that.

    cs-plugin list                     every plugin in the sources, with releases
    cs-plugin versions NAME            every release of one plugin
    cs-plugin add NAME[@VERSION]...    pin plugins (newest release by default)
    cs-plugin remove NAME...           drop plugins
    cs-plugin upgrade [NAME...]        move pins to the newest release
    cs-plugin outdated                 pins with a newer release
    cs-plugin generate                 rewrite the generated files from plugins.toml
    cs-plugin sync                     install exactly what plugins.toml pins
    cs-plugin sources                  the repos plugins are read from

Run from the project's root. Which plugins exist is read live from the source
repos' own marketplaces: plugins.toml [sources], or the defaults. add, remove
and upgrade regenerate the files Claude Code reads; sync is what a teammate runs
after cloning, and after every pull that changes plugins.toml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, claude, project, releases, remote, sources


def _index(cfg: project.Config) -> dict[str, dict]:
    return sources.index(cfg.repos, remote.read_json)


def cmd_list(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    cat = _index(cfg)
    found = releases.newest_first(list(cat.values()))
    width = max(map(len, cat), default=0)
    for name in sorted(cat):
        rel = found[name]
        newest = rel[0] if rel else ("no releases" if rel is not None else "not git")
        mark = "*" if name in cfg.plugins else " "
        clash = f"  (also in {', '.join(cat[name]['also_in'])})" if cat[name].get("also_in") else ""
        print(f"{mark} {name:<{width}}  {newest:<12}  {cat[name]['repo']}{clash}")
        if args.long and cat[name].get("description"):
            print(f"  {'':<{width}}  {cat[name]['description']}")
    if cfg.plugins:
        print(f"\n* pinned in {project.CONFIG}")
    return 0


def cmd_versions(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    cat = _index(cfg)
    name = args.plugin
    spec = cfg.plugins.get(name, {})
    source, repo = releases.source_of(name, spec, cat)
    found = releases.released(name, source)
    pinned = spec.get("version")
    rows = []
    for v in found:
        notes = ["newest"] if v == found[0] else []
        if v == pinned:
            notes.append(f"pinned in {project.CONFIG}")
        link = (remote.release_url(source, name, v) or "") if args.long else ""
        rows.append((v, ", ".join(notes), link))
    vw = max(len(v) for v, _, _ in rows)
    nw = max(len(n) for _, n, _ in rows)
    print(f"{name}  ({repo})")
    for v, notes, link in rows:
        print(f"  {v:<{vw}}  {notes:<{nw}}  {link}".rstrip())
    if pinned and pinned not in found:
        print(f"\npinned in {project.CONFIG} to {pinned}, which is not a release")
    for k in ("ref", "sha"):
        if k in spec:
            print(f"\npinned in {project.CONFIG} to {k} {spec[k]}, not a release")
    return 0


def _write(cfg: project.Config, cat: dict[str, dict]) -> None:
    root = Path.cwd()
    project.save(root, cfg)
    for path in project.generate(root, cfg, cat):
        print(f"wrote {path.relative_to(root)}")
    print(f"Next: `cs-plugin sync` to install, then commit {project.CONFIG} and .claude/.")


def cmd_add(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    cat = _index(cfg)
    for item in args.plugins:
        name, _, version = item.partition("@")
        version = releases.resolve(name, version or None, cat)
        old = cfg.plugins.get(name, {}).get("version")
        cfg.plugins[name] = {"version": version}
        print(f"{name} {old + ' -> ' if old and old != version else ''}{version}")
    _write(cfg, cat)
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    missing = [n for n in args.plugins if n not in cfg.plugins]
    if missing:
        raise project.ProjectError(f"not in {project.CONFIG}: {', '.join(missing)}")
    for name in args.plugins:
        del cfg.plugins[name]
        print(f"removed {name}")
    _write(cfg, _index(cfg))
    print("`cs-plugin sync` also uninstalls them from this project.")
    return 0


def cmd_outdated(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    behind = releases.behind(cfg, _index(cfg), None)
    for name, have, newest in behind:
        print(f"{name}  {have} -> {newest}")
    unversioned = [n for n, s in cfg.plugins.items() if "version" not in s]
    if unversioned:
        print(f"pinned to a ref or commit, not checked: {', '.join(sorted(unversioned))}")
    if not behind:
        print("every versioned pin is the newest release")
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    unknown = [n for n in args.plugins if n not in cfg.plugins]
    if unknown:
        raise project.ProjectError(f"not in {project.CONFIG}: {', '.join(unknown)}")
    cat = _index(cfg)
    behind = releases.behind(cfg, cat, args.plugins or None)
    for name, have, newest in behind:
        cfg.plugins[name] = {"version": newest}
        print(f"{name} {have} -> {newest}")
    if not behind:
        print("already at the newest releases")
        return 0
    _write(cfg, cat)
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    root = Path.cwd()
    cfg = project.load(root)
    changed = project.generate(root, cfg, _index(cfg))
    for path in changed:
        print(f"wrote {path.relative_to(root)}")
    if not changed:
        print("generated files are current")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if not claude.available():
        raise project.ProjectError("`claude` is not on PATH; install Claude Code first")
    cfg = project.load(root)
    problems = project.stale(root, cfg)
    if problems:
        raise project.ProjectError("the generated files do not match plugins.toml:\n  "
                                   + "\n  ".join(problems) + "\nRun `cs-plugin generate`.")
    settings = root / project.SETTINGS
    committed = settings.read_text() if settings.exists() else None
    try:
        # Local scope: registering writes the marketplace's absolute path, which
        # belongs in the uncommitted settings file, not the shared one.
        claude.run("plugin", "marketplace", "add", str((root / project.GEN_DIR).resolve()),
                "--scope", "local")
        claude.run("plugin", "marketplace", "update", cfg.marketplace)
        for cmd in project.sync_plan(cfg, claude.installed(cfg, root)):
            print("claude " + " ".join(cmd))
            print("  " + (claude.run(*cmd).stdout.strip().splitlines() or [""])[-1])
    finally:
        project.restore_layout(settings, committed)
    after = claude.installed(cfg, root)
    print()
    status = 0
    for name in sorted(cfg.plugins):
        want = cfg.plugins[name].get("version")
        have = after.get(name)
        ok = have is not None and (want is None or have == want)
        status |= not ok
        print(f"{'ok ' if ok else 'BAD'} {name} {have or 'not installed'}"
              + (f" (pinned {want})" if want and have != want else ""))
    print("\nRestart Claude Code in this project to load the changes.")
    return status


def cmd_sources(args: argparse.Namespace) -> int:
    cfg = project.load(Path.cwd())
    where = f"[sources] in {project.CONFIG}" if cfg.sources is not None else "the defaults"
    print(f"Plugins are read from these repos' marketplaces ({where}):")
    for repo in cfg.repos:
        print(f"  {repo}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cs-plugin", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"cs-plugin {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="every plugin in the sources, with releases")
    p.add_argument("-l", "--long", action="store_true", help="also show descriptions")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("versions", help="every release of one plugin, newest first")
    p.add_argument("plugin", metavar="NAME")
    p.add_argument("-l", "--long", action="store_true", help="also link each release")
    p.set_defaults(fn=cmd_versions)
    p = sub.add_parser("add", help="pin plugins, newest release unless NAME@VERSION")
    p.add_argument("plugins", nargs="+", metavar="NAME[@VERSION]")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("remove", help="drop plugins from plugins.toml")
    p.add_argument("plugins", nargs="+", metavar="NAME")
    p.set_defaults(fn=cmd_remove)
    p = sub.add_parser("upgrade", help="move pins to the newest release")
    p.add_argument("plugins", nargs="*", metavar="NAME")
    p.set_defaults(fn=cmd_upgrade)
    sub.add_parser("outdated", help="pins with a newer release").set_defaults(fn=cmd_outdated)
    sub.add_parser("generate", help="rewrite the generated files").set_defaults(fn=cmd_generate)
    sub.add_parser("sync", help="install exactly what plugins.toml pins").set_defaults(fn=cmd_sync)
    sub.add_parser("sources", help="the repos plugins are read from").set_defaults(fn=cmd_sources)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (project.ProjectError, sources.SourceError, remote.RemoteError) as e:
        print(f"cs-plugin: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
