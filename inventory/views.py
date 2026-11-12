from django.db.models import ProtectedError
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .filters import BookingFilter, VehicleFilter
from .models import Booking, Vehicle
from .serializers import BookingSerializer, VehicleSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List vehicles",
        parameters=[
            OpenApiParameter("brand", str, description="Case-insensitive brand, e.g. Toyota"),
            OpenApiParameter("fuel_type", str, enum=["Petrol", "Diesel", "Electric", "Hybrid"]),
            OpenApiParameter("is_available", bool),
        ],
    ),
    create=extend_schema(summary="Add a new vehicle"),
    retrieve=extend_schema(summary="Vehicle details"),
    update=extend_schema(summary="Update a vehicle (PUT)"),
    partial_update=extend_schema(summary="Partially update a vehicle (PATCH)"),
    destroy=extend_schema(summary="Delete a vehicle"),
)
class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filterset_class = VehicleFilter
    search_fields = ["name", "brand"]
    ordering_fields = ["id", "price_per_day", "year", "brand"]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete a vehicle that has bookings."},
                status=status.HTTP_409_CONFLICT,
            )


@extend_schema_view(
    list=extend_schema(summary="List bookings"),
    create=extend_schema(summary="Create a booking"),
    retrieve=extend_schema(summary="Booking details"),
)
class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Booking.objects.select_related("vehicle")
    serializer_class = BookingSerializer
    filterset_class = BookingFilter
    search_fields = ["customer_name", "customer_phone"]
    ordering_fields = ["id", "start_date", "end_date", "total_amount"]
