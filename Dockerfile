# Runs anywhere a container runs: Render, Fly, Railway, Cloud Run, plain Docker.
# The app binds $PORT (default 5000) and needs no platform-specific SDK.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000

WORKDIR /app

# psycopg2-binary ships wheels, so no build toolchain is needed at image time.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root, and it must own the working directory: the app writes OAuth token
# caches and run trajectories next to the code.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["python", "server.py"]
