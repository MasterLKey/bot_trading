# Dashboard: build React SPA, serve via FastAPI
FROM node:20-alpine AS frontend
WORKDIR /web
COPY dashboard/web/package.json ./
RUN npm install
COPY dashboard/web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN useradd -m -u 1000 bot && mkdir -p /app/data && chown -R bot:bot /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ ./bot/
COPY dashboard/api/ ./dashboard/api/
COPY --from=frontend /web/dist ./dashboard/web/dist
USER bot
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "dashboard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
