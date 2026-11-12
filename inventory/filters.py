import django_filters

from .models import Booking, Vehicle


class VehicleFilter(django_filters.FilterSet):
    brand = django_filters.CharFilter(field_name="brand", lookup_expr="iexact")
    fuel_type = django_filters.CharFilter(field_name="fuel_type", lookup_expr="iexact")
    is_available = django_filters.BooleanFilter(field_name="is_available")

    class Meta:
        model = Vehicle
        fields = ["brand", "fuel_type", "is_available"]


class BookingFilter(django_filters.FilterSet):
    class Meta:
        model = Booking
        fields = ["vehicle", "customer_phone"]
