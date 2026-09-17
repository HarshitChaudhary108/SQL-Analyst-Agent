FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Force uv to use the base image's Python instead of downloading its own
ENV UV_PYTHON_PREFERENCE=only-system

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]