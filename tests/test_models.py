from pathlib import Path

import pytest

from conftest import ROW_IOS, ROW_MICRO, row
from m8_themes_sync.models import (BadTheme, Theme, assign_paths,
                                   author_folder, fat_safe)


def test_parses_site_row():
    t = Theme.from_api(ROW_MICRO)
    assert (t.id, t.name, t.user_name) == (420, "M8CROFLORA", "microflora")
    assert len(t.data) == 53 and t.data.startswith(b"M8VERSION")
    assert t.filename == "M8CROFLORA.m8t"


@pytest.mark.parametrize("bad", [
    {"data": "\\x00112233"},            # not an M8 file
    {"data": "\\xzz"},                  # not hex
    {"data": None},
    {"name": "  "},
    {"id": None},
    {"data": "\\x" + "4d3856455253494f4e" + "00" * 5000},   # too large
])
def test_rejects_bad_rows(bad):
    with pytest.raises(BadTheme):
        Theme.from_api(row(ROW_MICRO, **bad))


@pytest.mark.parametrize("name,uid,expected", [
    ("beat-pharmaxy", "u", "beat-pharmaxy"),
    ("vincent--🤖ᶜᴴᴼᴺᴷᴱᴿᵇᵒᵗ", "u", "vincent--cHONKERbot"),
    ("nora-(kulupu-mun)", "u", "nora-_kulupu-mun"),
    ("../../etc", "u", "etc"),
    ("₱₣₴₮ɽ", "abcdef1234567", "user-abcdef12"),
    ("", "", "user-unknown"),
    ("impots.groove.fr", "u", "impots.groove.fr"),
])
def test_author_folder(name, uid, expected):
    assert author_folder(name, uid) == expected


def test_author_folder_cannot_escape():
    for hostile in ["..", "/", "a/../b", "C:\\x", "\x00"]:
        f = author_folder(hostile, "id")
        assert "/" not in f and "\\" not in f and f not in ("", ".", "..")


def test_fat_safe():
    assert fat_safe('A:B*C?') == "A_B_C_"
    assert fat_safe("PACMAN 2^5") == "PACMAN 2^5"
    assert fat_safe("...") == "_"


def test_assign_paths_duplicates():
    a = Theme.from_api(row(ROW_MICRO, id=1, name="SUNSET", user_id="u1",
                           user_name="Foo"))
    b = Theme.from_api(row(ROW_MICRO, id=2, name="sunset", user_id="u1",
                           user_name="Foo"))               # same author
    c = Theme.from_api(row(ROW_IOS, id=3, name="SUNSET", user_id="u2222222",
                           user_name="foo"))               # folder clash
    paths = assign_paths([c, b, a])
    assert paths[1] == Path("Foo/SUNSET.m8t")
    assert paths[2] == Path("Foo/sunset (2).m8t")
    assert paths[3] == Path("foo-u2222222/SUNSET.m8t")
    assert len({str(p).lower() for p in paths.values()}) == 3
