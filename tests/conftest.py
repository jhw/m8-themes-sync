import pytest

# Rows exactly as the site's API returns them (bytea as "\x<hex>").
ROW_MICRO = {
    "created_at": "2026-10-08T05:33:19.799428+00:00",
    "data": "\\x4d3856455253494f4e0002010020000008210a00857b60655b9adfdfdfff4d00ffe000ff9fff00ffc3758bff00ff50ffe000ff3070",
    "entity_type": "theme", "id": 420, "name": "M8CROFLORA",
    "updated_at": "2026-10-08T05:33:19.799428+00:00",
    "user_id": "55340270-c2d6-4b56-bcd3-0fdb25c835e6",
    "user_name": "microflora"}
ROW_IOS = {
    "created_at": "2026-09-14T01:07:59.667685+00:00",
    "data": "\\x4d3856455253494f4e0002010020070c1a151f3638506a38506ae2e9f17fff9500ff9c00fffcff3f8f00fffc5fffdfc8ff00ff0a00",
    "entity_type": "theme", "id": 418, "name": "IOS",
    "updated_at": "2026-09-14T01:07:59.667685+00:00",
    "user_id": "61225eb5-ccd5-48d5-9268-fac8fe8c6824",
    "user_name": "euphemism"}


def row(base, **kw):
    d = dict(base)
    d.update(kw)
    return d


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    """Returns queued responses in order and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def make_client():
    from m8_themes_sync.client import ThemesClient

    def _make(*responses, **kw):
        sleeps = []
        c = ThemesClient(session=FakeSession(*responses), delay=0,
                         sleep=sleeps.append, **kw)
        c.sleeps = sleeps
        return c
    return _make
