from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError

from .models import DeliveryMessage


class MessageConflict(APIException):
    status_code = 409
    default_detail = 'This message request ID was already used for different text. Retry the original message or start a new one.'


def contact_available(order):
    job = getattr(order, 'delivery_job', None)
    return bool(order.dining_type == 'delivery' and order.status == 'out_for_delivery'
                and order.assigned_delivery_staff and order.assigned_delivery_staff.is_active
                and job and job.picked_up_at)


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)
    client_message_id = serializers.UUIDField()


class DeliveryMessageSerializer(serializers.ModelSerializer):
    senderRole = serializers.CharField(source='sender_role', read_only=True)
    senderName = serializers.CharField(source='sender_name', read_only=True)
    clientMessageId = serializers.UUIDField(source='client_message_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = DeliveryMessage
        fields = ['id', 'senderRole', 'senderName', 'body', 'clientMessageId', 'createdAt']


class ContactRiderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    avatar = serializers.CharField(allow_blank=True)
    vehicleType = serializers.CharField(allow_blank=True)
    vehicleRegistration = serializers.CharField(allow_blank=True)


class ConversationSerializer(serializers.Serializer):
    orderNumber = serializers.CharField()
    participantRole = serializers.ChoiceField(choices=['customer', 'rider', 'dispatch'])
    canSend = serializers.BooleanField()
    reason = serializers.CharField()
    rider = ContactRiderSerializer(allow_null=True)


class MessagePageSerializer(serializers.Serializer):
    messages = DeliveryMessageSerializer(many=True)
    nextAfterId = serializers.IntegerField()
    hasMore = serializers.BooleanField()


def conversation(order, role):
    available = contact_available(order)
    rider = order.assigned_delivery_staff
    profile = getattr(rider, 'rider_profile', None) if rider else None
    reason = '' if available else 'Messaging is closed because this delivery has finished.' if order.status in ['delivered', 'cancelled'] else 'Messaging opens after your rider collects the food from the kitchen.'
    return {'orderNumber': order.order_number, 'participantRole': role, 'canSend': available and role != 'dispatch',
            'reason': 'Dispatch has read-only access to this conversation.' if role == 'dispatch' else reason,
            'rider': {'id': rider.id, 'name': rider.get_full_name() or rider.username, 'phone': (rider.phone or '') if available else '',
                      'avatar': rider.avatar or '', 'vehicleType': profile.vehicle_type if profile else '',
                      'vehicleRegistration': profile.vehicle_registration if profile else ''} if rider else None}


def message_page(order, request):
    try:
        after = int(request.query_params.get('after_id', '0'))
        if after < 0:
            raise ValueError
    except (ValueError, TypeError):
        raise ValidationError({'after_id': 'Use a non-negative message ID.'})
    rows = list(DeliveryMessage.objects.filter(order=order, rider_id=order.assigned_delivery_staff_id, id__gt=after).order_by('id')[:101])
    return {'messages': DeliveryMessageSerializer(rows[:100], many=True).data,
            'nextAfterId': rows[min(len(rows), 100) - 1].id if rows else after, 'hasMore': len(rows) > 100}


def save_message(order, user, role, data):
    serializer = MessageCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    body, request_id = serializer.validated_data['body'], serializer.validated_data['client_message_id']
    existing = DeliveryMessage.objects.filter(order=order, rider_id=order.assigned_delivery_staff_id, sender_role=role, client_message_id=request_id).first()
    if existing:
        if existing.body != body:
            raise MessageConflict()
        return existing, False
    if role not in ['customer', 'rider'] or not contact_available(order):
        raise ValidationError({'detail': 'Messages can be sent only after pickup and before this delivery finishes.'})
    sender = user if user and user.is_authenticated else None
    name = order.customer_name if role == 'customer' else user.get_full_name() or user.username
    message = DeliveryMessage.objects.create(order=order, rider_id=order.assigned_delivery_staff_id,
        sender=sender, sender_role=role, sender_name=name[:150], body=body, client_message_id=request_id)
    return message, True
