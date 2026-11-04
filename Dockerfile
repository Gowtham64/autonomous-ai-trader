# Multi-Agent Autonomous Trading System
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr and writing pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Install system dependencies including PostgreSQL client libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install lightweight CPU-only PyTorch first to avoid multi-GB GPU bloat
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy dependency definition
COPY pyproject.toml .

# Install project dependencies
RUN pip install --no-cache-dir -e .

# Copy source tree
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data

EXPOSE 8000

# Default command launches FastAPI and Dashboard
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

