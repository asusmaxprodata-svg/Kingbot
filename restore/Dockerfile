# KANG_BOT Dockerfile (build 7a0df6abee)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (opsional, tambah bila perlu TA-Lib, etc)
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl git &&     rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements_fix_clean_7a0df6abee.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r /app/requirements.txt

# App code
COPY . /app

# Non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Default command (overridden by docker-compose)
CMD ["python","run.py","--mode","live"]
