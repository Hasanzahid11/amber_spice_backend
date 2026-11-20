import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from .models import Notification

logger = logging.getLogger(__name__)


def build_order_payload(order):
    """Formats an Order instance into a clean JSON dictionary for frontends."""
    items_data = []
    summary_parts = []
    for item in order.items.all():
        items_data.append({
            'id': item.id,
            'name': item.name,
            'quantity': item.quantity,
            'price': str(item.price),
            'station': getattr(item, 'station', 'curry'),
            'customizations': item.customizations or {},
        })
        summary_parts.append(f"{item.quantity}x {item.name}")

    summary = ", ".join(summary_parts[:3])
    if len(summary_parts) > 3:
        summary += f" +{len(summary_parts) - 3} more"

    return {
        'id': order.id,
        'orderNumber': order.order_number,
        'customerName': order.customer_name or 'Walk-in / Guest',
        'customerPhone': order.customer_phone or '',
        'diningType': order.dining_type,
        'isTakeaway': order.dining_type == 'takeaway',
        'pickupCode': getattr(order, 'display_pickup_code', ''),
        'pickupRack': getattr(order, 'pickup_rack', '') or '',
        'customerArrivedAt': order.customer_arrived_at.isoformat() if getattr(order, 'customer_arrived_at', None) else None,
        'pickedUpAt': order.picked_up_at.isoformat() if getattr(order, 'picked_up_at', None) else None,
        'tableNumber': order.table_number or '',
        'deliveryAddress': getattr(order, 'delivery_address', ''),
        'status': order.status,
        'paymentStatus': getattr(order, 'payment_status', 'pending'),
        'totalAmount': str(order.total_amount),
        'items': items_data,
        'itemsCount': sum(i['quantity'] for i in items_data),
        'summary': summary,
        'notes': getattr(order, 'notes', '') or '',
        'createdAt': order.created_at.isoformat() if order.created_at else timezone.now().isoformat(),
        'updatedAt': order.updated_at.isoformat() if hasattr(order, 'updated_at') and order.updated_at else timezone.now().isoformat(),
    }


def broadcast_order_created(order):
    """
    Broadcasts new order event to 'admin_operations' WebSocket group
    and persists an unread Notification in the database.
    """
    try:
        payload = build_order_payload(order)
        title = f"New Order #{order.order_number}"
        message = f"{payload['customerName']} placed a {order.dining_type.upper()} order for €{order.total_amount} ({payload['summary']})"

        # Persist Notification
        notif = Notification.objects.create(
            type=Notification.NotificationType.ORDER_CREATED,
            target_role='admin',
            title=title,
            message=message,
            order=order,
            data=payload,
            is_read=False,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'admin_operations',
                {
                    'type': 'order.created',
                    'order': payload,
                    'notification': {
                        'id': notif.id,
                        'type': notif.type,
                        'title': notif.title,
                        'message': notif.message,
                        'createdAt': notif.created_at.isoformat(),
                        'orderId': order.id,
                    },
                }
            )
            logger.info("Broadcasted order.created for #%s to admin_operations", order.order_number)
    except Exception as e:
        logger.exception("Error broadcasting order.created for order %s: %s", getattr(order, 'id', '?'), e)


def broadcast_kitchen_ticket(order, action='received'):
    """
    Broadcasts an order to 'kitchen_kds' group when status changes to 'preparing'
    (e.g., Admin sends to kitchen) or when kitchen status updates.
    """
    try:
        payload = build_order_payload(order)
        title = f"Kitchen Ticket #{order.order_number}"
        message = f"{order.dining_type.upper()} ticket with {payload['itemsCount']} items sent to kitchen."

        notif = Notification.objects.create(
            type=Notification.NotificationType.KITCHEN_ALERT,
            target_role='kitchen',
            title=title,
            message=message,
            order=order,
            data=payload,
            is_read=False,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'kitchen_kds',
                {
                    'type': 'kitchen.ticket_received' if action == 'received' else 'kitchen.ticket_updated',
                    'ticket': payload,
                    'notification': {
                        'id': notif.id,
                        'type': notif.type,
                        'title': notif.title,
                        'message': notif.message,
                        'createdAt': notif.created_at.isoformat(),
                        'orderId': order.id,
                    },
                }
            )
            logger.info("Broadcasted kitchen ticket for #%s to kitchen_kds", order.order_number)
    except Exception as e:
        logger.exception("Error broadcasting kitchen ticket for order %s: %s", getattr(order, 'id', '?'), e)


def broadcast_order_status_updated(order, actor_name=None):
    """
    Broadcasts order status changes to both 'admin_operations' and 'kitchen_kds'.
    """
    try:
        payload = build_order_payload(order)
        actor = f" by {actor_name}" if actor_name else ""
        title = f"Order #{order.order_number} {order.status.upper()}"
        message = f"Order status changed to {order.status.upper()}{actor}."

        notif = Notification.objects.create(
            type=Notification.NotificationType.ORDER_STATUS if order.status != 'ready' else Notification.NotificationType.KITCHEN_READY,
            target_role='all',
            title=title,
            message=message,
            order=order,
            data=payload,
            is_read=False,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            event_data = {
                'type': 'order.status_updated',
                'order': payload,
                'notification': {
                    'id': notif.id,
                    'type': notif.type,
                    'title': notif.title,
                    'message': notif.message,
                    'createdAt': notif.created_at.isoformat(),
                    'orderId': order.id,
                },
            }
            async_to_sync(channel_layer.group_send)('admin_operations', event_data)
            async_to_sync(channel_layer.group_send)('kitchen_kds', {
                'type': 'kitchen.ticket_updated',
                'ticket': payload,
            })
            logger.info("Broadcasted status update %s for #%s", order.status, order.order_number)
    except Exception as e:
        logger.exception("Error broadcasting order status update: %s", e)


def broadcast_customer_arrived(order):
    """
    Broadcasts real-time event when a takeaway customer signals they have
    arrived at the restaurant counter to pick up their order.
    """
    try:
        payload = build_order_payload(order)
        code = payload.get('pickupCode') or f"#{order.id}"
        title = f"Customer Arrived at Counter! ({code})"
        message = f"{order.customer_name} is waiting at the counter to collect Takeaway {code} ({payload['itemsCount']} items)."

        notif = Notification.objects.create(
            type=Notification.NotificationType.CUSTOMER_ARRIVED,
            target_role='all',
            title=title,
            message=message,
            order=order,
            data=payload,
            is_read=False,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            event_data = {
                'type': 'customer.arrived',
                'order': payload,
                'notification': {
                    'id': notif.id,
                    'type': 'customer_arrived',
                    'title': notif.title,
                    'message': notif.message,
                    'createdAt': notif.created_at.isoformat(),
                    'orderId': order.id,
                },
            }
            async_to_sync(channel_layer.group_send)('admin_operations', event_data)
            async_to_sync(channel_layer.group_send)('kitchen_kds', event_data)
            logger.info("Broadcasted customer.arrived for #%s (%s)", order.order_number, code)
    except Exception as e:
        logger.exception("Error broadcasting customer.arrived: %s", e)
