from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Booking, Vehicle


def today():
    return timezone.localdate()


class VehicleAPITests(APITestCase):
    def setUp(self):
        self.toyota = Vehicle.objects.create(
            name="Corolla", brand="Toyota", year=2022, price_per_day="2500.00", fuel_type="Petrol")
        self.tata = Vehicle.objects.create(
            name="Nexon EV", brand="Tata", year=2024, price_per_day="3000.00",
            fuel_type="Electric", is_available=False)

    def test_list(self):
        r = self.client.get("/api/vehicles/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)

    def test_create(self):
        payload = {"name": "City", "brand": "Honda", "year": 2021,
                   "price_per_day": "2300.00", "fuel_type": "Petrol"}
        r = self.client.post("/api/vehicles/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["is_available"])

    def test_create_invalid_fuel_type_and_price(self):
        payload = {"name": "X", "brand": "Y", "year": 2021, "price_per_day": "-5", "fuel_type": "Steam"}
        r = self.client.post("/api/vehicles/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("fuel_type", r.data)
        self.assertIn("price_per_day", r.data)

    def test_invalid_year(self):
        payload = {"name": "X", "brand": "Y", "year": 1800, "price_per_day": "10", "fuel_type": "Petrol"}
        self.assertEqual(self.client.post("/api/vehicles/", payload, format="json").status_code, 400)

    def test_retrieve_update_delete(self):
        url = f"/api/vehicles/{self.toyota.id}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        payload = {"name": "Corolla", "brand": "Toyota", "year": 2023,
                   "price_per_day": "2600.00", "fuel_type": "Hybrid", "is_available": True}
        r = self.client.put(url, payload, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fuel_type"], "Hybrid")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_filters(self):
        self.assertEqual(self.client.get("/api/vehicles/?brand=Toyota").data["count"], 1)
        self.assertEqual(self.client.get("/api/vehicles/?brand=toyota").data["count"], 1)
        self.assertEqual(self.client.get("/api/vehicles/?fuel_type=Electric").data["count"], 1)
        self.assertEqual(self.client.get("/api/vehicles/?is_available=true").data["count"], 1)
        self.assertEqual(self.client.get("/api/vehicles/?is_available=false").data["count"], 1)
        self.assertEqual(
            self.client.get("/api/vehicles/?brand=Toyota&fuel_type=Electric").data["count"], 0)

    def test_delete_vehicle_with_bookings_is_blocked(self):
        Booking.objects.create(vehicle=self.toyota, customer_name="A", customer_phone="9876543210",
                               start_date=today(), end_date=today() + timedelta(days=1))
        r = self.client.delete(f"/api/vehicles/{self.toyota.id}/")
        self.assertEqual(r.status_code, 409)


class BookingAPITests(APITestCase):
    def setUp(self):
        self.vehicle = Vehicle.objects.create(
            name="Corolla", brand="Toyota", year=2022, price_per_day="2500.00", fuel_type="Petrol")

    def payload(self, **kw):
        data = {"vehicle": self.vehicle.id, "customer_name": "Anjali Menon",
                "customer_phone": "9876543210",
                "start_date": str(today() + timedelta(days=1)),
                "end_date": str(today() + timedelta(days=4))}
        data.update(kw)
        return data

    def post(self, **kw):
        return self.client.post("/api/bookings/", self.payload(**kw), format="json")

    def test_create_booking_calculates_total_and_marks_unavailable(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["total_amount"]), Decimal("7500.00"))  # 3 days * 2500
        self.assertEqual(r.data["vehicle_details"]["id"], self.vehicle.id)
        self.vehicle.refresh_from_db()
        self.assertFalse(self.vehicle.is_available)

    def test_total_amount_cannot_be_set_by_client(self):
        r = self.post(total_amount="1.00")
        self.assertEqual(Decimal(r.data["total_amount"]), Decimal("7500.00"))

    def test_start_date_in_past(self):
        r = self.post(start_date=str(today() - timedelta(days=1)))
        self.assertEqual(r.status_code, 400)
        self.assertIn("start_date", r.data)

    def test_start_today_is_allowed(self):
        r = self.post(start_date=str(today()), end_date=str(today() + timedelta(days=1)))
        self.assertEqual(r.status_code, 201)

    def test_end_before_or_equal_start(self):
        for end in (today() + timedelta(days=1), today()):
            r = self.post(end_date=str(end))
            self.assertEqual(r.status_code, 400)
            self.assertIn("end_date", r.data)

    def test_phone_validation(self):
        for bad in ("12345", "98765432101", "98765abcde", "+919876543", ""):
            r = self.post(customer_phone=bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("customer_phone", r.data)

    def test_blank_name(self):
        self.assertEqual(self.post(customer_name="   ").status_code, 400)

    def test_missing_fields(self):
        r = self.client.post("/api/bookings/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        for f in ("vehicle", "customer_name", "customer_phone", "start_date", "end_date"):
            self.assertIn(f, r.data)

    def test_unknown_vehicle(self):
        self.assertEqual(self.post(vehicle=9999).status_code, 400)

    def test_double_booking_overlap_rejected(self):
        self.assertEqual(self.post().status_code, 201)  # days +1 .. +4
        cases = [
            (1, 4),    # identical
            (2, 3),    # inside
            (0, 2),    # overlaps start
            (3, 6),    # overlaps end
            (0, 10),   # wraps existing
        ]
        for s, e in cases:
            r = self.post(start_date=str(today() + timedelta(days=s)),
                          end_date=str(today() + timedelta(days=e)))
            self.assertEqual(r.status_code, 400, (s, e))
            self.assertIn("already booked", str(r.data))

    def test_back_to_back_and_later_bookings_allowed(self):
        self.assertEqual(self.post().status_code, 201)  # +1 .. +4
        # starts on the day the previous one ends
        r = self.post(start_date=str(today() + timedelta(days=4)),
                      end_date=str(today() + timedelta(days=6)))
        self.assertEqual(r.status_code, 201, r.data)
        # well after
        r = self.post(start_date=str(today() + timedelta(days=30)),
                      end_date=str(today() + timedelta(days=31)))
        self.assertEqual(r.status_code, 201)

    def test_other_vehicle_same_dates_allowed(self):
        other = Vehicle.objects.create(name="City", brand="Honda", year=2021,
                                       price_per_day="2000", fuel_type="Petrol")
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post(vehicle=other.id).status_code, 201)

    def test_list_and_retrieve(self):
        created = self.post().data
        r = self.client.get("/api/bookings/")
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(f"/api/bookings/{created['id']}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["customer_name"], "Anjali Menon")

    def test_booking_update_and_delete_not_exposed(self):
        created = self.post().data
        url = f"/api/bookings/{created['id']}/"
        self.assertEqual(self.client.put(url, self.payload(), format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_release_vehicles_command(self):
        Booking.objects.create(vehicle=self.vehicle, customer_name="A", customer_phone="9876543210",
                               start_date=today() - timedelta(days=5), end_date=today() - timedelta(days=2))
        Vehicle.objects.filter(pk=self.vehicle.pk).update(is_available=False)
        call_command("release_vehicles")
        self.vehicle.refresh_from_db()
        self.assertTrue(self.vehicle.is_available)

    def test_release_keeps_vehicle_with_upcoming_booking(self):
        self.post()
        call_command("release_vehicles")
        self.vehicle.refresh_from_db()
        self.assertFalse(self.vehicle.is_available)


class DocsTests(APITestCase):
    def test_swagger_and_schema(self):
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
