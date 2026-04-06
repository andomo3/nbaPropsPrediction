FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Cache bust: increment when forced rebuild is needed
ARG CACHEBUST=2
COPY . /app

# Collect static files
RUN python backend/manage.py collectstatic --noinput

CMD ["sh", "-c", "gunicorn backend.wsgi:application --chdir /app/backend --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --env DJANGO_SETTINGS_MODULE=backend.settings"]
