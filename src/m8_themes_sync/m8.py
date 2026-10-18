from __future__ import annotations

import filecmp
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

from .cache import Cache
from .sync import Match

log = logging.getLogger("m8_themes_sync")

DEFAULT_M8_ROOT = Path("/Volumes/M8")
DEFAULT_THEMES_DIR = "Themes"
DEFAULT_SUBDIR = "m8themes"     # <Themes>/m8themes/<author>/NAME.m8t


class M8NotFound(Exception):
    """The M8 volume or its Themes folder is not there."""


@dataclass
class M8Report:
    destination: Path
    copied: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)
    not_cached: List[str] = field(default_factory=list)
    flattened: List[str] = field(default_factory=list)
    dry_run: bool = False


def copy_to_m8(items: Sequence[Match], cache: Cache, *,
               m8_root: Path = DEFAULT_M8_ROOT,
               themes_dir: str = DEFAULT_THEMES_DIR,
               subdir: str = DEFAULT_SUBDIR,
               dry_run: bool = False) -> M8Report:
    """Copy cached themes to ``<m8_root>/<themes_dir>/<subdir>/``.

    By default that is ``/Volumes/M8/Themes/m8themes/NAME.m8t`` (flat).
    Themes already on the card with identical content are left alone, and
    nothing outside ``<subdir>`` is touched - the stock themes in the root of
    ``Themes/`` and your own custom ones are never modified. ``Themes/`` must
    already exist; only the folders below it are created.
    """
    m8_root = Path(m8_root)
    if not m8_root.is_dir():
        raise M8NotFound(f"{m8_root} not found - is the M8 mounted?")
    base = m8_root / themes_dir
    if not base.is_dir():
        raise M8NotFound(f"{base} not found - is this an M8 SD card?")
    dest = base / subdir if subdir else base

    report = M8Report(destination=dest, dry_run=dry_run)
    log.info("M8: %s %s", "checking (dry run)" if dry_run else "copying to",
             dest)
    for _theme, rel in items:
        src = cache.file(rel)
        shown = rel.as_posix()
        if not src.is_file():
            report.not_cached.append(shown)
            log.warning("M8: %s not in the local cache, skipped", shown)
            continue
        target = dest / rel
        if target.is_file() and filecmp.cmp(src, target, shallow=False):
            report.unchanged.append(shown)
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        report.copied.append(shown)
        log.info("M8: %s %s", "would copy" if dry_run else "copied", shown)
    _flatten_legacy(dest, report, dry_run,
                    {rel.name: cache.file(rel) for _t, rel in items})
    return report


def _flatten_legacy(dest: Path, report: M8Report, dry_run: bool,
                    cached: dict) -> None:
    """Remove ``.m8t`` files in sub-folders of ``dest`` (the old
    ``<author>/NAME.m8t`` layout) whose exact bytes now sit as a file
    directly in ``dest`` (under any name: a theme sharing its name with
    another is renamed ``NAME (author).m8t``), then any folders left empty.
    A file with no identical flat copy is never touched."""
    if not dest.is_dir():
        return
    flat = {f.read_bytes() for f in dest.glob("*.m8t")
            if f.is_file() and not f.name.startswith("._")}
    if dry_run:     # what the copy above would have put there
        flat |= {src.read_bytes() for src in cached.values()
                 if src.is_file()}
    for old in sorted(dest.rglob("*.m8t")):
        if old.parent == dest or old.name.startswith("._"):
            continue
        if old.read_bytes() in flat:
            shown = old.relative_to(dest).as_posix()
            report.flattened.append(shown)
            log.info("M8: %s %s (now at the top level)",
                     "would remove" if dry_run else "removed", shown)
            if not dry_run:
                old.unlink()
                junk = old.with_name("._" + old.name)
                if junk.is_file():
                    junk.unlink()
    if dry_run:
        return
    for d in sorted((p for p in dest.rglob("*") if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        left = [c for c in d.iterdir() if not c.name.startswith("._")]
        if not left:
            for c in d.iterdir():
                c.unlink()
            d.rmdir()
