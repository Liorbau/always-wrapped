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

  <p>
    <strong>Live demo:</strong> <a href="https://always-wrapped.onrender.com/">https://always-wrapped.onrender.com/</a>
  </p>
</div>

<br />

A real-time Spotify listening history tracker and dashboard. Unlike the annual Spotify Wrapped, this runs 24/7, and provides a live "Always On" dashboard of your music habits using a self-healing background collector.

Under the hood it's a multi-agent system — a DJ you can chat with to build playlists, plus headless agents that learn from your listening and plan ahead (web or Telegram).

## Quick setup
### 1. Installation
Clone the repo and install dependencies:
pip install -r requirements.txt

### 2. Spotify Keys
1.  Create an App on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2.  In **Settings**, set the **Redirect URI** to `http://127.0.0.1:8888/callback`.
3.  Copy `.env.example` to `.env` and fill in your keys:
    ```env
    SPOTIFY_CLIENT_ID=your_id_here
    SPOTIFY_CLIENT_SECRET=your_secret_here
    SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
    OPENAI_API_KEY=sk-...          # DJ, Wrapped styling, and other agents
    # DATABASE_URL=postgresql://... # optional — omit for local SQLite
    ```
    See `.env.example` for Telegram, calendar, and deploy options.

### 3. Usage
**NOTE: Spotify only provides access to your last 50 played tracks, your statistics will begin with these.**

**Run Locally:**
To start the dashboard and tracker on your own machine:
python server.py
Visit http://localhost:5000 to see your stats.

**Run 24/7 (Optional):**
 To keep collecting data while your computer is off, deploy this code to any cloud provider and add your .env keys to their environment settings.
