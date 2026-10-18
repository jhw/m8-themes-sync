from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

M8T_MAGIC = b"M8VERSION"
MAX_THEME_BYTES = 4096          # real themes are 53 bytes

# Characters FAT (the M8's SD card) cannot hold in a filename.
_FAT_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_NOT_FOLDER_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_EXT = ".m8t"


class BadTheme(ValueError):
    """The server gave us a theme row we refuse to use."""


def fat_safe(filename: str) -> str:
    cleaned = _FAT_BAD.sub("_", " ".join(str(filename or "").split()))
    cleaned = cleaned.rstrip(" .")
    return cleaned or "_"


def author_folder(user_name: str, user_id: str = "") -> str:
    """ASCII-only, FAT-safe folder name for an author.

    Author names come from a remote site and include emoji, brackets and
    unicode lookalikes (the M8 only displays ASCII), so fold to ASCII and
    replace anything else. An author with nothing usable left (e.g. only
    symbols) becomes ``user-<first 8 of their id>``.
    """
    folded = unicodedata.normalize("NFKD", str(user_name or ""))
    folded = folded.encode("ascii", "ignore").decode("ascii")
    s = _NOT_FOLDER_SAFE.sub("_", folded).strip("_.- ")[:40].strip("_.- ")
    if not s:
        s = "user-" + (re.sub(r"[^A-Za-z0-9]", "", str(user_id or ""))[:8]
                       or "unknown")
    return s


def _parse_bytea(value) -> bytes:
    """PostgREST returns bytea as the string ``\\x4d38...`` (hex)."""
    if not isinstance(value, str):
        raise BadTheme("theme data is not a string")
    s = value[2:] if value.startswith("\\x") else value
    try:
        return bytes.fromhex(s)
    except ValueError as e:
        raise BadTheme(f"theme data is not hex: {e}") from e


@dataclass(frozen=True)
class Theme:
    id: int
    name: str
    user_id: str
    user_name: str
    created_at: str
    updated_at: str
    data: bytes

    @classmethod
    def from_api(cls, d: dict) -> "Theme":
        try:
            tid = int(d["id"])
        except (KeyError, TypeError, ValueError) as e:
            raise BadTheme("theme has no usable id") from e
        name = str(d.get("name") or "").strip()
        if not name:
            raise BadTheme(f"theme {tid} has no name")
        data = _parse_bytea(d.get("data"))
        if not data.startswith(M8T_MAGIC):
            raise BadTheme(f"theme {tid} ({name}) is not an M8 theme file")
        if len(data) > MAX_THEME_BYTES:
            raise BadTheme(f"theme {tid} ({name}) is unexpectedly large")
        return cls(id=tid, name=name,
                   user_id=str(d.get("user_id") or ""),
                   user_name=str(d.get("user_name") or ""),
                   created_at=str(d.get("created_at") or ""),
                   updated_at=str(d.get("updated_at") or ""),
                   data=data)

    @property
    def filename(self) -> str:
        return fat_safe(self.name) + _EXT


def assign_paths(themes: List[Theme]) -> Dict[int, Path]:
    """Relative path (``<author>/<NAME>.m8t``) for every theme.

    Two different authors whose folder names collide (FAT ignores case) get
    their user-id appended; two themes of one author that collide on file
    name get their site id appended. Processed in id order, so the result
    is stable from run to run.
    """
    folders: Dict[str, str] = {}      # lower-case folder -> owning user_id
    paths: Dict[int, Path] = {}
    used = set()
    for t in sorted(themes, key=lambda t: t.id):
        folder = author_folder(t.user_name, t.user_id)
        owner = folders.setdefault(folder.lower(), t.user_id)
        if owner != t.user_id:
            folder = f"{folder}-{(t.user_id or 'x')[:8]}"
            folders.setdefault(folder.lower(), t.user_id)
        fname = t.filename
        if (folder.lower(), fname.lower()) in used:
            fname = f"{fat_safe(t.name)} ({t.id}){_EXT}"
        used.add((folder.lower(), fname.lower()))
        paths[t.id] = Path(folder) / fname
    return paths
