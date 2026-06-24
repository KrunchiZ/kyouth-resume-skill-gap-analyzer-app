FROM python:3.14-slim

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project

# Copy sql and data files
COPY sql/ ./sql/

# Copy source code
COPY src/ ./src/

EXPOSE 8001

ENTRYPOINT ["uv", "run", "uvicorn"]
CMD ["--app-dir", "src", "--host", "0.0.0.0", "--port", "8001", "app:app"]