from __future__ import annotations

import filecmp
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .m8 import DEFAULT_M8_ROOT, DEFAULT_THEMES_DIR, M8NotFound

log = logging.getLogger("m8_themes_sync")

# The nine themes that ship with the M8 firmware.
STOCK_THEMES = frozenset({
    "BUSINESSCORE", "CASUALDJ", "EASYEYEZ", "GRAYSCALE", "MONOCHRONO",
    "PRETTYFLOWER", "SHADOWLOVE", "SOLARIZED", "WINTERSTORM"})
DEFAULTS_DIR = "defaults"


@dataclass
class OrganiseReport:
    moved_to_defaults: List[str] = field(default_factory=list)
    removed_duplicates: List[str] = field(default_factory=list)
    left_alone: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    dry_run: bool = False


def _has_identical_copy(f: Path, base: Path) -> bool:
    return any(c.is_file() and filecmp.cmp(f, c, shallow=False)
               for c in base.rglob(f.name)
               if c.parent != base and not c.name.startswith("._"))


def _drop_appledouble(f: Path) -> None:
    junk = f.with_name("._" + f.name)    # macOS metadata sidecar, if any
    if junk.is_file():
        junk.unlink()


def organise_themes(*, m8_root: Path = DEFAULT_M8_ROOT,
                    themes_dir: str = DEFAULT_THEMES_DIR,
                    dry_run: bool = False) -> OrganiseReport:
    """Tidy the root of ``<m8_root>/Themes``.

    * A stock M8 theme goes to ``Themes/defaults/`` (where they live
      originally). If ``defaults/`` already has an identical copy, the root
      copy is just removed; if it has a *different* file of that name, both
      are left and reported as a conflict.
    * Any other ``.m8t`` in the root that has a byte-identical copy in a
      subfolder (``m8themes/<author>/``, ``wol/``...) is removed: the copy
      is the one you keep.
    * Everything else is left alone and listed, so nothing is ever deleted
      unless the same bytes survive elsewhere on the card.
    """
    m8_root = Path(m8_root)
    base = m8_root / themes_dir
    if not m8_root.is_dir():
        raise M8NotFound(f"{m8_root} not found - is the M8 mounted?")
    if not base.is_dir():
        raise M8NotFound(f"{base} not found - is this an M8 SD card?")
    report = OrganiseReport(dry_run=dry_run)
    defaults = base / DEFAULTS_DIR
    say = "would " if dry_run else ""

    for f in sorted(base.glob("*.m8t"), key=lambda p: p.name.lower()):
        if f.name.startswith("._"):
            continue
        if f.stem.upper() in STOCK_THEMES:
            target = defaults / f.name
            if target.is_file():
                if not filecmp.cmp(f, target, shallow=False):
                    report.conflicts.append(f.name)
                    log.warning("%s differs from defaults/%s: left both",
                                f.name, f.name)
                    continue
                if not dry_run:
                    f.unlink()
                    _drop_appledouble(f)
                report.removed_duplicates.append(f.name)
                log.info("%sremove %s (identical copy in defaults/)",
                         say, f.name)
            else:
                if not dry_run:
                    defaults.mkdir(exist_ok=True)
                    shutil.move(str(f), str(target))
                    _drop_appledouble(f)
                report.moved_to_defaults.append(f.name)
                log.info("%smove %s -> defaults/", say, f.name)
        elif _has_identical_copy(f, base):
            if not dry_run:
                f.unlink()
                _drop_appledouble(f)
            report.removed_duplicates.append(f.name)
            log.info("%sremove %s (identical copy in a subfolder)", say,
                     f.name)
        else:
            report.left_alone.append(f.name)
            log.info("left %s (no identical copy elsewhere)", f.name)
    return report
