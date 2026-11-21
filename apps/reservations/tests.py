from datetime import date, timedelta
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Table, Reservation


class ReservationApiTests(APITestCase):
    def setUp(self):
        self.table_small = Table.objects.create(number='T1', capacity=2, status='available')
        self.table_large = Table.objects.create(number='T2', capacity=6, status='available')
        self.future_date = (date.today() + timedelta(days=2)).isoformat()
        self.future_time = '19:30'

    def test_table_availability_check(self):
        # Check availability for 2 guests
        url = f"/api/v1/reservations/tables/availability/?guests=2&date={self.future_date}&time={self.future_time}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        table_numbers = [t['number'] for t in response.data]
        self.assertIn('T1', table_numbers)
        self.assertIn('T2', table_numbers)

        # For 5 guests, only T2 (capacity 6) should be available
        url_large = f"/api/v1/reservations/tables/availability/?guests=5&date={self.future_date}&time={self.future_time}"
        res_large = self.client.get(url_large)
        self.assertEqual(res_large.status_code, status.HTTP_200_OK)
        large_numbers = [t['number'] for t in res_large.data]
        self.assertNotIn('T1', large_numbers)
        self.assertIn('T2', large_numbers)

    def test_public_create_table_reservation(self):
        payload = {
            'guestName': 'John Murphy',
            'guestPhone': '+353871234567',
            'guestEmail': 'john@example.com',
            'guestsCount': 2,
            'reservationDate': self.future_date,
            'timeSlot': self.future_time,
            'specialRequests': 'Window seat please',
        }
        response = self.client.post('/api/v1/reservations/bookings/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['guestName'], 'John Murphy')
        self.assertEqual(response.data['status'], 'confirmed')
        self.assertEqual(response.data['tableNumber'], 'T1')  # Best fit for 2 guests
        self.assertTrue(len(response.data['booking_reference']) > 0)

        # Verify tracking endpoint works publicly with the booking reference
        ref = response.data['booking_reference']
        track_res = self.client.get(f"/api/v1/reservations/bookings/track/{ref}/")
        self.assertEqual(track_res.status_code, status.HTTP_200_OK)
        self.assertEqual(track_res.data['guestName'], 'John Murphy')
        self.assertEqual(track_res.data['tableNumber'], 'T1')

    def test_double_booking_conflict_prevention(self):
        payload = {
            'guestName': 'First Booker',
            'guestPhone': '+353871111111',
            'guestsCount': 2,
            'reservationDate': self.future_date,
            'timeSlot': self.future_time,
        }
        res1 = self.client.post('/api/v1/reservations/bookings/', payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['tableNumber'], 'T1')

        # Second booking for 2 guests gets T2 (since T1 is booked)
        payload2 = {
            'guestName': 'Second Booker',
            'guestPhone': '+353872222222',
            'guestsCount': 2,
            'reservationDate': self.future_date,
            'timeSlot': self.future_time,
        }
        res2 = self.client.post('/api/v1/reservations/bookings/', payload2, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data['tableNumber'], 'T2')

        # Third booking fails because both tables are booked for that slot
        payload3 = {
            'guestName': 'Third Booker',
            'guestPhone': '+353873333333',
            'guestsCount': 2,
            'reservationDate': self.future_date,
            'timeSlot': self.future_time,
        }
        res3 = self.client.post('/api/v1/reservations/bookings/', payload3, format='json')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timeSlot', res3.data)
