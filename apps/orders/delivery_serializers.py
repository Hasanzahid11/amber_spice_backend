from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .delivery_workflow import DeliveryWorkflow
from .models import DeliveryEvent, DeliveryJob, Order, OrderItem, RiderProfile


class DeliverySummarySerializer(serializers.ModelSerializer):
    acceptedAt = serializers.DateTimeField(source='accepted_at', allow_null=True)
    pickedUpAt = serializers.DateTimeField(source='picked_up_at', allow_null=True)
    arrivedAt = serializers.DateTimeField(source='arrived_at', allow_null=True)
    deliveredAt = serializers.DateTimeField(source='delivered_at', allow_null=True)
    cashCollectedAt = serializers.DateTimeField(source='cash_collected_at', allow_null=True)
    returnRequestedAt = serializers.DateTimeField(source='return_requested_at', allow_null=True)
    returnedAt = serializers.DateTimeField(source='returned_at', allow_null=True)
    hasIssue = serializers.SerializerMethodField()
    kitchenHandoverAt = serializers.DateTimeField(source='handed_over_at', allow_null=True)
    pickupVerifiedAt = serializers.DateTimeField(source='pickup_verified_at', allow_null=True)
    deliveryVerifiedAt = serializers.DateTimeField(source='delivery_verified_at', allow_null=True)
    customerConfirmedReceipt = serializers.BooleanField(source='customer_confirmed_receipt')
    customerConfirmedAt = serializers.DateTimeField(source='customer_confirmed_at', allow_null=True)
    customerPaymentMarkedAt = serializers.DateTimeField(source='customer_payment_marked_at', allow_null=True)
    customerPaymentMedium = serializers.CharField(source='customer_payment_medium')
    bagCount = serializers.IntegerField(source='bag_count')

    class Meta:
        model = DeliveryJob
        fields = [
            'stage', 'acceptedAt', 'pickedUpAt', 'arrivedAt', 'deliveredAt',
            'cashCollectedAt', 'returnRequestedAt', 'returnedAt', 'hasIssue',
            'kitchenHandoverAt', 'pickupVerifiedAt', 'deliveryVerifiedAt',
            'customerConfirmedReceipt', 'customerConfirmedAt',
            'customerPaymentMarkedAt', 'customerPaymentMedium', 'bagCount',
        ]

    def get_hasIssue(self, obj) -> bool:
        return bool(obj.issue_code)


class DeliveryEventSerializer(serializers.ModelSerializer):
    actorName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at')

    class Meta:
        model = DeliveryEvent
        fields = ['id', 'action', 'note', 'amount', 'actorName', 'createdAt']

    def get_actorName(self, obj) -> str:
        return (obj.actor.get_full_name() or obj.actor.username) if obj.actor else 'Former team member'


class DeliveryIssueSerializer(serializers.Serializer):
    code = serializers.CharField()
    note = serializers.CharField()
    reportedAt = serializers.DateTimeField()


class DeliveryProgressSerializer(DeliverySummarySerializer):
    issue = serializers.SerializerMethodField()
    events = DeliveryEventSerializer(source='order.delivery_events', many=True)

    class Meta(DeliverySummarySerializer.Meta):
        fields = DeliverySummarySerializer.Meta.fields + ['issue', 'events']

    @extend_schema_field(DeliveryIssueSerializer(allow_null=True))
    def get_issue(self, obj):
        if obj.issue_code:
            return {'code': obj.issue_code, 'note': obj.issue_note, 'reportedAt': obj.issue_reported_at}
        return None


class RiderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'name', 'quantity', 'customizations']


class RiderJobSerializer(serializers.ModelSerializer):
    orderNumber = serializers.CharField(source='order_number')
    customerName = serializers.CharField(source='customer_name')
    customerPhone = serializers.CharField(source='customer_phone')
    deliveryAddress = serializers.CharField(source='delivery_address')
    deliveryPostalCode = serializers.CharField(source='delivery_postal_code')
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    paymentMethod = serializers.CharField(source='payment_method')
    paymentStatus = serializers.CharField(source='payment_status')
    createdAt = serializers.DateTimeField(source='created_at')
    scheduledFor = serializers.DateTimeField(source='scheduled_for', allow_null=True)
    delivery = DeliveryProgressSerializer(source='delivery_job', allow_null=True)
    items = RiderItemSerializer(many=True)
    availableActions = serializers.SerializerMethodField()
    contactAvailable = serializers.SerializerMethodField()
    ticketReferenceFormat = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'orderNumber', 'customerName', 'customerPhone', 'deliveryAddress', 'deliveryPostalCode',
                  'totalAmount', 'paymentMethod', 'paymentStatus', 'status', 'notes', 'createdAt', 'scheduledFor',
                  'delivery', 'items', 'availableActions', 'contactAvailable', 'ticketReferenceFormat']

    def get_availableActions(self, obj) -> list[str]:
        return DeliveryWorkflow.allowed_actions(obj, self.context['request'].user)

    def get_contactAvailable(self, obj) -> bool:
        from .delivery_chat import contact_available
        return contact_available(obj)

    def get_ticketReferenceFormat(self, obj) -> str:
        job = getattr(obj, 'delivery_job', None)
        return 'code' if job and job.handover_code else 'order_number'


class RiderProfileUpdateSerializer(serializers.Serializer):
    on_duty = serializers.BooleanField(required=False)
    vehicle_type = serializers.ChoiceField(choices=RiderProfile.Vehicle.choices, required=False)
    vehicle_registration = serializers.CharField(max_length=30, allow_blank=True, required=False)


class RiderLocationSerializer(serializers.Serializer):
    name = serializers.CharField()
    address = serializers.CharField()
    phone = serializers.CharField()


class RiderSummarySerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    onDuty = serializers.BooleanField()
    vehicleType = serializers.CharField()
    vehicleRegistration = serializers.CharField(allow_blank=True)
    timezone = serializers.CharField()
    activeJobs = serializers.IntegerField()
    pendingAssignments = serializers.IntegerField()
    deliveredToday = serializers.IntegerField()
    cashCollectedToday = serializers.DecimalField(max_digits=12, decimal_places=2)
    cashOutstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
    pickupLocation = RiderLocationSerializer(allow_null=True)


class RiderNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)


class RiderIssueSerializer(RiderNoteSerializer):
    code = serializers.ChoiceField(choices=[
        ('customer_unavailable', 'Customer unavailable'), ('address_problem', 'Address problem'),
        ('vehicle_problem', 'Vehicle problem'), ('order_problem', 'Order or packaging problem'), ('other', 'Other'),
    ])


class PickupVerificationSerializer(serializers.Serializer):
    ticket_code = serializers.CharField(max_length=32, min_length=1, trim_whitespace=True)
    bag_count = serializers.IntegerField(min_value=1, max_value=30)


class DeliveryVerificationSerializer(PickupVerificationSerializer):
    recipient_confirmed = serializers.BooleanField()


class PackedItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class KitchenHandoverSerializer(serializers.Serializer):
    rider_id = serializers.IntegerField(min_value=1)
    bag_count = serializers.IntegerField(min_value=1, max_value=30)
    items = PackedItemSerializer(many=True, allow_empty=False, max_length=100)
    sealed = serializers.BooleanField()
