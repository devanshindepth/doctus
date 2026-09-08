# Multi-stage build for Doctus Clearance Studio
# Stage 1: Build React + TypeScript frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python container
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python dependencies
COPY pyproject.toml ./
RUN uv pip install --system --no-cache \
    fastapi>=0.111 \
    "uvicorn[standard]>=0.29" \
    pydantic>=2.0 \
    pyyaml>=6 \
    c2pa-python>=0.37 \
    pillow>=11 \
    hatchling

# Copy application source and fixtures
COPY src/ ./src/
COPY fixtures/ ./fixtures/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/

# Copy compiled React frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Install doctus in editable / system mode
RUN uv pip install --system --no-deps -e .

EXPOSE 8080

# Run FastAPI backend serving both API and React SPA
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT}"]
