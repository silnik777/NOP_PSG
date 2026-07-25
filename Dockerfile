FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY --from=web /web/dist ./web/dist

RUN pip install --upgrade pip && pip install ".[postgres]"

EXPOSE 8000

CMD ["uvicorn", "egsd.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
