import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Block until the default database accepts connections."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60, help="Seconds to wait before giving up.")

    def handle(self, *args, **options):
        deadline = time.monotonic() + options["timeout"]
        self.stdout.write("Waiting for database...")
        while True:
            try:
                connections["default"].ensure_connection()
                break
            except OperationalError:
                if time.monotonic() > deadline:
                    raise CommandError("Database did not become available in time.")
                time.sleep(1)
        self.stdout.write(self.style.SUCCESS("Database is ready."))
