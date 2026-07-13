FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --upgrade pip && pip install ".[postgres]"

EXPOSE 8000

CMD ["uvicorn", "egsd.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
