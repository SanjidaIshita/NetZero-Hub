#!/bin/sh
set -e

python manage.py wait_for_db

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput >/dev/null
    if [ "${SEED_DATA:-true}" = "true" ]; then
        python manage.py seed_data
    fi
fi

exec "$@"
