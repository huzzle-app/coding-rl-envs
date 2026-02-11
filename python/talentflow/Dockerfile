# TalentFlow Django Debug Environment
# Terminal Bench v2 - Django Full Stack RL Environment
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies including git for version control
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Initialize git repo for state management (RL reset functionality)
RUN git config --global user.email "agent@talentflow.test" && \
    git config --global user.name "RL Agent" && \
    git init && \
    git add -A && \
    git commit -m "Initial buggy state" || true

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
