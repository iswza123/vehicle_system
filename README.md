# 🚗 Vehicle Inventory & Booking REST API

A Django REST Framework API to manage vehicles and create bookings, with date validation,
double-booking protection, automatic pricing and interactive Swagger documentation.

| | |
|---|---|
| **Live API** | `https://<your-app>.onrender.com/api/` *(add after deploying)* |
| **Swagger UI** | `https://<your-app>.onrender.com/api/docs/` |
| **Demo video** | *(add YouTube / Drive link here)* |

**Tech:** Python 3.10+ · Django 5.2 · Django REST Framework · django-filter · drf-spectacular (OpenAPI/Swagger) · WhiteNoise · Gunicorn · SQLite (dev) / PostgreSQL (prod)

---

## 1. Setup & installation

```bash
# 1. Clone
git clone <your-repo-url>
cd vehicle_system

# 2. Virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env              # Windows: copy .env.example .env
#    then edit SECRET_KEY (and DATABASE_URL if you want PostgreSQL)
```

### Migration commands
```bash
python manage.py makemigrations   # (migrations are already included)
python manage.py migrate
```

### Optional
```bash
python manage.py seed_vehicles      # insert 6 sample vehicles
python manage.py createsuperuser    # to use /admin/
```

## 2. Run the project
```bash
python manage.py runserver
```
- API root: http://127.0.0.1:8000/api/
- **Swagger UI: http://127.0.0.1:8000/api/docs/**
- ReDoc: http://127.0.0.1:8000/api/redoc/
- Admin: http://127.0.0.1:8000/admin/

## 3. How to test the APIs

1. **Swagger** – open `/api/docs/`, expand an endpoint, click *Try it out*.
2. **Postman** – import `docs/postman_collection.json` (the `base_url` variable defaults to `http://127.0.0.1:8000`; change it to your hosted URL). It includes the valid booking and every invalid scenario.
3. **curl** – example below.
4. **Automated tests** – 24 tests covering CRUD, filters and every booking rule:
   ```bash
   python manage.py test
   ```

## 4. API endpoints

### Vehicles
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/vehicles/` | List vehicles (paginated, 10 per page) |
| POST | `/api/vehicles/` | Add a new vehicle |
| GET | `/api/vehicles/<id>/` | Vehicle details |
| PUT | `/api/vehicles/<id>/` | Update a vehicle (`PATCH` also supported) |
| DELETE | `/api/vehicles/<id>/` | Delete a vehicle (`409` if it has bookings) |

**Filtering** (combinable): `?brand=Toyota` · `?fuel_type=Electric` · `?is_available=true`
Extras: `?search=corolla` · `?ordering=-price_per_day` · `?page=2`

### Bookings
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/bookings/` | List bookings |
| POST | `/api/bookings/` | Create a booking |
| GET | `/api/bookings/<id>/` | Booking details |

Extras: `?vehicle=1` · `?customer_phone=9876543210`

### Sample vehicle JSON
```json
{
  "name": "Corolla",
  "brand": "Toyota",
  "year": 2022,
  "price_per_day": "2500.00",
  "fuel_type": "Petrol",
  "is_available": true
}
```
`fuel_type` ∈ `Petrol`, `Diesel`, `Electric`, `Hybrid`.

### Sample booking JSON
**Request** – `POST /api/bookings/`
```json
{
  "vehicle": 1,
  "customer_name": "Anjali Menon",
  "customer_phone": "9876543210",
  "start_date": "2030-01-10",
  "end_date": "2030-01-13"
}
```
**Response** – `201 Created` (`total_amount` is calculated by the server: 3 days × 2500)
```json
{
  "id": 1,
  "vehicle": 1,
  "vehicle_details": {
    "id": 1, "name": "Corolla", "brand": "Toyota", "year": 2022,
    "price_per_day": "2500.00", "fuel_type": "Petrol", "is_available": false
  },
  "customer_name": "Anjali Menon",
  "customer_phone": "9876543210",
  "start_date": "2030-01-10",
  "end_date": "2030-01-13",
  "total_amount": "7500.00",
  "created_at": "2030-01-01T10:00:00+05:30"
}
```

