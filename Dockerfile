FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=backend.settings

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Cache bust: increment when forced rebuild is needed
ARG CACHEBUST=4
COPY . /app

# Collect static files (run from the Django project root)
RUN cd /app/backend && python manage.py collectstatic --noinput

# Set working directory to Django project root so gunicorn finds the module
WORKDIR /app/backend

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn backend.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120"]
