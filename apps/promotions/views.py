from decimal import Decimal
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsManagerOrAdmin
from .models import Promotion, PromotionUsage
from .serializers import (
    PromotionSerializer,
    PromotionPublicSerializer,
    ValidatePromoCodeRequestSerializer,
    ValidatePromoCodeResponseSerializer,
    PromotionUsageSerializer,
)


class PromotionViewSet(viewsets.ModelViewSet):
    """
    Promotions and Discounts ViewSet.
    Admin/Manager: Full CRUD, usage statistics, pause/resume toggling.
    Customer: Public active offers, 1-click code validation at checkout.
    """
    queryset = Promotion.objects.all()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve'] and not (self.request.user and self.request.user.is_authenticated and self.request.user.is_manager_or_admin):
            return PromotionPublicSerializer
        return PromotionSerializer

    def get_permissions(self):
        if self.action in ['active', 'validate_code', 'auto_apply']:
            return [permissions.AllowAny()]
        if self.action in ['list', 'retrieve']:
            # Customers can list/retrieve public promotions
            return [permissions.AllowAny()]
        # Create, update, delete, toggle, stats restricted to Manager/Admin
        return [IsManagerOrAdmin()]

    def get_queryset(self):
        qs = Promotion.objects.all()
        user = self.request.user
        # Non-staff users only see currently active and valid promotions
        if not (user and user.is_authenticated and user.is_manager_or_admin):
            now = timezone.now()
            qs = qs.filter(
                is_active=True,
                start_date__lte=now
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        GET /api/v1/promotions/active/
        Public endpoint returning all currently active promotions, banners, and coupon offers.
        """
        now = timezone.now()
        active_promos = Promotion.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        serializer = PromotionPublicSerializer(active_promos, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='toggle-active', permission_classes=[IsManagerOrAdmin])
    def toggle_active(self, request, pk=None):
        """
        POST /api/v1/promotions/<id>/toggle-active/
        Admin 1-click toggle to pause or activate a promotion.
        """
        promo = self.get_object()
        promo.is_active = not promo.is_active
        promo.save(update_fields=['is_active', 'updated_at'])
        status_text = "activated" if promo.is_active else "paused"
        return Response({
            'message': f"Promotion '{promo.name}' {status_text}.",
            'isActive': promo.is_active,
            'promotion': PromotionSerializer(promo).data
        })

    @action(detail=True, methods=['get'], permission_classes=[IsManagerOrAdmin])
    def stats(self, request, pk=None):
        """
        GET /api/v1/promotions/<id>/stats/
        Detailed redemption statistics for management review.
        """
        promo = self.get_object()
        total_usages = promo.usages.count()
        total_discount = promo.usages.aggregate(total=Sum('discount_applied'))['total'] or Decimal('0.00')
        avg_discount = (total_discount / Decimal(total_usages)).quantize(Decimal('0.01')) if total_usages > 0 else Decimal('0.00')

        return Response({
            'promotionId': str(promo.id),
            'name': promo.name,
            'code': promo.code,
            'discountType': promo.discount_type,
            'timesUsed': promo.times_used,
            'usageLimitTotal': promo.usage_limit_total,
            'totalDiscountGiven': total_discount,
            'averageDiscountPerOrder': avg_discount,
            'isActive': promo.is_active,
            'isExpired': promo.is_expired,
        })

    @action(detail=False, methods=['post'], url_path='validate-code')
    def validate_code(self, request):
        """
        POST /api/v1/promotions/validate-code/
        Validates a promotional code against cart subtotal, customer eligibility,
        time restrictions, and minimum spend requirements.
        """
        req_serializer = ValidatePromoCodeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        code_input = data['code'].strip().upper()
        subtotal = data['subtotal']
        delivery_fee = data['delivery_fee']
        dining_type = data['dining_type']
        customer_phone = data.get('customer_phone', '')
        customer_email = data.get('customer_email', '')
        items = data.get('items', [])

        promo = Promotion.objects.filter(code=code_input).first()
        if not promo:
            return Response({
                'isValid': False,
                'code': code_input,
                'promotionId': None,
                'promotionName': None,
                'discountType': None,
                'discountAmount': Decimal('0.00'),
                'newDeliveryFee': delivery_fee,
                'originalSubtotal': subtotal,
                'discountedSubtotal': subtotal,
                'estimatedTotal': subtotal + delivery_fee,
                'message': f"Promotional code '{code_input}' is invalid or does not exist."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Step 1: Check general time, date, and overall limit validity
        is_valid_now, reason = promo.is_valid_now()
        if not is_valid_now:
            return Response({
                'isValid': False,
                'code': code_input,
                'promotionId': str(promo.id),
                'promotionName': promo.name,
                'discountType': promo.discount_type,
                'discountAmount': Decimal('0.00'),
                'newDeliveryFee': delivery_fee,
                'originalSubtotal': subtotal,
                'discountedSubtotal': subtotal,
                'estimatedTotal': subtotal + delivery_fee,
                'message': reason
            }, status=status.HTTP_400_BAD_REQUEST)

        # Step 2: Check customer-specific eligibility (First order, per-customer limits)
        user = request.user if request.user.is_authenticated else None
        is_eligible, elig_reason = promo.is_eligible_customer(
            user=user,
            customer_phone=customer_phone,
            customer_email=customer_email
        )
        if not is_eligible:
            return Response({
                'isValid': False,
                'code': code_input,
                'promotionId': str(promo.id),
                'promotionName': promo.name,
                'discountType': promo.discount_type,
                'discountAmount': Decimal('0.00'),
                'newDeliveryFee': delivery_fee,
                'originalSubtotal': subtotal,
                'discountedSubtotal': subtotal,
                'estimatedTotal': subtotal + delivery_fee,
                'message': elig_reason
            }, status=status.HTTP_400_BAD_REQUEST)

        # Step 3: Compute actual discount
        discount_amount, new_delivery_fee, calc_reason = promo.calculate_discount(
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            dining_type=dining_type,
            items=items
        )

        if discount_amount <= Decimal('0.00'):
            return Response({
                'isValid': False,
                'code': code_input,
                'promotionId': str(promo.id),
                'promotionName': promo.name,
                'discountType': promo.discount_type,
                'discountAmount': Decimal('0.00'),
                'newDeliveryFee': delivery_fee,
                'originalSubtotal': subtotal,
                'discountedSubtotal': subtotal,
                'estimatedTotal': subtotal + delivery_fee,
                'message': calc_reason
            }, status=status.HTTP_400_BAD_REQUEST)

        discounted_sub = max(Decimal('0.00'), subtotal - discount_amount)
        estimated_total = max(Decimal('0.00'), discounted_sub + new_delivery_fee)

        res_data = {
            'isValid': True,
            'code': promo.code,
            'promotionId': str(promo.id),
            'promotionName': promo.name,
            'discountType': promo.discount_type,
            'discountAmount': discount_amount,
            'newDeliveryFee': new_delivery_fee,
            'originalSubtotal': subtotal,
            'discountedSubtotal': discounted_sub,
            'estimatedTotal': estimated_total,
            'message': f"Promotional code applied: {calc_reason}"
        }
        serializer = ValidatePromoCodeResponseSerializer(res_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='auto-apply')
    def auto_apply(self, request):
        """
        POST /api/v1/promotions/auto-apply/
        Automatically evaluates all active code-less promotions (e.g. Free delivery over €35,
        first-order discount) and applies the single highest discount to the customer's cart.
        """
        subtotal = Decimal(str(request.data.get('subtotal', 0)))
        delivery_fee = Decimal(str(request.data.get('delivery_fee', 0)))
        dining_type = request.data.get('dining_type', 'delivery')
        customer_phone = request.data.get('customer_phone', '')
        customer_email = request.data.get('customer_email', '')
        items = request.data.get('items', [])

        user = request.user if request.user.is_authenticated else None
        now = timezone.now()

        # Query active promotions with NO coupon code required
        auto_promos = Promotion.objects.filter(
            is_active=True,
            code__isnull=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )

        best_promo = None
        best_discount = Decimal('0.00')
        best_new_delivery_fee = delivery_fee
        best_reason = ""

        for promo in auto_promos:
            valid_now, _ = promo.is_valid_now()
            if not valid_now:
                continue

            eligible, _ = promo.is_eligible_customer(user=user, customer_phone=customer_phone, customer_email=customer_email)
            if not eligible:
                continue

            disc, new_fee, reason = promo.calculate_discount(
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                dining_type=dining_type,
                items=items
            )
            if disc > best_discount:
                best_discount = disc
                best_new_delivery_fee = new_fee
                best_promo = promo
                best_reason = reason

        if best_promo and best_discount > Decimal('0.00'):
            discounted_sub = max(Decimal('0.00'), subtotal - best_discount)
            estimated_total = max(Decimal('0.00'), discounted_sub + best_new_delivery_fee)
            return Response({
                'applied': True,
                'promotionId': str(best_promo.id),
                'promotionName': best_promo.name,
                'discountType': best_promo.discount_type,
                'discountAmount': best_discount,
                'newDeliveryFee': best_new_delivery_fee,
                'originalSubtotal': subtotal,
                'discountedSubtotal': discounted_sub,
                'estimatedTotal': estimated_total,
                'message': f"Automatic offer applied: {best_reason}"
            })

        return Response({
            'applied': False,
            'message': 'No automatic promotions eligible for this cart.'
        })


class PromotionUsageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit log of promotion code redemptions.
    Restricted to Manager and Owner/Admin.
    """
    queryset = PromotionUsage.objects.select_related('promotion', 'order', 'user').all()
    serializer_class = PromotionUsageSerializer
    permission_classes = [IsManagerOrAdmin]

