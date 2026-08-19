FROM python:3.11-slim

WORKDIR /app

# Unbuffered Python output (for Docker logs)
ENV PYTHONUNBUFFERED=1

# Enable web auth mode for Docker (binds OAuth to 0.0.0.0)
ENV WEB_AUTH=true

# Bind on all interfaces inside the container so the published port is
# reachable. Because this is a non-loopback bind, the app requires an API
# token: set API_TOKEN to pin one, otherwise a random token is generated at
# startup and printed to the container logs.
ENV HOST=0.0.0.0

# Install uv for faster package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies only (not the app itself)
RUN uv sync --frozen

# Copy application
COPY . .

# Remove any existing tokens (user should mount their own)
RUN rm -f token.json

# Expose ports: 8766 for web UI, 8767 for OAuth callback
EXPOSE 8766 8767

# Run with uvicorn (FastAPI)
CMD ["uv", "run", "python", "main.py"]
