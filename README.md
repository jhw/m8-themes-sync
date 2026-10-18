# m8-themes-sync

Mirror Dirtywave M8 themes (`.m8t`) from [m8them.es](https://m8them.es/),
keep a local cache, and copy them to an M8. A sibling of
`matey-sync`, built the same way.

## Install

    cd /Users/jhw/work/m8-themes-sync
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e '.[dev]'

## Use

    m8-themes-sync --list                # the full catalogue (grouped by author for reading); writes nothing
    m8-themes-sync                       # cache every theme under tmp/
    m8-themes-sync dracula               # only themes whose name or author contains "dracula"
    m8-themes-sync --dry-run             # show what would change
    m8-themes-sync --m8                  # ...then copy to /Volumes/M8/Themes/m8themes/
    m8-themes-sync -v                    # also log every HTTP request

Run it again later and only new or changed themes are written. Exit code:
0 ok, 1 something failed.

## Where things go

The cache (default `<project>/tmp/`, git-ignored; override with `--cache-dir`
or `$M8_THEMES_SYNC_CACHE`) is one flat folder of `{THEME}.m8t` files:

    tmp/BELLAGIO.m8t
    tmp/TKF.m8t
    tmp/.index.json                 <- site id -> file, plus the author

On the M8, the same layout goes under `Themes/m8themes/`:

    /Volumes/M8/Themes/
        *.m8t                       stock themes + any you put there: never touched
        defaults/                   copies of the nine stock themes (backup)
        m8themes/*.m8t              written by this tool (flat: browse by name)
        custom/                     your own hand-made themes

`m8-themes-sync --organise [--dry-run]` tidies the root of `Themes/`: the nine
stock themes go to `defaults/`, any other root `.m8t` with a byte-identical copy
in a subfolder is removed, and everything else is left and listed. Nothing is
deleted unless the same bytes survive elsewhere on the card.

The tool otherwise only ever writes inside `Themes/m8themes/` (`--m8-subdir` to change),
skips files already identical on the card, and requires `Themes/` to exist.

- Files are flat, named after the theme. If two themes share a name (the
  site has a few, e.g. SUNSET), the later one becomes `NAME (author).m8t`
  (author folded to ASCII, since the M8 only displays ASCII), or
  `NAME (author, id).m8t` if that is taken too. `--list` still groups by
  author so you can see who made what, and the cache index records the author.
- If a theme is renamed on the site, the cached copy is renamed too, not
  duplicated.
- Moving from an older author-folder layout: `--m8` removes any `.m8t` in a
  sub-folder of `Themes/m8themes/` whose identical copy now sits at the top
  level, then empties folders; a file with no identical flat copy is never
  touched. The cache migrates itself the same way.

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
