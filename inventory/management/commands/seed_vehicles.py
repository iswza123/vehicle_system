from decimal import Decimal

from django.core.management.base import BaseCommand

from inventory.models import Vehicle

SAMPLE = [
    ("Corolla", "Toyota", 2022, "2500.00", "Petrol"),
    ("Innova Crysta", "Toyota", 2023, "4200.00", "Diesel"),
    ("Camry", "Toyota", 2023, "5000.00", "Hybrid"),
    ("Nexon EV", "Tata", 2024, "3000.00", "Electric"),
    ("City", "Honda", 2021, "2300.00", "Petrol"),
    ("Creta", "Hyundai", 2022, "3200.00", "Diesel"),
]


class Command(BaseCommand):
    help = "Insert a few sample vehicles for quick testing."

    def handle(self, *args, **options):
        created = 0
        for name, brand, year, price, fuel in SAMPLE:
            _, was_created = Vehicle.objects.get_or_create(
                name=name, brand=brand, year=year,
                defaults={"price_per_day": Decimal(price), "fuel_type": fuel},
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"Created {created} sample vehicle(s)."))
