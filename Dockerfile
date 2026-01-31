FROM python:3.13.11-alpine3.23@sha256:2f607129b1b915a949320bf0c4831a73d1c1b1be663c2b1d8c93aa35a5f44a95

WORKDIR /app

# Install uv for faster dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.9.28-python3.13-alpine3.23 /uv /usr/local/bin/uv

RUN apk add --no-cache curl ca-certificates

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./
COPY .python-version ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY main.py ./

# Expose port
EXPOSE 8000

# Run the application with uvicorn
CMD ["uv", "run", "fastapi", "run", "main.py", "--forwarded-allow-ips=*", "--host", "0.0.0.0", "--port", "8000"]