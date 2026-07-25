<div align="center">
  <img src="static/logo.png" alt="Always Wrapped Logo" width="100%">

  <p>
    <strong>Don't wait 365 days to stay wrapped.</strong>
  </p>

  <p>
    <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" />
    <img src="https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white" />
    <img src="https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white" />
    <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" />
    <img src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" />
    <img src="https://img.shields.io/badge/Spotify_API-1ED760?style=for-the-badge&logo=spotify&logoColor=white" />
    <img src="https://img.shields.io/badge/Render-%2346E3B7.svg?style=for-the-badge&logo=render&logoColor=white" />
    <img src="https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white" />
    <img src="https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white" />
    <img src="https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E" />
    <img src="https://img.shields.io/badge/LiteLLM-6E56CF?style=for-the-badge" />
    <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
    <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
    <img src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white" />
  </p>
</div>

<br />

A real-time Spotify listening tracker and dashboard. Unlike the annual Spotify Wrapped, this runs 24/7 and keeps a live view of your listening habits with a background collector.

Under the hood it is a multi-agent system: a listening analyzer and playlist-building DJ you can chat with on the web or Telegram.

Live demo: https://always-wrapped.onrender.com

## Quick setup

```bash
git clone https://github.com/Liorbau/always-wrapped.git
cd always-wrapped
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in your keys — see below
./venv/bin/python server.py
```

Open http://localhost:5000

### Environment

Copy [`.env.example`](.env.example) and fill in at least:

- **Spotify** — create an app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and set the redirect URI to `http://127.0.0.1:8888/callback`
- **Database** — omit `DATABASE_URL` for local SQLite, or point it at any Postgres (Supabase, Neon, etc.)
- **LLM** — `OPENAI_API_KEY` (or another LiteLLM provider) for the DJ and Wrapped styling

Everything else in `.env.example` is optional (Telegram, calendar, spend cap, deploy settings).

### Local data without waiting

Spotify only exposes your last ~50 plays on first connect. To populate a local dashboard immediately:

```bash
DATABASE_URL= ./venv/bin/python scripts/seed_local_db.py
```

### Docker

```bash
docker build -t always-wrapped .
docker run --env-file .env -p 5000:5000 always-wrapped
```

### Tests

```bash
./venv/bin/python tests/test_ingest.py   # any tests/test_*.py works
```
