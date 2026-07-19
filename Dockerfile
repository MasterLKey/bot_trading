FROM python:3.12-slim

WORKDIR /app

RUN useradd -m -u 1000 bot && mkdir -p /app/data && chown -R bot:bot /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY pytest.ini .

USER bot
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot", "stream", "--mode", "advisory"]
