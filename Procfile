web: gunicorn backend.wsgi --chdir /app/backend --bind 0.0.0.0:$PORT --workers 2 --timeout 120
release: python backend/manage.py migrate --noinput
