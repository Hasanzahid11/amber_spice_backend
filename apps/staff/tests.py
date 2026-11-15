from datetime import date, time, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import StaffAttendance, StaffMember, StaffShift

User = get_user_model()


class StaffManagementSystemTests(APITestCase):
    def setUp(self):
        # 1. Manager & Staff Users
        self.manager = User.objects.create_user(
            username='staff_manager',
            email='manager@restaurant.com',
            phone='+353875551001',
            password='password123',
            role=User.Role.MANAGER
        )
        self.kitchen_user = User.objects.create_user(
            username='chef_rajesh',
            email='rajesh@restaurant.com',
            phone='+353875551002',
            password='password123',
            role=User.Role.KITCHEN_STAFF
        )
        self.customer = User.objects.create_user(
            username='dining_customer',
            email='customer@example.com',
            phone='+353871234567',
            password='password123',
            role=User.Role.CUSTOMER
        )

        # 2. Seed Staff Members
        self.staff_server = StaffMember.objects.create(
            name='Aoife Kelly',
            role=StaffMember.Role.SERVER,
            shift=StaffMember.Shift.MORNING,
            status=StaffMember.Status.ACTIVE,
            assigned_section='Conservatory Floor',
            phone='+353879998877',
            hourly_rate=Decimal('15.50')
        )
        self.staff_chef = StaffMember.objects.create(
            user=self.kitchen_user,
            name='Rajesh Kumar',
            role=StaffMember.Role.HEAD_CHEF,
            shift=StaffMember.Shift.FULL_DAY,
            status=StaffMember.Status.OFF_DUTY,
            assigned_section='Main Kitchen Station',
            phone='+353875551002',
            hourly_rate=Decimal('22.00')
        )

    def test_create_staff_member_old_api_contract(self):
        """Validates that existing payload with assignedSection and camelCase works 100%."""
        self.client.force_authenticate(user=self.manager)

        payload = {
            'name': 'Sean O’Brien',
            'role': 'Server',
            'shift': 'Evening (16:00 - 23:00)',
            'status': 'active',
            'assignedSection': 'VIP Dining Room',
            'phone': '087 123 4567'
        }
        res = self.client.post('/api/v1/staff/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'Sean O’Brien')
        self.assertEqual(res.data['assignedSection'], 'VIP Dining Room')
        # Normalizes Irish phone
        self.assertEqual(res.data['phone'], '+353871234567')

    def test_list_and_filter_staff(self):
        self.client.force_authenticate(user=self.manager)

        res = self.client.get('/api/v1/staff/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)

        # Filter by role
        res_chef = self.client.get('/api/v1/staff/?role=Head+Chef')
        self.assertEqual(res_chef.status_code, status.HTTP_200_OK)
        names = [s['name'] for s in res_chef.data]
        self.assertIn('Rajesh Kumar', names)

    def test_on_duty_staff_endpoint(self):
        self.client.force_authenticate(user=self.kitchen_user)

        res = self.client.get('/api/v1/staff/on-duty/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        duty_names = [s['name'] for s in res.data]
        self.assertIn('Aoife Kelly', duty_names)
        self.assertNotIn('Rajesh Kumar', duty_names)

    def test_clock_in_and_clock_out_attendance_lifecycle(self):
        self.client.force_authenticate(user=self.manager)

        # 1. Clock in Rajesh
        clock_in_url = f'/api/v1/staff/{self.staff_chef.id}/clock-in/'
        res_in = self.client.post(clock_in_url, {'notes': 'Starting morning prep'}, format='json')
        self.assertEqual(res_in.status_code, status.HTTP_200_OK)
        self.assertEqual(res_in.data['staff']['status'], 'active')

        self.staff_chef.refresh_from_db()
        self.assertEqual(self.staff_chef.status, StaffMember.Status.ACTIVE)
        self.assertTrue(self.staff_chef.attendance_records.filter(clock_out__isnull=True).exists())

        # 2. Toggle Break
        break_url = f'/api/v1/staff/{self.staff_chef.id}/toggle-break/'
        res_break = self.client.post(break_url)
        self.assertEqual(res_break.status_code, status.HTTP_200_OK)
        self.assertEqual(res_break.data['status'], 'break')

        # 3. Resume duty
        res_resume = self.client.post(break_url)
        self.assertEqual(res_resume.data['status'], 'active')

        # 4. Clock out Rajesh
        clock_out_url = f'/api/v1/staff/{self.staff_chef.id}/clock-out/'
        res_out = self.client.post(clock_out_url, {'notes': 'Completed shift'}, format='json')
        self.assertEqual(res_out.status_code, status.HTTP_200_OK)
        self.assertEqual(res_out.data['staff']['status'], 'off-duty')

        self.staff_chef.refresh_from_db()
        self.assertEqual(self.staff_chef.status, StaffMember.Status.OFF_DUTY)

        # 5. Check attendance history endpoint
        res_att = self.client.get(f'/api/v1/staff/{self.staff_chef.id}/attendance/')
        self.assertEqual(res_att.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_att.data), 1)

    def test_staff_shifts_schedule_api(self):
        self.client.force_authenticate(user=self.manager)

        tomorrow = date.today() + timedelta(days=1)
        payload = {
            'staffMember': self.staff_server.id,
            'shiftDate': tomorrow.isoformat(),
            'startTime': '16:00:00',
            'endTime': '23:00:00',
            'title': 'Friday Dinner Rush',
            'station': 'Conservatory Floor Tables',
            'status': 'scheduled'
        }
        res_shift = self.client.post('/api/v1/staff/schedules/', payload, format='json')
        self.assertEqual(res_shift.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_shift.data['title'], 'Friday Dinner Rush')

        # Check staff member schedules action
        res_member_shifts = self.client.get(f'/api/v1/staff/{self.staff_server.id}/schedules/')
        self.assertEqual(res_member_shifts.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_member_shifts.data), 1)

    def test_customer_cannot_access_staff_api(self):
        self.client.force_authenticate(user=self.customer)

        res = self.client.get('/api/v1/staff/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
