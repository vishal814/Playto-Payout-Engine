#!/bin/bash
# Start the Celery background worker in the background (using the & symbol)
celery -A backend worker -l info -P solo &

# Start the Django web server in the foreground
gunicorn backend.wsgi --bind 0.0.0.0:$PORT --log-file -
