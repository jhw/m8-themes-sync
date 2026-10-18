# m8-themes-sync

Mirror Dirtywave M8 themes (`.m8t`) from [m8them.es](https://m8them.es/),
grouped by author, keep a local cache, and copy them to an M8. A sibling of
`matey-sync`, built the same way.

## Install

    cd /Users/jhw/work/m8-themes-sync
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e '.[dev]'

## Use

    m8-themes-sync --list                # the full catalogue, grouped by author; writes nothing
    m8-themes-sync                       # cache every theme under tmp/<author>/
    m8-themes-sync dracula               # only themes whose name or author contains "dracula"
    m8-themes-sync --dry-run             # show what would change
    m8-themes-sync --m8                  # ...then copy to /Volumes/M8/Themes/m8themes/<author>/
    m8-themes-sync -v                    # also log every HTTP request

Run it again later and only new or changed themes are written. Exit code:
0 ok, 1 something failed.

## Where things go

The cache (default `<project>/tmp/`, git-ignored; override with `--cache-dir`
or `$M8_THEMES_SYNC_CACHE`) is `{author}/{THEME}.m8t`:

    tmp/beat-pharmaxy/BELLAGIO.m8t
    tmp/tekfrenz/TKF.m8t
    tmp/.index.json                 <- site id -> where each theme is stored

On the M8, the same layout goes under `Themes/m8themes/`:

    /Volumes/M8/Themes/
        *.m8t                       stock themes + any you put there: never touched
        defaults/                   copies of the nine stock themes (backup)
        m8themes/<author>/*.m8t     written by this tool
        wol/                        your own hand-made themes

The tool only ever writes inside `Themes/m8themes/` (`--m8-subdir` to change),
skips files already identical on the card, and requires `Themes/` to exist.

- Author folder names are folded to ASCII (the M8 only displays ASCII):
  `vincent--🤖ᶜᴴᴼᴺᴷᴱᴿᵇᵒᵗ` becomes `vincent--cHONKERbot`; an author with nothing
  usable left becomes `user-<id>`. Case-clashing folders are disambiguated.
- Two themes with the same name by the same author get ` (<site id>)` added.
- If a theme is renamed or moved to another author on the site, the cached
  copy is moved too, not duplicated.

## How it works

m8them.es is a single-page app over a Supabase (PostgREST) database, readable
without logging in using the public "anon" key its own JavaScript ships:

| Request | Returns |
|---|---|
| `GET /rest/v1/entities?entity_type=eq.theme&order=id.asc&limit=1000&offset=N` | JSON rows: `id, name, user_id, user_name, created_at, updated_at, data` |

`data` is the whole `.m8t` file as hex (`\x4d38...`, 53 bytes), so one request
fetches the entire catalogue (314 themes at the time of writing); there are no
per-theme downloads. The client is still polite: one request at a time,
`--delay` seconds apart (default 1s), exponential back-off on 429/5xx or
connection errors, honest User-Agent. If the site rotates its key, set
`$M8_THEMES_KEY`.

## Tests

    pytest

Fake HTTP session and temporary directories only: no network, no real M8.
