# Energy Agent — Ingestion Layer

Polls RSS feeds and YouTube channels related to Oil, Natural Gas, and Uranium/Nuclear energy.
Runs as a persistent Python process on Railway with SQLite for state.

## Project Structure

```
energy-agent/
├── main.py                  # Entrypoint
├── config.py                # All feed/channel sources defined here
├── requirements.txt
├── Dockerfile
├── .env.example
├── db/
│   └── database.py          # Schema + all DB operations
├── ingestion/
│   ├── rss.py               # RSS fetch, parse, dedup, store
│   └── youtube.py           # YouTube API + transcript fetch
├── scheduler/
│   └── jobs.py              # APScheduler job definitions
└── utils/
    └── fingerprint.py       # Content hashing for dedup
```

## Setup

### 1. Clone and install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Get a YouTube Data API key
- Go to console.cloud.google.com
- Create a project → Enable "YouTube Data API v3"
- Create an API key → paste into .env

### 4. Run locally
```bash
python main.py
```

## Railway Deployment

1. Push this repo to GitHub
2. Create a new Railway project → Deploy from GitHub repo
3. Add a Volume mounted at `/data`
4. Set environment variables in Railway dashboard (copy from .env.example)
5. Deploy — Railway will build from the Dockerfile automatically

## Polling Schedule

| Source Type | Interval |
|-------------|----------|
| RSS Feeds (15 sources) | Every 15 minutes |
| YouTube Channels (3) | Every 30 min, self-gated by each channel's posting window |

## Adding Sources

Edit `config.py` only — no other files need to change.

- **RSS**: Add an entry to `RSS_FEEDS` list
- **YouTube**: Add an entry to `YOUTUBE_CHANNELS` list with the channel's `channel_id`
  - Find channel IDs at: `https://www.youtube.com/@channelname/about` (view page source, search for `channelId`)

## Database

SQLite at the path set by `DB_PATH` env var (default: `/data/energy_agent.db`).

Key tables:
- `rss_items` — all ingested RSS entries
- `youtube_items` — all ingested videos + transcripts
- `source_poll_log` — per-poll audit log with error tracking
