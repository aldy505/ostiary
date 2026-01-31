FROM python:3.13-alpine

WORKDIR /app

# Install uv for faster dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

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