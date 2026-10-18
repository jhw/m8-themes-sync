from conftest import FakeResp, ROW_IOS, ROW_MICRO
from m8_themes_sync import cli
from m8_themes_sync.client import ThemesClient


def patch_client(monkeypatch, *responses):
    from conftest import FakeSession
    session = FakeSession(*responses)
    real = ThemesClient
    monkeypatch.setattr(cli, "ThemesClient", lambda **kw: real(
        session=session, sleep=lambda s: None, **{**kw, "delay": 0}))
    return session


def test_sync_and_copy(monkeypatch, tmp_path, capsys):
    patch_client(monkeypatch, FakeResp(200, [ROW_IOS, ROW_MICRO]))
    root = tmp_path / "M8"
    (root / "Themes").mkdir(parents=True)
    rc = cli.main(["--cache-dir", str(tmp_path / "c"), "--m8",
                   "--m8-root", str(root)])
    assert rc == 0
    assert (root / "Themes/m8themes/microflora/M8CROFLORA.m8t").is_file()
    assert "2 of 2 themes match (2 authors)" in capsys.readouterr().out


def test_list_prints_by_author_and_writes_nothing(monkeypatch, tmp_path,
                                                   capsys):
    patch_client(monkeypatch, FakeResp(200, [ROW_IOS, ROW_MICRO]))
    rc = cli.main(["--list", "--cache-dir", str(tmp_path / "c")])
    out = capsys.readouterr().out
    assert rc == 0 and "euphemism (1)\n    IOS" in out
    assert not (tmp_path / "c").exists()


def test_server_error_exit_code(monkeypatch, tmp_path):
    patch_client(monkeypatch, *[FakeResp(500)] * 4)
    assert cli.main(["--cache-dir", str(tmp_path / "c")]) == 1


def test_missing_m8_is_an_error(monkeypatch, tmp_path):
    patch_client(monkeypatch, FakeResp(200, [ROW_IOS]))
    assert cli.main(["--cache-dir", str(tmp_path / "c"), "--m8",
                     "--m8-root", str(tmp_path / "nope")]) == 1