### Validation error examples (`400 Bad Request`)
```json
{"non_field_errors": ["Vehicle is already booked for the selected dates."]}
{"start_date": ["Start date cannot be in the past."]}
{"end_date": ["End date must be after start date."]}
{"customer_phone": ["Phone number must be exactly 10 digits."]}
```

```bash
curl -X POST http://127.0.0.1:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{"vehicle":1,"customer_name":"Anjali Menon","customer_phone":"9876543210","start_date":"2030-01-10","end_date":"2030-01-13"}'
```

## 5. Booking rules & design decisions

| Rule | Implementation |
|---|---|
| No double-booking | Overlap query in the serializer **and** a re-check inside a transaction with a row lock (`select_for_update`), so concurrent requests can't both succeed on PostgreSQL |
| `total_amount = days × price_per_day` | Computed server-side in `Booking.save()`; the field is read-only for clients |
| Start date not in past | Checked against today's date in the configured timezone (`Asia/Kolkata`); today is allowed |
| End date after start date | Serializer check + database `CHECK` constraint |
| Phone must be 10 digits | Regex `^\d{10}$` |
| Vehicle unavailable after booking | `is_available` is set to `False` in the same transaction as the booking |

**Design notes**
- **Check-out style dates:** `days = end_date − start_date`, and the end date is the return day. A booking ending on the 13th and another starting on the 13th do **not** overlap.
- **Releasing vehicles:** because `is_available` flips to `False` on booking, run the included command periodically (e.g. a daily cron job) to mark vehicles available again once all their bookings have ended:
  ```bash
  python manage.py release_vehicles
  ```
  Date-range overlap checking – not the flag – is what prevents double-booking, so a vehicle flagged unavailable can still be booked for *different, non-overlapping* dates.
- Vehicles with bookings can't be deleted (`on_delete=PROTECT` → `409`), preserving booking history.
- Bookings are create/read only, as per the specification.
- The API is open (no authentication), as per the task. For production, add `DEFAULT_PERMISSION_CLASSES` in `settings.py`.

## 6. Project structure
```
vehicle_system/
├── manage.py
├── requirements.txt
├── .env.example
├── build.sh · Procfile · render.yaml      # deployment
├── docs/postman_collection.json
├── vehicle_system/                         # project: settings, root urls
└── inventory/                              # app
    ├── models.py        # Vehicle, Booking + business logic
    ├── serializers.py   # validation & booking creation
    ├── views.py         # ViewSets
    ├── filters.py       # ?brand= ?fuel_type= ?is_available=
    ├── urls.py          # router
    ├── admin.py
    ├── management/commands/   # seed_vehicles, release_vehicles
    └── tests/test_api.py
```

## 7. Deployment (Render – free tier)

1. Push this repo to GitHub.
2. On https://render.com → **New → Blueprint** → select the repo. `render.yaml` provisions the web service **and** a PostgreSQL database, generates `SECRET_KEY` and runs `build.sh` (install → collectstatic → migrate).
3. Open `https://<your-app>.onrender.com/api/docs/`.
4. Paste the live URL at the top of this README.

*Manual alternative:* create a Web Service (Build: `./build.sh`, Start: `gunicorn vehicle_system.wsgi:application`) and set `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`. The same files work on Railway, Heroku (`Procfile`) and PythonAnywhere.

## 8. Demo video
📹 **Link:** *(add YouTube / Drive link here)*

Suggested 3-minute script: run the server → open Swagger → add a vehicle → create a valid booking (show the calculated `total_amount` and `is_available` flipping to `false`) → show each validation error (overlap, past date, end ≤ start, bad phone) → show filters → run `python manage.py test`.
