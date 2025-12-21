# Production Dockerfile using distroless image
# This creates a minimal, secure image for deployment
#
# Build: docker build -f docker/Dockerfile -t blocky-market-maker:prod .
# Run:   docker run --rm -v $(pwd)/.env:/app/.env blocky-market-maker:prod

# --- Stage 1: The Builder ---
FROM docker.io/python:3.11-slim-bookworm AS builder

# Install build-essential for C extensions
RUN apt-get update && \
    apt-get install -y build-essential --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set up a directory for our packages
WORKDIR /app
COPY requirements.txt .

# Install packages into a specific directory
RUN pip install --no-cache-dir --target="/app/packages" -r requirements.txt

# --- Stage 2: The Final Image ---
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

# Copy the installed packages from the builder
COPY --from=builder /app/packages /app/packages

# Copy your application code
COPY . .

# Tell Python where to find the packages and src modules
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/packages:/app/src"

# Run the bot via run.py entry point
# Note: distroless python image uses /usr/bin/python3.11 as entrypoint
CMD ["run.py"]

