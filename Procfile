web: gunicorn backend.wsgi --bind 0.0.0.0:$PORT --log-file -
worker: celery -A backend worker -l info
