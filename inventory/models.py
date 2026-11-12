import re
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r"^\d{10}$", message="Phone number must be exactly 10 digits."
)


def validate_year(value):
    max_year = timezone.localdate().year + 1
    if not 1900 <= value <= max_year:
        raise ValidationError(f"Year must be between 1900 and {max_year}.")


class Vehicle(models.Model):
    class FuelType(models.TextChoices):
        PETROL = "Petrol", "Petrol"
        DIESEL = "Diesel", "Diesel"
        ELECTRIC = "Electric", "Electric"
        HYBRID = "Hybrid", "Hybrid"

    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, db_index=True)
    year = models.IntegerField(validators=[validate_year])
    price_per_day = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    fuel_type = models.CharField(max_length=10, choices=FuelType.choices, db_index=True)
    is_available = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.brand} {self.name} ({self.year})"


class Booking(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="bookings")
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=10, validators=[phone_validator])
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gt=F("start_date")), name="booking_end_after_start"
            )
        ]

    def __str__(self):
        return f"Booking #{self.pk} - {self.vehicle} ({self.start_date} → {self.end_date})"

    # ---- business logic -------------------------------------------------
    @staticmethod
    def calculate_total(vehicle, start_date, end_date):
        """total_amount = number of days * price_per_day."""
        days = (end_date - start_date).days
        return (Decimal(str(vehicle.price_per_day)) * days).quantize(Decimal("0.01"))

    @staticmethod
    def overlapping(vehicle, start_date, end_date, exclude_pk=None):
        """
        Bookings of `vehicle` that clash with [start_date, end_date).
        The end date is the return day, so back-to-back bookings
        (new start == existing end) are allowed.
        """
        qs = Booking.objects.filter(
            vehicle=vehicle, start_date__lt=end_date, end_date__gt=start_date
        )
        return qs.exclude(pk=exclude_pk) if exclude_pk else qs

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "End date must be after start date."
        if self.pk is None and self.start_date and self.start_date < timezone.localdate():
            errors["start_date"] = "Start date cannot be in the past."
        if errors:
            raise ValidationError(errors)
        if self.vehicle_id and self.start_date and self.end_date:
            if Booking.overlapping(self.vehicle, self.start_date, self.end_date, self.pk).exists():
                raise ValidationError("Vehicle is already booked for the selected dates.")

    def save(self, *args, **kwargs):
        self.total_amount = self.calculate_total(self.vehicle, self.start_date, self.end_date)
        super().save(*args, **kwargs)
