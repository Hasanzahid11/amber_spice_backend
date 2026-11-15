from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.reservations.models import (
    DiningArea,
    Table,
    RestaurantTable,
    ReservationSchedule,
    ReservationSetting,
    Reservation,
    ReservationNotification,
)
from apps.reservations.services import send_reservation_notification

User = get_user_model()


class ModernReservationSystemTests(APITestCase):
    def setUp(self):
        # 1. Staff and Customer
        self.staff_user = User.objects.create_user(
            username='cashier_staff',
            email='cashier@restaurant.com',
            phone='+353875551004',
            password='password123',
            role=User.Role.CASHIER_FRONT
        )
        self.customer = User.objects.create_user(
            username='dining_customer',
            email='customer@example.com',
            phone='+353871234567',
            password='password123',
            role=User.Role.CUSTOMER
        )

        # 2. Dining Areas
        self.main_dining = DiningArea.objects.create(
            name='Main Dining Room',
            description='Warm atmospheric interior hall',
            display_order=1
        )
        self.conservatory = DiningArea.objects.create(
            name='Conservatory & Terrace',
            description='Bright botanical seating area',
            display_order=2
        )

        # 3. Tables
        self.table_small = Table.objects.create(
            number='T-10',
            capacity=2,
            min_capacity=1,
            max_capacity=2,
            dining_area=self.main_dining,
            section=Table.Section.WINDOW,
            shape=Table.TableShape.SQUARE,
            status=Table.Status.AVAILABLE
        )
        self.table_medium = Table.objects.create(
            number='T-11',
            capacity=4,
            min_capacity=1,
            max_capacity=4,
            dining_area=self.conservatory,
            section=Table.Section.MAIN_HALL,
            shape=Table.TableShape.RECTANGULAR,
            status=Table.Status.AVAILABLE
        )

        self.tomorrow = (date.today() + timedelta(days=1)).isoformat()

    def test_create_reservation_camelcase_old_api(self):
        # Old API payload in camelCase
        payload = {
            'guestName': 'Aoife Byrne',
            'guestPhone': '+353 87 999 8877',
            'guestEmail': 'aoife@example.com',
            'guestsCount': 2,
            'reservationDate': self.tomorrow,
            'timeSlot': '19:30',
            'specialRequests': 'Quiet table near window please.'
        }
        res = self.client.post('/api/v1/reservations/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', res.data)
        self.assertTrue(res.data['referenceCode'].startswith('RES-'))
        self.assertEqual(res.data['guestName'], 'Aoife Byrne')
        # Smart auto-assignment should pick the small table (capacity 2)
        self.assertEqual(res.data['table'], self.table_small.id)
        # Notification record should be generated automatically
        self.assertTrue(ReservationNotification.objects.filter(reservation_id=res.data['id']).exists())

    def test_create_reservation_snake_case_compatibility(self):
        # Snake case payload
        payload = {
            'guest_name': 'Conor McGregor',
            'guest_phone': '0871112233',
            'guests_count': 4,
            'reservation_date': self.tomorrow,
            'time_slot': '20:00',
        }
        res = self.client.post('/api/v1/reservations/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['guestName'], 'Conor McGregor')
        # Smart auto-assignment should pick the medium table (capacity 4)
        self.assertEqual(res.data['table'], self.table_medium.id)

    def test_available_slots_calculation(self):
        # Check slot availability
        url = f"/api/v1/reservations/available-slots/?date={self.tomorrow}&guests=2"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('slots', res.data)
        self.assertTrue(len(res.data['slots']) > 0)

        slot_1930 = next(s for s in res.data['slots'] if s['timeSlot'] == '19:30')
        self.assertTrue(slot_1930['isAvailable'])

    def test_reservation_lookup(self):
        # Create booking first
        booking = Reservation.objects.create(
            guest_name='Siobhan Kelly',
            guest_phone='+353871234567',
            guest_email='siobhan@example.com',
            guests_count=2,
            reservation_date=self.tomorrow,
            time_slot='18:30',
            table=self.table_small
        )

        lookup_url = f"/api/v1/reservations/lookup/?reference={booking.reference_code}"
        res = self.client.get(lookup_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['referenceCode'], booking.reference_code)
        self.assertEqual(res.data['guestName'], 'Siobhan Kelly')

    def test_staff_seating_and_completing_lifecycle(self):
        self.client.force_authenticate(user=self.staff_user)

        booking = Reservation.objects.create(
            guest_name='Patrick Murphy',
            guest_phone='+353875551001',
            guests_count=2,
            reservation_date=self.tomorrow,
            time_slot='19:00',
            table=self.table_small,
            status=Reservation.Status.CONFIRMED
        )

        # 1. Staff seats the party
        seat_url = f"/api/v1/reservations/{booking.id}/seat/"
        res_seat = self.client.post(seat_url)
        self.assertEqual(res_seat.status_code, status.HTTP_200_OK)
        self.assertEqual(res_seat.data['reservation']['status'], 'seated')

        # Table should now be occupied
        self.table_small.refresh_from_db()
        self.assertEqual(self.table_small.status, Table.Status.OCCUPIED)
        self.assertEqual(self.table_small.guest_name, 'Patrick Murphy')

        # 2. Staff completes the dining
        complete_url = f"/api/v1/reservations/{booking.id}/complete/"
        res_complete = self.client.post(complete_url)
        self.assertEqual(res_complete.status_code, status.HTTP_200_OK)
        self.assertEqual(res_complete.data['reservation']['status'], 'completed')

        # Table should now be available again
        self.table_small.refresh_from_db()
        self.assertEqual(self.table_small.status, Table.Status.AVAILABLE)
        self.assertIsNone(self.table_small.guest_name)

    def test_customer_cancellation(self):
        booking = Reservation.objects.create(
            guest_name='Cancel Test',
            guest_phone='+353879991122',
            guests_count=2,
            reservation_date=self.tomorrow,
            time_slot='20:30',
            table=self.table_small
        )

        cancel_url = f"/api/v1/reservations/{booking.id}/cancel/"
        payload = {'reference': booking.reference_code, 'reason': 'Change of plans'}
        res = self.client.post(cancel_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['reservation']['status'], 'cancelled')

        # Cancellation notification should be dispatched
        notifications = ReservationNotification.objects.filter(
            reservation=booking,
            notification_type=ReservationNotification.NotificationType.CANCELLATION
        )
        self.assertTrue(notifications.exists())

    def test_dining_area_api_and_table_relationship(self):
        res = self.client.get('/api/v1/reservations/dining-areas/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)
        names = [d['name'] for d in res.data]
        self.assertIn('Main Dining Room', names)
        self.assertIn('Conservatory & Terrace', names)

    def test_restaurant_table_alias_and_availability_slot(self):
        # RestaurantTable alias is interchangeable with Table
        self.assertEqual(RestaurantTable, Table)

        target_date = date.today() + timedelta(days=2)
        # Check initial slot availability
        is_free = self.table_small.is_available_for_slot(
            res_date=target_date,
            start_time=time(19, 0),
            duration_minutes=90
        )
        self.assertTrue(is_free)

        # Create a conflicting booking
        Reservation.objects.create(
            table=self.table_small,
            guest_name='Conflict Test',
            guest_phone='+353871112233',
            guests_count=2,
            reservation_date=target_date,
            time_slot='19:00',
            reservation_time=time(19, 0),
            duration_minutes=90,
            status=Reservation.Status.CONFIRMED
        )

        # Now slot should conflict
        is_free_after = self.table_small.is_available_for_slot(
            res_date=target_date,
            start_time=time(19, 30),
            duration_minutes=90
        )
        self.assertFalse(is_free_after)

    def test_reservation_schedule_shift_validation(self):
        # Configure Wednesday closed
        sched = ReservationSchedule.objects.create(
            day_of_week=ReservationSchedule.DayOfWeek.WEDNESDAY,
            is_closed=True
        )
        # Find next Wednesday
        today = date.today()
        days_ahead = (2 - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_wednesday = today + timedelta(days=days_ahead)

        is_open, msg = ReservationSchedule.is_time_slot_open(next_wednesday, time(19, 0))
        self.assertFalse(is_open)
        self.assertIn("closed for dining", msg.lower())

    def test_reservation_settings_singleton(self):
        settings_obj = ReservationSetting.get_settings()
        self.assertEqual(settings_obj.standard_duration_minutes, 90)
        self.assertEqual(settings_obj.max_party_size, 16)
