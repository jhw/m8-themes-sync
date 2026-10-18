import pytest

from m8_themes_sync import cli
from m8_themes_sync.m8 import M8NotFound
from m8_themes_sync.organise import organise_themes


@pytest.fixture
def card(tmp_path):
    t = tmp_path / "M8" / "Themes"
    (t / "defaults").mkdir(parents=True)
    (t / "m8themes/tekfrenz").mkdir(parents=True)
    (t / "wol").mkdir()
    return tmp_path / "M8", t


def test_stock_moved_dupes_removed_unknown_kept(card):
    root, t = card
    (t / "GRAYSCALE.m8t").write_bytes(b"g")          # stock, not in defaults
    (t / "._GRAYSCALE.m8t").write_bytes(b"junk")
    (t / "SOLARIZED.m8t").write_bytes(b"s")          # stock, already there
    (t / "defaults/SOLARIZED.m8t").write_bytes(b"s")
    (t / "TKF.m8t").write_bytes(b"tkf")              # download, copy exists
    (t / "m8themes/tekfrenz/TKF.m8t").write_bytes(b"tkf")
    (t / "SOLARIZED3.m8t").write_bytes(b"s3")        # custom, copy in wol
    (t / "wol/SOLARIZED3.m8t").write_bytes(b"s3")
    (t / "MINE.m8t").write_bytes(b"mine")            # unique: must survive
    r = organise_themes(m8_root=root)
    assert r.moved_to_defaults == ["GRAYSCALE.m8t"]
    assert sorted(r.removed_duplicates) == ["SOLARIZED.m8t",
                                            "SOLARIZED3.m8t", "TKF.m8t"]
    assert r.left_alone == ["MINE.m8t"]
    assert (t / "defaults/GRAYSCALE.m8t").read_bytes() == b"g"
    assert sorted(p.name for p in t.glob("*.m8t")) == ["MINE.m8t"]
    assert not list(t.glob("._*"))
    assert (t / "m8themes/tekfrenz/TKF.m8t").is_file()


def test_same_name_different_bytes_is_never_deleted(card):
    root, t = card
    (t / "TKF.m8t").write_bytes(b"edited by hand")
    (t / "m8themes/tekfrenz/TKF.m8t").write_bytes(b"original")
    (t / "CASUALDJ.m8t").write_bytes(b"mine")
    (t / "defaults/CASUALDJ.m8t").write_bytes(b"stock")
    r = organise_themes(m8_root=root)
    assert r.left_alone == ["TKF.m8t"] and r.conflicts == ["CASUALDJ.m8t"]
    assert (t / "TKF.m8t").read_bytes() == b"edited by hand"
    assert (t / "CASUALDJ.m8t").read_bytes() == b"mine"


def test_dry_run_changes_nothing(card):
    root, t = card
    (t / "GRAYSCALE.m8t").write_bytes(b"g")
    (t / "TKF.m8t").write_bytes(b"x")
    (t / "wol/TKF.m8t").write_bytes(b"x")
    r = organise_themes(m8_root=root, dry_run=True)
    assert r.moved_to_defaults and r.removed_duplicates
    assert (t / "GRAYSCALE.m8t").is_file() and (t / "TKF.m8t").is_file()


def test_creates_defaults_if_missing(tmp_path):
    (tmp_path / "M8/Themes").mkdir(parents=True)
    (tmp_path / "M8/Themes/GRAYSCALE.m8t").write_bytes(b"g")
    organise_themes(m8_root=tmp_path / "M8")
    assert (tmp_path / "M8/Themes/defaults/GRAYSCALE.m8t").is_file()


def test_missing_card(tmp_path):
    with pytest.raises(M8NotFound):
        organise_themes(m8_root=tmp_path / "nope")


def test_cli_flag(card, capsys):
    root, t = card
    (t / "GRAYSCALE.m8t").write_bytes(b"g")
    assert cli.main(["--organise", "--m8-root", str(root)]) == 0
    assert "1 moved to defaults/" in capsys.readouterr().out
