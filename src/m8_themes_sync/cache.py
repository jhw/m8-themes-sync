from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from .models import Theme


def default_cache_dir() -> Path:
    """``<project>/tmp`` when run from a source checkout, else ``./tmp``.

    Override with $M8_THEMES_SYNC_CACHE or --cache-dir.
    """
    env = os.environ.get("M8_THEMES_SYNC_CACHE")
    if env:
        return Path(env).expanduser()
    project = Path(__file__).resolve().parents[2]
    if (project / "pyproject.toml").is_file():
        return project / "tmp"
    return Path.cwd() / "tmp"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    os.replace(part, path)


class Cache:
    """Local mirror laid out as ``<author>/<THEME>.m8t``::

        tmp/beat-pharmaxy/BELLAGIO.m8t
        tmp/tekfrenz/TKF.m8t
        tmp/.index.json            <- site id -> where we stored it

    A theme is only 53 bytes, so "is it up to date?" is answered by comparing
    the file's bytes with what the site sent. The index just remembers where
    each site id went, so a theme renamed (or moved to another author) on the
    site is moved here too instead of being left behind as a stale copy.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.index_path = self.root / ".index.json"
        self.index: Dict[str, dict] = self._load_index()

    def _load_index(self) -> Dict[str, dict]:
        try:
            data = json.loads(self.index_path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_index(self) -> None:
        body = json.dumps(self.index, indent=2, sort_keys=True).encode()
        _atomic_write(self.index_path, body)

    def file(self, rel: Path) -> Path:
        return self.root / rel

    def status(self, theme: Theme, rel: Path) -> str:
        """'new', 'updated' (file or location differs) or 'same'."""
        target = self.file(rel)
        if not target.is_file():
            # Renamed/moved on the site: we hold it, just somewhere else.
            return "updated" if self.moved_from(theme, rel) else "new"
        old = self.index.get(str(theme.id), {}).get("rel")
        if target.read_bytes() != theme.data or (old and old != rel.as_posix()):
            return "updated"
        return "same"

    def moved_from(self, theme: Theme, rel: Path) -> Optional[Path]:
        old = self.index.get(str(theme.id), {}).get("rel")
        if old and old != rel.as_posix() and self.file(Path(old)).is_file():
            return Path(old)
        return None

    def store(self, theme: Theme, rel: Path) -> None:
        old = self.moved_from(theme, rel)
        _atomic_write(self.file(rel), theme.data)
        if old is not None:
            self.file(old).unlink()
            try:
                self.file(old).parent.rmdir()   # only if now empty
            except OSError:
                pass
        self.index[str(theme.id)] = {
            "rel": rel.as_posix(), "name": theme.name,
            "author": theme.user_name, "updated_at": theme.updated_at}
        self.save_index()
