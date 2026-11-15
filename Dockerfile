# The whole app in one container: the API and the built website on one address. The port comes from the PORT
# variable that hosts such as Render set (7860 when it is not set). Build and run locally:
#   docker build -t chn . && docker run -p 7860:7860 chn

# 1. Build the website. An empty API address makes it call the same address it was opened from.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build

# 2. The API, with only the data and models it reads.
FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --chown=user backend/app backend/app
COPY --chown=user data/thresholds.json data/thresholds.json
COPY --chown=user data/content data/content
COPY --chown=user data/synthetic data/synthetic
COPY --chown=user data/processed data/processed
COPY --chown=user models models
COPY --from=web --chown=user /web/dist frontend/dist
RUN mkdir -p data/local && chown user data/local
USER user
ENV CHN_STATIC_DIR=/app/frontend/dist
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-7860}"]
