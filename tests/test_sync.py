from pathlib import Path

from conftest import FakeResp, ROW_IOS, ROW_MICRO, row
from m8_themes_sync.cache import Cache
from m8_themes_sync.sync import group_by_author, sync

ROWS = [ROW_IOS, ROW_MICRO]


def run(make_client, tmp_path, rows=ROWS, term="", dry_run=False):
    cache = Cache(tmp_path / "cache")
    c = make_client(FakeResp(200, rows))
    return sync(term, c, cache, dry_run=dry_run), cache


def test_first_run_writes_by_author(make_client, tmp_path):
    rep, cache = run(make_client, tmp_path)
    assert len(rep.new) == 2 and rep.unchanged == 0 and rep.authors == 2
    f = cache.root / "euphemism" / "IOS.m8t"
    assert f.read_bytes().startswith(b"M8VERSION") and f.stat().st_size == 53
    assert (cache.root / "microflora" / "M8CROFLORA.m8t").is_file()
    assert not list(cache.root.rglob("*.part"))


def test_second_run_is_a_noop(make_client, tmp_path):
    run(make_client, tmp_path)
    rep, _ = run(make_client, tmp_path)
    assert not rep.new and not rep.updated and rep.unchanged == 2


def test_changed_theme_is_updated(make_client, tmp_path):
    run(make_client, tmp_path)
    new_data = ROW_IOS["data"][:-2] + "ff"
    rep, cache = run(make_client, tmp_path,
                     [row(ROW_IOS, data=new_data), ROW_MICRO])
    assert [t.name for t, _ in rep.updated] == ["IOS"]
    assert (cache.root / "euphemism/IOS.m8t").read_bytes()[-1] == 0xFF


def test_rename_and_author_change_move_the_file(make_client, tmp_path):
    run(make_client, tmp_path)
    rep, cache = run(make_client, tmp_path,
                     [row(ROW_IOS, name="IOS2"), ROW_MICRO])
    assert [r.as_posix() for _, r in rep.updated] == ["euphemism/IOS2.m8t"]
    assert not (cache.root / "euphemism/IOS.m8t").exists()
    rep, cache = run(make_client, tmp_path,
                     [row(ROW_IOS, name="IOS2", user_name="newname"),
                      ROW_MICRO])
    assert (cache.root / "newname/IOS2.m8t").is_file()
    assert not (cache.root / "euphemism").exists()   # emptied dir removed


def test_term_filters_by_name_or_author(make_client, tmp_path):
    rep, cache = run(make_client, tmp_path, term="MICRO")
    assert [t.name for t, _ in rep.matched] == ["M8CROFLORA"]
    assert rep.on_site == 2
    assert not (cache.root / "euphemism").exists()


def test_dry_run_writes_nothing(make_client, tmp_path):
    rep, cache = run(make_client, tmp_path, dry_run=True)
    assert len(rep.new) == 2
    assert not cache.root.exists() or not list(cache.root.rglob("*.m8t"))


def test_group_by_author(make_client, tmp_path):
    rep, _ = run(make_client, tmp_path)
    assert list(group_by_author(rep.matched)) == ["euphemism", "microflora"]
