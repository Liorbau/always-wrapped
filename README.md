<div align="center">
  <img src="logo.png" alt="Always Wrapped Logo" width="100%">
  
  <p>
    <strong>Don't wait 365 days to stay wrapped.</strong>
  </p>

  <p>
    <a href="https://always-wrapped.onrender.com">View Live Demo</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" />
    <img src="https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white" />
    <img src="https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white" />
    <img src="https://img.shields.io/badge/Spotify_API-1ED760?style=for-the-badge&logo=spotify&logoColor=white" />
    <img src="https://img.shields.io/badge/Render-%2346E3B7.svg?style=for-the-badge&logo=render&logoColor=white" />
    <img src="https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white" />
    <img src="https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white" />
    <img src="https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E" />
</p>
</div>

<br />

A real-time Spotify listening history tracker and dashboard. Unlike the annual Spotify Wrapped, this runs 24/7, and provides a live "Always On" dashboard of your music habits using a self-healing background collector.

## Quick setup
### 1. Installation
Clone the repo and install dependencies:
pip install -r requirements.txt

### 2. Spotify Keys
1.  Create an App on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2.  In **Settings**, set the **Redirect URI** to `http://127.0.0.1:8888/callback`.
3.  Create a `.env` file in the project folder and paste your keys:
    ```env
    SPOTIFY_CLIENT_ID=your_id_here
    SPOTIFY_CLIENT_SECRET=your_secret_here
    SPOTIFY_REDIRECT_URI=[http://127.0.0.1:8888/callback](http://127.0.0.1:8888/callback)
    ```

### 3. Usage
**Run Locally:**
To start the dashboard and tracker on your own machine:
python server.py
Visit http://localhost:5000 to see your stats.

**Run 24/7 (Optional):**
 To keep collecting data while your computer is off, deploy this code to any cloud provider and add your .env keys to their environment settings.