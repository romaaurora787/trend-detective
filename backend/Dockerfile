# Backend image for Google Cloud Run / Render / any container host.
# Build from the backend folder:  docker build -t trend-detective-api .
FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev
# Cloud Run sets $PORT (default 8080).
CMD ["sh", "-c", "uv run --no-sync uvicorn trend_detective.api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
