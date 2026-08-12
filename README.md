# Honkai: Star Rail Wish Tracker — Discord Bot

A Discord bot that imports a player's *Honkai: Star Rail* warp (gacha) history directly from
HoyoverseTMs API and tracks pity, 50/50 status, and pull statistics per banner.

## Features

- **`/importwarp <url>`** — imports a player's full warp history from their in-game warp
  history URL and stores it per-user, per-banner in a local SQLite database.
- **`!stats`** — shows current pity counters, guaranteed status (50/50 for Event banners,
  75/25 for Weapon banners), and pulls remaining until the next 5★/4★.
- **`!average`** — shows average pity across all recorded 5★ pulls, per banner.
- **`!warp <banner>`** — paginated (reaction-based) browser through full pull history for a
  given banner.
- **`!clear`** — clears a user's stored history.

## How it works

- Uses the public Hoyoverse `getGachaLog` endpoint, paginating with `end_id` until the full
  history is retrieved.
- Warp history is parsed to reconstruct pity counters and guarantee state by walking pulls
  chronologically and resetting counters on each 5★/4★ hit.
- Data is stored locally in SQLite, keyed by `(user_id, banner_type)`.

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your own Discord bot token and application ID:
   ```bash
   cp .env.example .env
   ```
3. Run the bot:
   ```bash
   python bot.py
   ```

## Tech stack

Python · discord.py · SQLite · Hoyoverse API

## Notes

This project was built for personal/community use and interacts with an unofficial,
publicly-accessible Hoyoverse endpoint used by other warp-tracking tools in the community.
It is not affiliated with or endorsed by HoYoverse.
