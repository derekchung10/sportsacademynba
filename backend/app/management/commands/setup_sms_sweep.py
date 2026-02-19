"""
Management command to register the periodic SMS flush sweep with django-q.

Usage:
    python manage.py setup_sms_sweep

This creates (or updates) a Schedule entry that runs flush_stale_threads()
every minute.  Safe to run multiple times — it uses update_or_create.
"""
from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = "Register the periodic SMS batch flush sweep task with django-q"

    def handle(self, *args, **options):
        schedule, created = Schedule.objects.update_or_create(
            name="sms_flush_stale_threads",
            defaults={
                "func": "app.services.sms_batcher.flush_stale_threads",
                "schedule_type": Schedule.MINUTES,
                "minutes": 1,
                "repeats": -1,  # run forever
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} periodic task: {schedule.name} (every 1 minute)"
        ))
