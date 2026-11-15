from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish
from apps.orders.models import Order
from .models import Promotion, PromotionUsage

User = get_user_model()


class PromotionsAndDiscountsTests(APITestCase):
    """
    Comprehensive test suite for Promotions & Discounts:
    Percentage, fixed value, first-order, free delivery, BOGO, promo codes,
    minimum spend, time-limited expiry, and usage limits.
    """

    def setUp(self):
        # Admin / Manager User
        self.admin_user = User.objects.create_user(
            username='admin_promo',
            email='admin@amberspice.com',
            phone='+353871112222',
            password='AdminPassword123!',
            role=User.Role.OWNER_ADMIN,
            first_name='Admin',
            last_name='User'
        )

        # Customer User (New)
        self.new_customer = User.objects.create_user(
            username='customer_new',
            email='newbie@example.com',
            phone='+353879998888',
            password='CustomerPassword123!',
            role=User.Role.CUSTOMER
        )

        # Customer User (Existing with prior order)
        self.existing_customer = User.objects.create_user(
            username='customer_existing',
            email='existing@example.com',
            phone='+353877776666',
            password='CustomerPassword123!',
            role=User.Role.CUSTOMER
        )
        self.prior_order = Order.objects.create(
            customer=self.existing_customer,
            customer_name='Existing Customer',
            customer_phone='+353877776666',
            total_amount=Decimal('30.00'),
            status=Order.Status.COMPLETED
        )

        # Menu Category & Dishes
        self.category = Category.objects.create(name='Mains', slug='mains')
        self.biryani = Dish.objects.create(
            category=self.category,
            name='Chicken Biryani',
            price=Decimal('15.00')
        )
        self.naan = Dish.objects.create(
            category=self.category,
            name='Garlic Naan',
            price=Decimal('4.00')
        )

    def test_admin_create_percentage_and_fixed_discount(self):
        """
        Tests Admin creating a percentage promotion and a fixed-value discount.
        """
        self.client.force_authenticate(user=self.admin_user)

        # 1. Percentage discount: 20% off with max cap €10
        payload_pct = {
            'name': 'Weekend Special 20%',
            'code': 'WEEKEND20',
            'discount_type': 'percentage',
            'discount_value': '20.00',
            'max_discount_amount': '10.00',
            'minimum_order_amount': '25.00',
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(days=7)).isoformat(),
        }
        res_pct = self.client.post('/api/v1/promotions/', payload_pct, format='json')
        self.assertEqual(res_pct.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_pct.data['code'], 'WEEKEND20')

        # 2. Fixed value discount: €5 off on orders over €30
        payload_fix = {
            'name': 'Five Off Over Thirty',
            'code': 'FIVE5',
            'discount_type': 'fixed_amount',
            'discount_value': '5.00',
            'minimum_order_amount': '30.00',
        }
        res_fix = self.client.post('/api/v1/promotions/', payload_fix, format='json')
        self.assertEqual(res_fix.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_fix.data['code'], 'FIVE5')

    def test_validate_percentage_promo_code_and_minimum_order(self):
        """
        Tests percentage promo code calculation and enforcement of minimum spend.
        """
        promo = Promotion.objects.create(
            name='15% Off',
            code='SAVE15',
            discount_type=Promotion.DiscountType.PERCENTAGE,
            discount_value=Decimal('15.00'),
            minimum_order_amount=Decimal('20.00')
        )

        # Test Case 1: Subtotal €15 (Under €20 minimum) -> Should fail
        res_fail = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'SAVE15',
            'subtotal': '15.00',
            'delivery_fee': '3.50'
        })
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res_fail.data['isValid'])
        self.assertIn('minimum', res_fail.data['message'].lower())

        # Test Case 2: Subtotal €40 (Meets €20 minimum) -> 15% of €40 = €6.00 discount
        res_pass = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'SAVE15',
            'subtotal': '40.00',
            'delivery_fee': '3.50'
        })
        self.assertEqual(res_pass.status_code, status.HTTP_200_OK)
        self.assertTrue(res_pass.data['isValid'])
        self.assertEqual(Decimal(str(res_pass.data['discountAmount'])), Decimal('6.00'))
        self.assertEqual(Decimal(str(res_pass.data['discountedSubtotal'])), Decimal('34.00'))
        self.assertEqual(Decimal(str(res_pass.data['estimatedTotal'])), Decimal('37.50'))

    def test_first_order_discount(self):
        """
        Tests First-Order discount: eligible for new customer, rejected for existing customer.
        """
        promo = Promotion.objects.create(
            name='First Order 10%',
            code='WELCOME10',
            discount_type=Promotion.DiscountType.FIRST_ORDER,
            discount_value=Decimal('10.00'),
            is_first_order_only=True
        )

        # New customer: Eligible
        self.client.force_authenticate(user=self.new_customer)
        res_new = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'WELCOME10',
            'subtotal': '30.00'
        })
        self.assertEqual(res_new.status_code, status.HTTP_200_OK)
        self.assertTrue(res_new.data['isValid'])
        self.assertEqual(Decimal(str(res_new.data['discountAmount'])), Decimal('3.00'))

        # Existing customer (has prior order): Rejected
        self.client.force_authenticate(user=self.existing_customer)
        res_exist = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'WELCOME10',
            'subtotal': '30.00'
        })
        self.assertEqual(res_exist.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res_exist.data['isValid'])
        self.assertIn('first order', res_exist.data['message'].lower())

    def test_free_delivery_promotion(self):
        """
        Tests Free Delivery promotion waiving the delivery fee on orders >= €25.
        """
        Promotion.objects.create(
            name='Free Delivery Over €25',
            code='FREESHIP',
            discount_type=Promotion.DiscountType.FREE_DELIVERY,
            minimum_order_amount=Decimal('25.00')
        )

        res = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'FREESHIP',
            'subtotal': '30.00',
            'delivery_fee': '4.50',
            'dining_type': 'delivery'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['isValid'])
        self.assertEqual(Decimal(str(res.data['discountAmount'])), Decimal('4.50'))
        self.assertEqual(Decimal(str(res.data['newDeliveryFee'])), Decimal('0.00'))
        self.assertEqual(Decimal(str(res.data['estimatedTotal'])), Decimal('30.00'))

    def test_buy_one_get_one_bogo_offer(self):
        """
        Tests Buy One Biryani Get One Garlic Naan Free.
        """
        Promotion.objects.create(
            name='BOGO Biryani & Naan',
            code='BOGONAAN',
            discount_type=Promotion.DiscountType.BOGO,
            buy_dish=self.biryani,
            buy_quantity=1,
            get_dish=self.naan,
            get_quantity=1,
            get_discount_percentage=Decimal('100.00')  # 100% free
        )

        # Cart with 1 Biryani and 1 Naan
        cart_items = [
            {'dish_id': self.biryani.id, 'quantity': 1, 'price': '15.00'},
            {'dish_id': self.naan.id, 'quantity': 1, 'price': '4.00'},
        ]

        res = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'BOGONAAN',
            'subtotal': '19.00',
            'delivery_fee': '3.00',
            'items': cart_items
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['isValid'])
        # Naan (€4.00) is discounted 100% free
        self.assertEqual(Decimal(str(res.data['discountAmount'])), Decimal('4.00'))

    def test_time_limited_expired_promotion(self):
        """
        Tests that an expired promotion cannot be redeemed.
        """
        Promotion.objects.create(
            name='Expired Flash Sale',
            code='EXPIRED50',
            discount_type=Promotion.DiscountType.PERCENTAGE,
            discount_value=Decimal('50.00'),
            start_date=timezone.now() - timedelta(days=10),
            end_date=timezone.now() - timedelta(days=1)  # Expired yesterday
        )

        res = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'EXPIRED50',
            'subtotal': '50.00'
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['isValid'])
        self.assertIn('expired', res.data['message'].lower())

    def test_usage_limits(self):
        """
        Tests total usage limit and per-customer usage limit.
        """
        promo = Promotion.objects.create(
            name='Limited 1 Use Per Customer',
            code='ONETIME',
            discount_type=Promotion.DiscountType.FIXED_AMOUNT,
            discount_value=Decimal('5.00'),
            usage_limit_total=10,
            usage_limit_per_customer=1
        )

        # Customer uses code once
        promo.record_redemption(
            user=self.new_customer,
            customer_phone=self.new_customer.phone,
            discount_applied=Decimal('5.00')
        )
        self.assertEqual(promo.times_used, 1)

        # Customer tries to use code a second time -> Rejected
        self.client.force_authenticate(user=self.new_customer)
        res_second = self.client.post('/api/v1/promotions/validate-code/', {
            'code': 'ONETIME',
            'subtotal': '25.00'
        })
        self.assertEqual(res_second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res_second.data['isValid'])
        self.assertIn('maximum', res_second.data['message'].lower())

    def test_admin_toggle_active_and_stats(self):
        """
        Tests admin 1-click pause/resume toggle and statistics endpoint.
        """
        promo = Promotion.objects.create(
            name='Toggleable Promo',
            code='TOGGLE',
            discount_type=Promotion.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            is_active=True
        )
        self.client.force_authenticate(user=self.admin_user)

        # Toggle to inactive
        res_pause = self.client.post(f'/api/v1/promotions/{promo.id}/toggle-active/')
        self.assertEqual(res_pause.status_code, status.HTTP_200_OK)
        self.assertFalse(res_pause.data['isActive'])

        # Check stats endpoint
        res_stats = self.client.get(f'/api/v1/promotions/{promo.id}/stats/')
        self.assertEqual(res_stats.status_code, status.HTTP_200_OK)
        self.assertIn('timesUsed', res_stats.data)
        self.assertIn('totalDiscountGiven', res_stats.data)

