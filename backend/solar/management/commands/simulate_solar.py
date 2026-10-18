"""python manage.py simulate_solar --cases 500 --seed 42 --out ../process-mining/solar

Simulates the ORG-001 solar installation process and writes the event log as CSV (for Disco) and XES.
Nothing is written to the database."""
from pathlib import Path

from django.core.management.base import BaseCommand

from solar.process_log import write_csv, write_xes
from solar.simulation import simulate


class Command(BaseCommand):
    help = "Simulate solar installation requests and write a process-mining event log (CSV + XES)."

    def add_arguments(self, parser):
        parser.add_argument("--cases", type=int, default=500)
        parser.add_argument("--seed", type=int, default=42, help="Same seed = same log every time")
        parser.add_argument("--start", default="2026-01-05", help="First request date (YYYY-MM-DD)")
        parser.add_argument("--end", default="2026-08-31", help="Last request date (YYYY-MM-DD)")
        parser.add_argument("--out", default="../process-mining/solar", help="Folder for the log files")

    def handle(self, *args, **opts):
        out = Path(opts["out"])
        out.mkdir(parents=True, exist_ok=True)
        rows = simulate(opts["cases"], opts["seed"], opts["start"], opts["end"])
        write_csv(rows, out / "solar_event_log.csv")
        write_xes(rows, out / "solar_event_log.xes")
        cases = len({r["case_id"] for r in rows})
        self.stdout.write(self.style.SUCCESS(
            f"Simulated {cases} solar requests, {len(rows)} events -> {out / 'solar_event_log.csv'} (and .xes)"))
