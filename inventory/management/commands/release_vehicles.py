from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Vehicle


class Command(BaseCommand):
    help = "Mark vehicles as available again once all of their bookings have ended."

    def handle(self, *args, **options):
        today = timezone.localdate()
        count = (
            Vehicle.objects.filter(is_available=False)
            .exclude(bookings__end_date__gt=today)
            .update(is_available=True)
        )
        self.stdout.write(self.style.SUCCESS(f"Released {count} vehicle(s)."))
