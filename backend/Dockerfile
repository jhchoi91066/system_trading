# =============================================================================
# Multi-stage Docker build for Bitcoin Trading Bot Backend
# =============================================================================

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim as runtime

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY . .

# Create logs directory and set permissions
RUN mkdir -p logs && \
    chown -R appuser:appuser /app && \
    chmod +x *.py

# Switch to non-root user
USER appuser

# Add user's local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port
EXPOSE 8000

# Default command - can be overridden
CMD ["python", "main.py"]