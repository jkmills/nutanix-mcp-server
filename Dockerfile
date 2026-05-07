FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY src/ src/

# Install dependencies
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Default: HTTP transport on port 8000
EXPOSE 8000

ENV NUTANIX_HOST=""
ENV NUTANIX_PORT="9440"
ENV NUTANIX_USERNAME=""
ENV NUTANIX_PASSWORD=""
ENV NUTANIX_VERIFY_SSL="true"

ENTRYPOINT ["uv", "run", "nutanix-mcp", "--http"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
