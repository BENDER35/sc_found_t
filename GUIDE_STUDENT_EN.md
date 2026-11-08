# sc-found-t Student Guide

## Objective
Learn to use `sc-found-t` to find public contact emails from YouTube and Twitch channels for the purpose of proposing professional collaborations.

## What does the script do?
The script explores public pages of YouTube and Twitch channels to extract email addresses that creators have published for business contact. It does not use private APIs, does not guess addresses, and does not purchase lists.

## Typical Use Cases

### 1. Searching contacts from a specific channel
```bash
# Single channel
.venv/bin/python run.py @channel_name

# Multiple channels separated by spaces
.venv/bin/python run.py "@channel1 @channel2 twitch.tv/streamer"
```

### 2. Searching by keyword
```bash
# Search for channels related to a topic
.venv/bin/python run.py --search "spanish cooking"

# With audience filters
.venv/bin/python run.py --search "minecraft" --min-subs 10000

# Only YouTube, sorting by views
.venv/bin/python run.py --search "tutorials" --search-platform youtube --search-sort views
```

### 3. Filtering only business emails
```bash
.venv/bin/python run.py @channel --only-business
```
This leaves only emails with roles like: `contact`, `collaborations`, `press`, `management`.

## Main Components

### Data Input
- **Standalone channels**: `@handle`, full `URL`, or `twitch.tv/username`
- **File**: A text file with one channel per line (the `input/example.txt` includes examples)
- **Keyword search**: Use `--search "your topic"`

### Most Useful Options for Beginners

| Option | When to use it |
|---|---|
| `--no-crawl` | You only want emails from the bio, without visiting websites |
| `--min-subs 5000` | Only channels with at least 5,000 subscribers |
| `--only-business` | You only want professional emails |
| `--delay 2.0` | If you see many timeouts, increase the delay |

### Recommended Workflow

1. **First search by keyword** to discover channels:
   ```bash
   .venv/bin/python run.py --search "mexican cooking" --min-subs 1000
   ```

2. **Review the generated list** (`busqueda_canales.csv` in the `out/` folder)

3. **Run full analysis** of the selected channels:
   ```bash
   .venv/bin/python run.py input/my_channels.txt --only-business
   ```

4. **Review results** in `contactos_20261105_1234.csv`

## How Filtering Works

The script scores each found email:

- `mailto:` declared on the website: +25 points
- `colaborations`/`partnerships` section: +70 points
- `contact`/`hello` text: +60 points
- `press` section: +55 points
- `management` section: +50 points
- Generic email: +20 points

Then it deduplicates, keeping only one email per address (the one with highest score).

It also automatically filters out:
- `noreply@`, `no-reply@`, `donotreply@` addresses
- `example.com`, `tuemail@`, `nombre@ejemplo.com` domains
- Emails from domains that aren't the creator's (unless they are Gmail, Outlook, etc.)

## Practical Tips

### For YouTube
- No special basic configuration required
- If YouTube asks for bot verification, use `--cookies-from-browser firefox`
- Search order is: description → About tab → external website

### For Twitch
- **You need credentials** from developer.twitch.tv
- Configure `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` as environment variables
- Twitch search only finds the name, not the channel's topic
- It's better to search the channel on YouTube first, then use Twitch just to confirm

### Avoiding Problems
- **Don't remove `--contact-email`** from the User-Agent unless you'll actually identify yourself
- Use `--delay` higher if you see many "too many requests" errors
- `--max-domains-total 60` is the global limit of websites that will be visited
- Cache (`--cache-ttl 168`) saves results for 7 days to avoid re-working

## Legal and Ethics

- Only visits public pages
- Respect `robots.txt` (unless you explicitly disable it)
- Emails are business published for contact
- Always include unsubscribe in your first email
- Don't make mass sends without consent

## What Will You Learn?

- How to work with Python command-line tools
- Handling YouTube and Twitch APIs (official and unofficial)
- Extraction and classification of web page data
- Responsible scraping best practices
- Data structure and result processing