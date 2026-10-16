from django.core.management.base import BaseCommand

from recycling.services.orchestrator import send_due_reminders


class Command(BaseCommand):
    help = "Send collection reminders for bookings due in REMINDER_DAYS_BEFORE days."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s)."))
