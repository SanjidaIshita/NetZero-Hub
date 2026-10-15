import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Block until the database accepts connections (used by the Docker entrypoint)."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=90)

    def handle(self, *args, timeout, **options):
        deadline = time.monotonic() + timeout
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database is available."))
                return
            except OperationalError as exc:
                if time.monotonic() > deadline:
                    raise CommandError(f"Database not available after {timeout}s: {exc}")
                self.stdout.write("Waiting for database...")
                time.sleep(2)
