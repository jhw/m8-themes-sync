import pytest

from conftest import FakeResp, ROW_IOS, ROW_MICRO
from m8_themes_sync.cache import Cache
from m8_themes_sync.m8 import M8NotFound, copy_to_m8
from m8_themes_sync.sync import sync


@pytest.fixture
def synced(make_client, tmp_path):
    cache = Cache(tmp_path / "cache")
    rep = sync("", make_client(FakeResp(200, [ROW_IOS, ROW_MICRO])), cache)
    return rep, cache


def card(tmp_path, with_themes=True):
    root = tmp_path / "M8"
    (root / "Themes").mkdir(parents=True) if with_themes else root.mkdir()
    return root


def test_copies_into_subdir_only(synced, tmp_path):
    rep, cache = synced
    root = card(tmp_path)
    stock = root / "Themes" / "TKF.m8t"
    stock.write_bytes(b"stock")
    r = copy_to_m8(rep.matched, cache, m8_root=root)
    assert len(r.copied) == 2
    assert (root / "Themes/m8themes/IOS.m8t").read_bytes() \
        == (cache.root / "IOS.m8t").read_bytes()
    assert stock.read_bytes() == b"stock"           # root untouched
    assert sorted(p.name for p in (root / "Themes").iterdir()) \
        == ["TKF.m8t", "m8themes"]


def test_skips_identical_and_refreshes_changed(synced, tmp_path):
    rep, cache = synced
    root = card(tmp_path)
    copy_to_m8(rep.matched, cache, m8_root=root)
    assert len(copy_to_m8(rep.matched, cache, m8_root=root).unchanged) == 2
    (root / "Themes/m8themes/IOS.m8t").write_bytes(b"old")
    r = copy_to_m8(rep.matched, cache, m8_root=root)
    assert r.copied == ["IOS.m8t"] and len(r.unchanged) == 1


def test_dry_run(synced, tmp_path):
    rep, cache = synced
    root = card(tmp_path)
    r = copy_to_m8(rep.matched, cache, m8_root=root, dry_run=True)
    assert len(r.copied) == 2
    assert not (root / "Themes" / "m8themes").exists()


def test_missing_card_or_themes_dir(synced, tmp_path):
    rep, cache = synced
    with pytest.raises(M8NotFound):
        copy_to_m8(rep.matched, cache, m8_root=tmp_path / "nope")
    with pytest.raises(M8NotFound):
        copy_to_m8(rep.matched, cache, m8_root=card(tmp_path, False))


def test_not_cached_is_reported(synced, tmp_path):
    rep, cache = synced
    (cache.root / "IOS.m8t").unlink()
    r = copy_to_m8(rep.matched, cache, m8_root=card(tmp_path))
    assert r.not_cached == ["IOS.m8t"]


def test_old_author_folders_are_flattened(synced, tmp_path):
    rep, cache = synced
    root = card(tmp_path)
    old = root / "Themes/m8themes/euphemism"
    old.mkdir(parents=True)
    (old / "IOS.m8t").write_bytes((cache.root / "IOS.m8t").read_bytes())
    (old / "._IOS.m8t").write_bytes(b"appledouble")
    (old / "MINE.m8t").write_bytes(b"not on the site")   # must survive
    gone = root / "Themes/m8themes/microflora"
    gone.mkdir()
    (gone / "M8CROFLORA.m8t").write_bytes(
        (cache.root / "M8CROFLORA.m8t").read_bytes())
    (gone / "._M8CROFLORA.m8t").write_bytes(b"appledouble")
    dry = copy_to_m8(rep.matched, cache, m8_root=root, dry_run=True)
    assert sorted(dry.flattened) == ["euphemism/IOS.m8t",
                                     "microflora/M8CROFLORA.m8t"]
    assert (old / "IOS.m8t").exists()                    # dry run: untouched
    r = copy_to_m8(rep.matched, cache, m8_root=root)
    assert sorted(r.flattened) == ["euphemism/IOS.m8t",
                                   "microflora/M8CROFLORA.m8t"]
    assert (root / "Themes/m8themes/IOS.m8t").is_file()
    assert not gone.exists()                             # emptied, removed
    assert (old / "MINE.m8t").read_bytes() == b"not on the site"
    assert not (old / "IOS.m8t").exists()
