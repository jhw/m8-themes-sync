from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .cache import Cache
from .client import ThemesClient
from .models import Theme, assign_paths

log = logging.getLogger("m8_themes_sync")

Match = Tuple[Theme, Path]


@dataclass
class SyncReport:
    term: str = ""
    on_site: int = 0
    matched: List[Match] = field(default_factory=list)
    new: List[Match] = field(default_factory=list)
    updated: List[Match] = field(default_factory=list)
    unchanged: int = 0
    failed: List[Tuple[str, str]] = field(default_factory=list)
    dry_run: bool = False

    @property
    def authors(self) -> int:
        return len({rel.parent for _, rel in self.matched})


def catalogue(client: ThemesClient) -> Tuple[List[Theme], Dict[int, Path]]:
    """Every theme on the site and where each belongs (``<author>/<file>``)."""
    log.info("fetching the theme list from m8them.es")
    themes = client.fetch_all()
    paths = assign_paths(themes)
    log.info("%d themes by %d authors", len(themes),
             len({p.parent for p in paths.values()}))
    return themes, paths


def matches(term: str, theme: Theme, rel: Path) -> bool:
    """Empty term matches everything; else a case-insensitive substring of the
    theme name or its author (as shown on the site, or as a folder)."""
    t = (term or "").strip().lower()
    return (not t or t in theme.name.lower()
            or t in theme.user_name.lower() or t in rel.parent.name.lower())


def group_by_author(items: List[Match]) -> Dict[str, List[Match]]:
    groups: Dict[str, List[Match]] = defaultdict(list)
    for item in items:
        groups[item[1].parent.as_posix()].append(item)
    return dict(sorted(groups.items(), key=lambda kv: kv[0].lower()))


def sync(term: str, client: ThemesClient, cache: Cache, *,
         dry_run: bool = False) -> SyncReport:
    """Fetch the catalogue and write whatever the local cache is missing.

    The whole catalogue comes in one request, so the "download" is really just
    writing files: a theme is written if its cache file is missing, differs
    from the site's bytes, or the site moved/renamed it.
    """
    report = SyncReport(term=term, dry_run=dry_run)
    themes, paths = catalogue(client)
    report.on_site = len(themes)
    report.matched = [(t, paths[t.id]) for t in themes
                      if matches(term, t, paths[t.id])]
    log.info("%d match %r", len(report.matched), term or "(everything)")

    for theme, rel in report.matched:
        state = cache.status(theme, rel)
        if state == "same":
            report.unchanged += 1
            continue
        (report.new if state == "new" else report.updated).append(
            (theme, rel))
        if dry_run:
            log.info("would %s %s", "add" if state == "new" else "update",
                     rel.as_posix())
            continue
        try:
            cache.store(theme, rel)
            log.info("%s %s", "added" if state == "new" else "updated",
                     rel.as_posix())
        except OSError as e:
            report.failed.append((rel.as_posix(), str(e)))
            log.warning("%s: FAILED - %s", rel.as_posix(), e)
    return report
