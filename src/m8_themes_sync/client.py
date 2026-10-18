from __future__ import annotations

import logging
import os
import random
import time
from typing import Callable, List, Optional

import requests

from . import __version__
from .models import BadTheme, Theme

log = logging.getLogger("m8_themes_sync")

# m8them.es is a single-page app over a Supabase (PostgREST) database. This is
# the public, read-only "anon" key that the site's own JavaScript ships to every
# browser; override with $M8_THEMES_KEY / --api-key if the site ever rotates it.
BASE_URL = "https://iwwnybraapmglftdybbr.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml3d255YnJhYXBtZ2xmdGR5YmJyIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE2Njg2NDM2NTAsImV4cCI6MTk4NDIxOTY1MH0."
    "eGowH9ZF-elCf-195uGd5MBU7b98cCatJkjrLSuHpbU")
USER_AGENT = f"m8-themes-sync/{__version__} (personal theme mirror)"
PAGE_SIZE = 1000
RETRY_STATUS = {429, 500, 502, 503, 504}
COLUMNS = "id,name,user_id,user_name,created_at,updated_at,data"


class ThemesError(Exception):
    """The site returned something we did not expect."""


def _retry_after(resp) -> Optional[float]:
    value = (getattr(resp, "headers", None) or {}).get("Retry-After")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class ThemesClient:
    """Polite client for the database behind m8them.es.

    One request returns every theme *including its file contents* (a theme is
    only 53 bytes), so a whole sync is normally a single HTTP request, plus
    one more per 1000 themes. It still paces requests, and on 429/5xx or a
    connection error backs off exponentially (honouring Retry-After).
    """

    def __init__(self, base_url: str = BASE_URL, api_key: Optional[str] = None,
                 session=None, delay: float = 1.0, jitter: float = 0.25,
                 timeout: float = 30.0, retries: int = 3,
                 backoff: float = 2.0, max_wait: float = 60.0,
                 page_size: int = PAGE_SIZE,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("M8_THEMES_KEY") or ANON_KEY
        self.session = session if session is not None else requests.Session()
        self.delay = delay
        self.jitter = jitter
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.max_wait = max_wait
        self.page_size = page_size
        self._sleep = sleep
        self._clock = clock
        self._last: Optional[float] = None
        self.requests_made = 0

    def _pace(self) -> None:
        if self._last is None:
            return
        gap = self.delay * (1 + random.uniform(0, self.jitter))
        wait = self._last + gap - self._clock()
        if wait > 0:
            log.debug("pausing %.2fs between requests", wait)
            self._sleep(wait)

    def _get(self, url: str, params: Optional[dict] = None):
        headers = {"User-Agent": USER_AGENT, "apikey": self.api_key,
                   "Authorization": f"Bearer {self.api_key}"}
        attempt = 0
        while True:
            self._pace()
            log.debug("GET %s %s", url, params or "")
            try:
                self.requests_made += 1
                resp = self.session.get(url, params=params,
                                        timeout=self.timeout, headers=headers)
            except requests.RequestException as e:
                self._last = self._clock()
                if attempt >= self.retries:
                    raise
                wait = min(self.backoff * 2 ** attempt, self.max_wait)
                attempt += 1
                log.warning("request failed (%s); retry %d/%d in %.0fs",
                            e.__class__.__name__, attempt, self.retries, wait)
                self._sleep(wait)
                continue
            self._last = self._clock()
            if resp.status_code in RETRY_STATUS and attempt < self.retries:
                wait = min(_retry_after(resp)
                           or self.backoff * 2 ** attempt, self.max_wait)
                attempt += 1
                log.warning("server said HTTP %d; backing off %.0fs "
                            "(retry %d/%d)", resp.status_code, wait,
                            attempt, self.retries)
                self._sleep(wait)
                continue
            return resp

    def fetch_all(self) -> List[Theme]:
        """Every theme on the site, oldest first. Unusable rows are skipped."""
        themes: List[Theme] = []
        skipped = 0
        offset = 0
        while True:
            r = self._get(f"{self.base_url}/rest/v1/entities", params={
                "select": COLUMNS, "entity_type": "eq.theme",
                "order": "id.asc", "offset": offset,
                "limit": self.page_size})
            if r.status_code != 200:
                raise ThemesError(f"themes request returned HTTP "
                                  f"{r.status_code}")
            try:
                rows = r.json()
            except ValueError as e:
                raise ThemesError(f"themes response was not JSON: {e}") from e
            if not isinstance(rows, list):
                raise ThemesError("themes response had an unexpected shape")
            for row in rows:
                try:
                    themes.append(Theme.from_api(row))
                except (BadTheme, AttributeError, TypeError) as e:
                    skipped += 1
                    log.warning("ignored a theme row: %s", e)
            if len(rows) < self.page_size:
                break
            offset += self.page_size
        if skipped:
            log.warning("ignored %d unusable theme rows", skipped)
        return themes
