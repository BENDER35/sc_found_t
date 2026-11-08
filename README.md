# sc-found-t

Searches for **public contact emails** from YouTube and Twitch channels to propose collaborations. It only reads what the creator already publishes: the channel bio, the "Contact" link YouTube shows in the *About* tab, and the public contact pages of the websites the creator links to.

No paid APIs, no guessing mailboxes, no purchased lists.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# A single channel
.venv/bin/python run.py @mkbhd

# Multiple channels separated by commas or spaces
.venv/bin/python run.py "@mkbhd @DotCSV twitch.tv/ibai"

# A file with one channel per line
.venv/bin/python run.py input/example.txt -o out

# Only the bio, without visiting external websites
.venv/bin/python run.py @mkbhd --no-crawl

# Only contact/business emails, not personal accounts
.venv/bin/python run.py input/ejemplo.txt --only-business
```

```bash
# Search by keyword and extract emails from what appears
.venv/bin/python run.py --search "spanish cooking"

# Only one platform, sorting by audience and keeping the big ones
.venv/bin/python run.py --search "minecraft español" \
    --search-platform youtube --search-sort views --min-subs 50000

# Searching for channels, not videos (deduplicates by channel)
.venv/bin/python run.py --search "recipes" --search-type channel
```

You can also combine with standalone targets: what comes out of `--search` is analyzed together with the channels you indicate.

Output in `out/`: `contactos_<date>.csv`, `.json` and a `.md` with the report. When using `--search`, a `busqueda_canales.csv` with the found channels is also saved, so you can review the list before proceeding.

## Keyword Search

**YouTube** requires nothing: `yt-dlp` queries the public results page and returns the channel for each video, which is deduplicated before spending more resources. `--search-sort` changes the order (relevance, views, date) and `--search-type channel` filters by channel type instead of video.

**Twitch** does need credentials, because there's no public search without a token. Register at <https://dev.twitch.tv/console/apps> and export:

```bash
export TWITCH_CLIENT_ID=...
export TWITCH_CLIENT_SECRET=...
```

It's a server-to-server app, not the account of any creator. The token comes from `client_credentials` and doesn't access private data. Without those variables, `--search` still works on YouTube and warns that Twitch is left out.

## Options

| Flag | What it does |
|---|---|
| `-s, --search` | Keyword: discovers channels before searching emails |
| `--search-platform` | `youtube`, `twitch` or `todos` |
| `--search-sort` | `relevance`, `views` or `date` |
| `--search-type` | `video` (dedup by channel) or `channel` |
| `--search-limit` | Maximum channels per platform (40) |
| `--live-only` | On Twitch, only those currently live |
| `--min-subs N` | Does not track channels below N subscribers |
| `-o, --outdir` | Output folder (default `out/`) |
| `-c, --concurrency` | Channels in parallel (4) |
| `--delay` | Seconds between requests to same domain (1.5) |
| `--max-pages` | Pages per domain (6) |
| `--max-domains` | Domains per creator (5) |
| `--max-domains-total` | Global limit of domains in whole execution (60) |
| `--no-crawl` | Only searches in the bio, does not visit websites |
| `--only-business` | Leaves only `contact`, `collaborations`, `press`, `management` |
| `--min-score N` | Filters by minimum score |
| `--any-domain` | Accepts emails from third parties found on platforms (more noise) |
| `--ignore-robots` | Ignores `robots.txt` on external sites |
| `--cache-ttl` | Cache hours in `.cache/` (168) |
| `--contact-email` | Your email; goes in the User-Agent so you can be identified |
| `--cookies-from-browser` | `firefox`, `chrome`, `brave`... if YouTube asks for verification |

## Where it searches, and in what order

1. **Channel description** (YouTube and Twitch). If you searched by keyword, this is the first thing looked at for each result.
2. **YouTube `/about` tab**, which is where the creator's real contact link is located (what YouTube calls *business inquiries*) and the rest of its links section.
3. **External sites** the creator links to: first those that usually have declared contact (Patreon, Ko-fi, Linktree, About.me, Buy Me a Coffee...) and then their own website, testing `/contacto`, `/press`, `/colaboraciones`, `/partnerships`, `/sponsors`, `/booking`, `/management`...
4. Manually written emails to avoid bots: `nombre (at) gmail (dot) com`.

## How it filters

- Discards `noreply@`, `example.com`, `tuemail@`, `nombre@ejemplo.com`.
- Discards emails whose domain is not from the visited site, unless they are from a consumer provider (gmail, hotmail...) or a declared `mailto:`. This removes the noise from Patreon or Zendesk support portals.
- Scores each contact: `mailto:` declared +25, `colaboraciones/`partnerships` 70, `contacto`/`hola` 60, `prensa` 55, `gestión` 50, generic 20.
- Deduplicates by email keeping the one with highest score.

## Label

The script comes with `--contact-email` in the User-Agent
(`sc-found-t/1.0 (+collaboration-outreach bot; contact: YOUR-EMAIL-ACA)`).
It's the honest thing: the site administrator can see who you are and ask you to stop. Don't remove it if you won't identify yourself.

## Worth Knowing Limits

- **Twitch does not provide channel links.** Its `/about` is rendered in JavaScript and the public endpoint only returns the bio. If the streamer doesn't put an email in the bio, there will be no result; it's advisable to pass their YouTube channel or their website.
- **Twitch search only sees the name, not the topic.** Its official API compares with the login or the channel name, so search well who goes by their channel name (`cocinacarmen`), not who makes recipes with another name. For that, search on YouTube and cross-reference with the creator's website.
- **`--min-subs` does not filter the output list**, it only decides who to track: subscribers are only known when resolving each channel. In Twitch there's no follower data, so the filter doesn't discard anything there.
- **YouTube** may ask for age or bot verification. If that happens, use `--cookies-from-browser firefox`.
- **Does not validate that the mailbox exists.** All come from public pages, but check the domain before writing: `hola@midominio.com` on a website that isn't the creator's usually is the support ticket of a payment provider.
- **Personal emails (`nombre.apellido@gmail.com`) are marked as `sin_clasificar`.** Use `--only-business` to keep professional mailboxes.

## Legal and ethics

- Only visits public pages, respecting `robots.txt` (unless you explicitly disable it) and with a delay per domain.
- Contact data **published for business contact**. Nothing from filtered records, purchased databases or guessed mailboxes.
- Always include an unsubscribe link in your first email and do not make massive sends without consent.