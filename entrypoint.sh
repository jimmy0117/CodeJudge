#!/bin/bash
set -e

echo "Waiting for database..."
while ! pg_isready -h ${POSTGRES_HOST:-db} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-apcs_user}; do
  sleep 1
done

echo "Database is ready!"
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
