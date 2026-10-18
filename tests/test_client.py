import pytest
import requests

from conftest import FakeResp, ROW_IOS, ROW_MICRO, row
from m8_themes_sync.client import ANON_KEY, ThemesClient, ThemesError


def test_fetch_all_one_request(make_client):
    c = make_client(FakeResp(200, [ROW_IOS, ROW_MICRO]))
    themes = c.fetch_all()
    assert [t.name for t in themes] == ["IOS", "M8CROFLORA"]
    url, params, headers = c.session.calls[0]
    assert url.endswith("/rest/v1/entities")
    assert params["entity_type"] == "eq.theme" and params["offset"] == 0
    assert headers["apikey"] == ANON_KEY
    assert headers["Authorization"] == f"Bearer {ANON_KEY}"
    assert headers["User-Agent"].startswith("m8-themes-sync/")
    assert c.requests_made == 1


def test_paginates(make_client):
    r2 = row(ROW_MICRO, id=2)
    c = make_client(FakeResp(200, [ROW_IOS, ROW_MICRO]),
                    FakeResp(200, [r2]), page_size=2)
    assert len(c.fetch_all()) == 3
    assert [call[1]["offset"] for call in c.session.calls] == [0, 2]


def test_skips_bad_rows(make_client):
    c = make_client(FakeResp(200, [ROW_IOS, row(ROW_MICRO, data="\\x00"),
                                   "junk"]))
    assert [t.name for t in c.fetch_all()] == ["IOS"]


def test_retries_then_succeeds(make_client):
    c = make_client(FakeResp(503), FakeResp(429, headers={"Retry-After": "7"}),
                    FakeResp(200, [ROW_IOS]))
    assert len(c.fetch_all()) == 1
    assert c.sleeps == [2.0, 7.0]


def test_gives_up_after_retries(make_client):
    c = make_client(*[FakeResp(503)] * 4)
    with pytest.raises(ThemesError):
        c.fetch_all()
    assert c.requests_made == 4


def test_connection_error_retried_then_raised(make_client):
    err = requests.ConnectionError("boom")
    c = make_client(err, err, err, err)
    with pytest.raises(requests.ConnectionError):
        c.fetch_all()
    assert c.sleeps == [2.0, 4.0, 8.0]


@pytest.mark.parametrize("resp", [FakeResp(401), FakeResp(200, {"a": 1}),
                                  FakeResp(200, ValueError("no json"))])
def test_unexpected_responses(make_client, resp):
    with pytest.raises(ThemesError):
        make_client(resp).fetch_all()


def test_key_from_env(monkeypatch):
    monkeypatch.setenv("M8_THEMES_KEY", "abc")
    assert ThemesClient(session=object()).api_key == "abc"
