from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests

from . import __version__
from .cache import Cache, default_cache_dir
from .client import BASE_URL, ThemesClient, ThemesError
from .m8 import (DEFAULT_M8_ROOT, DEFAULT_SUBDIR, DEFAULT_THEMES_DIR,
                 M8NotFound, copy_to_m8)
from .sync import catalogue, group_by_author, matches, sync

log = logging.getLogger("m8_themes_sync")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m8-themes-sync",
        description="Mirror M8 themes (.m8t) from m8them.es into "
                    "<cache>/<author>/, optionally copying them to an M8 "
                    "SD card.")
    p.add_argument("term", nargs="?", default="",
                   help="only themes whose name or author contains this "
                        "(omit for every theme)")
    p.add_argument("--list", action="store_true",
                   help="print the full catalogue grouped by author and "
                        "exit; writes nothing")
    p.add_argument("--cache-dir", type=Path, default=None,
                   help="local cache (default: <project>/tmp, or "
                        "$M8_THEMES_SYNC_CACHE)")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be written/copied, change nothing")
    p.add_argument("--m8", action="store_true",
                   help="copy matching themes to the M8 after syncing")
    p.add_argument("--m8-root", type=Path, default=DEFAULT_M8_ROOT,
                   help=f"M8 mount point (default {DEFAULT_M8_ROOT})")
    p.add_argument("--m8-subdir", default=DEFAULT_SUBDIR,
                   help=f"folder inside {DEFAULT_THEMES_DIR}/ on the M8; "
                        f"themes go in <subdir>/<author>/ "
                        f"(default '{DEFAULT_SUBDIR}')")
    p.add_argument("--delay", type=float, default=1.0,
                   help="seconds between requests to the site (default 1.0)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="also log every HTTP request and pause")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="only log warnings and errors")
    p.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)
    p.add_argument("--api-key", default=None, help=argparse.SUPPRESS)
    p.add_argument("--version", action="version",
                   version=f"m8-themes-sync {__version__}")
    return p


def setup_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet \
        else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S"))
    log.handlers[:] = [handler]
    log.setLevel(level)
    log.propagate = False


def print_catalogue(items) -> None:
    for folder, group in group_by_author(items).items():
        print(f"{folder} ({len(group)})")
        for theme, _rel in sorted(group, key=lambda m: m[0].name.lower()):
            print(f"    {theme.name}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose, args.quiet)
    client = ThemesClient(base_url=args.base_url, api_key=args.api_key,
                          delay=args.delay)

    if args.list:
        try:
            themes, paths = catalogue(client)
        except (ThemesError, requests.RequestException) as e:
            log.error("%s", e)
            return 1
        print_catalogue([(t, paths[t.id]) for t in themes
                         if matches(args.term, t, paths[t.id])])
        return 0

    cache = Cache(args.cache_dir or default_cache_dir())
    log.info("cache: %s", cache.root)
    try:
        report = sync(args.term, client, cache, dry_run=args.dry_run)
    except (ThemesError, requests.RequestException) as e:
        log.error("%s", e)
        return 1

    verb = "would add" if report.dry_run else "added"
    log.info("done: %d of %d themes match (%d authors); %s %d new + %d "
             "updated; %d already up to date; %d HTTP requests",
             len(report.matched), report.on_site, report.authors, verb,
             len(report.new), len(report.updated), report.unchanged,
             client.requests_made)
    if report.failed:
        log.warning("%d failed: %s", len(report.failed),
                    ", ".join(p for p, _ in report.failed))

    status = 1 if report.failed else 0
    if args.m8:
        try:
            m = copy_to_m8(report.matched, cache, m8_root=args.m8_root,
                           subdir=args.m8_subdir, dry_run=args.dry_run)
        except M8NotFound as e:
            log.error("%s", e)
            return 1
        log.info("M8 done: %s %d, %d already there%s",
                 "would copy" if m.dry_run else "copied", len(m.copied),
                 len(m.unchanged),
                 f", {len(m.not_cached)} not in cache" if m.not_cached
                 else "")
    return status


if __name__ == "__main__":
    sys.exit(main())
