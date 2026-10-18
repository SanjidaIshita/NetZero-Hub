"""python manage.py export_solar_log --out ../process-mining/solar/solar_live_log.csv

Exports the events the running app has really recorded (bookings, payments, staff updates, cancellations,
refunds) in the same event-log format as simulate_solar."""
from pathlib import Path

from django.core.management.base import BaseCommand

from solar.process_log import rows_from_database, write_csv, write_xes


class Command(BaseCommand):
    help = "Export recorded solar events as a process-mining event log (CSV + XES)."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="../process-mining/solar/solar_live_log.csv")

    def handle(self, *args, **opts):
        out = Path(opts["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = rows_from_database()
        write_csv(rows, out)
        write_xes(rows, out.with_suffix(".xes"))
        cases = len({r["case_id"] for r in rows})
        self.stdout.write(self.style.SUCCESS(f"Exported {cases} solar requests, {len(rows)} events -> {out}"))
