FROM python:3.13-alpine

WORKDIR /app

# Unbuffered Python output (for Docker logs)
ENV PYTHONUNBUFFERED=1

# Enable web auth mode for Docker (binds OAuth to 0.0.0.0)
ENV WEB_AUTH=true

# Pick up security updates published after the base image was tagged
RUN apk upgrade --no-cache

# Install uv for faster package management (musl build, to match the alpine base)
COPY --from=ghcr.io/astral-sh/uv:alpine /usr/local/bin/uv /usr/local/bin/uv

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
