from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Booking, Vehicle, phone_validator


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "name", "brand", "year", "price_per_day", "fuel_type", "is_available"]


class BookingSerializer(serializers.ModelSerializer):
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)
    customer_phone = serializers.CharField(max_length=10, validators=[phone_validator])

    class Meta:
        model = Booking
        fields = [
            "id", "vehicle", "vehicle_details", "customer_name", "customer_phone",
            "start_date", "end_date", "total_amount", "created_at",
        ]
        read_only_fields = ["total_amount", "created_at"]

    def validate_customer_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Customer name cannot be blank.")
        return value

    def validate_start_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return value

    def validate(self, attrs):
        start, end = attrs["start_date"], attrs["end_date"]
        if end <= start:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        if Booking.overlapping(attrs["vehicle"], start, end).exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["Vehicle is already booked for the selected dates."]}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Lock the vehicle row and re-check, so two simultaneous requests
        # cannot both pass validation and double-book the same dates.
        vehicle = Vehicle.objects.select_for_update().get(pk=validated_data["vehicle"].pk)
        if Booking.overlapping(vehicle, validated_data["start_date"], validated_data["end_date"]).exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["Vehicle is already booked for the selected dates."]}
            )
        validated_data["vehicle"] = vehicle
        booking = super().create(validated_data)
        # Business rule: after booking, the vehicle becomes unavailable.
        vehicle.is_available = False
        vehicle.save(update_fields=["is_available"])
        return booking
