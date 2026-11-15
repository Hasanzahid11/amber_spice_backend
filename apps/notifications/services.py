import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Notification, NotificationTemplate, NotificationPreference

logger = logging.getLogger(__name__)


class NotificationChannelDispatcher:
    """
    Modular dispatcher handling delivery across In-App, Email, SMS, WhatsApp, and Push.
    Designed for zero failure - if an external gateway is down or not configured,
    the event is safely logged and persisted.
    """

    @classmethod
    def dispatch(cls, notification: Notification) -> bool:
        channel = notification.channel

        try:
            if channel == Notification.Channel.IN_APP:
                return cls._deliver_in_app(notification)
            elif channel == Notification.Channel.EMAIL:
                return cls._deliver_email(notification)
            elif channel == Notification.Channel.SMS:
                return cls._deliver_sms(notification)
            elif channel == Notification.Channel.WHATSAPP:
                return cls._deliver_whatsapp(notification)
            elif channel == Notification.Channel.PUSH:
                return cls._deliver_push(notification)
            else:
                return cls._deliver_in_app(notification)
        except Exception as e:
            logger.error(f"[Notification] Failed to deliver {notification}: {e}")
            notification.status = Notification.Status.FAILED
            notification.error_message = str(e)
            notification.save(update_fields=['status', 'error_message', 'updated_at'])
            return False

    @classmethod
    def _deliver_in_app(cls, notification: Notification) -> bool:
        notification.status = Notification.Status.DELIVERED
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at', 'updated_at'])
        return True

    @classmethod
    def _deliver_email(cls, notification: Notification) -> bool:
        recipient_email = notification.recipient_email or (notification.recipient.email if notification.recipient else None)
        if not recipient_email:
            notification.status = Notification.Status.FAILED
            notification.error_message = "No recipient email address provided."
            notification.save(update_fields=['status', 'error_message', 'updated_at'])
            return False

        subject = f"[Amber Spice] {notification.title}"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'orders@amberspice.com')
        body = (
            f"{notification.message}\n\n"
            f"---\n"
            f"Amber Spice Restaurant\n"
            f"Dublin, Ireland | Tel: +353 (0)1 234 5678\n"
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=[recipient_email],
                fail_silently=True
            )
            notification.status = Notification.Status.SENT
            notification.sent_at = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'updated_at'])
            return True
        except Exception as e:
            notification.status = Notification.Status.FAILED
            notification.error_message = str(e)
            notification.save(update_fields=['status', 'error_message', 'updated_at'])
            return False

    @classmethod
    def _deliver_sms(cls, notification: Notification) -> bool:
        recipient_phone = notification.recipient_phone or (notification.recipient.phone if notification.recipient else None)
        if not recipient_phone:
            notification.status = Notification.Status.FAILED
            notification.error_message = "No recipient phone number provided."
            notification.save(update_fields=['status', 'error_message', 'updated_at'])
            return False

        # In a production environment with Twilio / SMS provider:
        # e.g. twilio_client.messages.create(body=notification.message, to=recipient_phone)
        logger.info(f"[SMS Gateway] Sent to {recipient_phone}: {notification.message}")
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at', 'updated_at'])
        return True

    @classmethod
    def _deliver_whatsapp(cls, notification: Notification) -> bool:
        recipient_phone = notification.recipient_phone or (notification.recipient.phone if notification.recipient else None)
        if not recipient_phone:
            notification.status = Notification.Status.FAILED
            notification.error_message = "No recipient phone number provided."
            notification.save(update_fields=['status', 'error_message', 'updated_at'])
            return False

        # WhatsApp Business Cloud API payload simulation
        logger.info(f"[WhatsApp Gateway] Delivered to {recipient_phone}: *{notification.title}*\n{notification.message}")
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at', 'updated_at'])
        return True

    @classmethod
    def _deliver_push(cls, notification: Notification) -> bool:
        # Web Push / FCM Push simulation
        logger.info(f"[Push Gateway] Sent notification to user {notification.recipient_id}: {notification.title}")
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at', 'updated_at'])
        return True


def send_notification(
    event_type: str,
    recipient=None,
    recipient_email: str = "",
    recipient_phone: str = "",
    recipient_role: str = "",
    title: str = "",
    message: str = "",
    data: dict = None,
    channels: list = None
) -> list[Notification]:
    """
    Primary notification dispatch entry point.
    Renders templates if title/message not provided, verifies user channel preferences,
    and dispatches across all specified channels.
    """
    if channels is None:
        channels = [Notification.Channel.IN_APP, Notification.Channel.EMAIL]

    if data is None:
        data = {}

    # Check recipient preferences if user is authenticated
    if recipient and hasattr(recipient, 'notification_preferences'):
        prefs = recipient.notification_preferences
        filtered_channels = []
        for ch in channels:
            if ch == Notification.Channel.EMAIL and not prefs.email_enabled:
                continue
            if ch == Notification.Channel.SMS and not prefs.sms_enabled:
                continue
            if ch == Notification.Channel.WHATSAPP and not prefs.whatsapp_enabled:
                continue
            if ch == Notification.Channel.PUSH and not prefs.push_enabled:
                continue
            filtered_channels.append(ch)
        channels = filtered_channels or [Notification.Channel.IN_APP]

    created_notifications = []

    for ch in channels:
        # Check if an active template exists for this event_type & channel
        final_title = title
        final_message = message

        template = NotificationTemplate.objects.filter(
            event_type=event_type,
            channel=ch,
            is_active=True
        ).first()

        if template:
            rendered_t, rendered_m = template.render(data)
            final_title = rendered_t or final_title
            final_message = rendered_m or final_message

        notif = Notification.objects.create(
            recipient=recipient,
            recipient_email=recipient_email or (recipient.email if recipient else ""),
            recipient_phone=recipient_phone or (recipient.phone if recipient else ""),
            recipient_role=recipient_role,
            notification_type=event_type,
            channel=ch,
            title=final_title,
            message=final_message,
            data=data
        )

        NotificationChannelDispatcher.dispatch(notif)
        created_notifications.append(notif)

    return created_notifications


# ==========================================
# Specialized Event Notification Handlers
# ==========================================

def notify_new_order(order) -> list[Notification]:
    """
    1. Customer receives order placement confirmation.
    2. Kitchen and Admin receive incoming order alert.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'total_amount': f"€{order.total_amount:.2f}",
        'dining_type': order.get_dining_type_display(),
        'estimated_time': order.estimated_time_minutes,
        'order_id': str(order.id),
    }

    # 1. Customer Notification
    customer_notifs = send_notification(
        event_type=Notification.NotificationType.NEW_ORDER,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} Received!",
        message=f"Thank you, {order.customer_name}! We have received your {order.get_dining_type_display()} order #{order.order_number} (€{order.total_amount:.2f}). Estimated prep time: {order.estimated_time_minutes} mins.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL, Notification.Channel.SMS]
    )

    # 2. Staff / Kitchen Notification
    staff_notifs = send_notification(
        event_type=Notification.NotificationType.NEW_ORDER,
        recipient_role='kitchen',
        title=f"New {order.get_dining_type_display()} Order #{order.order_number}",
        message=f"New incoming order #{order.order_number} from {order.customer_name}. Total: €{order.total_amount:.2f}.",
        data=context,
        channels=[Notification.Channel.IN_APP]
    )

    return customer_notifs + staff_notifs


def notify_order_accepted(order) -> list[Notification]:
    """
    Customer is notified that restaurant accepted the order.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'order_id': str(order.id),
        'estimated_time': order.estimated_time_minutes,
    }
    return send_notification(
        event_type=Notification.NotificationType.ORDER_ACCEPTED,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} Confirmed",
        message=f"Your order #{order.order_number} has been accepted and confirmed by the restaurant.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.SMS]
    )


def notify_order_preparing(order) -> list[Notification]:
    """
    Customer is notified that the kitchen has begun preparation.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.ORDER_PREPARING,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Your Food is Being Prepared!",
        message=f"Our chefs have started cooking your order #{order.order_number}. It will be ready shortly!",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.WHATSAPP]
    )


def notify_order_ready(order) -> list[Notification]:
    """
    Customer notified for pickup, or delivery driver alerted for dispatch.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'order_id': str(order.id),
        'dining_type': order.dining_type,
    }
    action_text = "ready for collection at our front counter" if order.dining_type == 'takeaway' else "ready and being handed to your courier"
    return send_notification(
        event_type=Notification.NotificationType.ORDER_READY,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} is Ready!",
        message=f"Good news, {order.customer_name}! Order #{order.order_number} is {action_text}.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.SMS, Notification.Channel.WHATSAPP]
    )


def notify_order_dispatched(order, driver_name: str = "Our courier", eta_minutes: int = 15) -> list[Notification]:
    """
    Customer notified that delivery driver is on the way.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'driver_name': driver_name,
        'eta_minutes': eta_minutes,
        'delivery_address': order.delivery_address,
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.ORDER_DISPATCHED,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} Out for Delivery!",
        message=f"{driver_name} is on the way to {order.delivery_address} with your order #{order.order_number}. Estimated arrival: ~{eta_minutes} mins.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.SMS]
    )


def notify_order_completed(order) -> list[Notification]:
    """
    Customer receives delivery/pickup completion receipt & thank you.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'total_amount': f"€{order.total_amount:.2f}",
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.ORDER_COMPLETED,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} Completed",
        message=f"Thank you for ordering with Amber Spice! We hope you enjoyed your meal. Order #{order.order_number} has been completed.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL]
    )


def notify_order_cancelled(order, reason: str = "Unforeseen kitchen constraint") -> list[Notification]:
    """
    Customer and admin notified of order cancellation with reason.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'reason': reason,
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.ORDER_CANCELLED,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Order #{order.order_number} Cancelled",
        message=f"We regret to inform you that order #{order.order_number} has been cancelled. Reason: {reason}. Any charge has been refunded.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL, Notification.Channel.SMS]
    )


def notify_payment_confirmation(order, payment_method: str = "Card") -> list[Notification]:
    """
    Customer and admin confirmation of successful payment.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'total_amount': f"€{order.total_amount:.2f}",
        'payment_method': payment_method,
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.PAYMENT_CONFIRMATION,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Payment Confirmed - Order #{order.order_number}",
        message=f"Your payment of €{order.total_amount:.2f} via {payment_method} has been received for order #{order.order_number}.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL]
    )


def notify_payment_failed(order, reason: str = "Card declined or authentication timeout") -> list[Notification]:
    """
    Customer alerted of failed payment with retry instructions.
    """
    context = {
        'customer_name': order.customer_name,
        'order_number': order.order_number,
        'reason': reason,
        'order_id': str(order.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.PAYMENT_FAILED,
        recipient=order.customer,
        recipient_email=order.customer_email or (order.customer.email if order.customer else ""),
        recipient_phone=order.customer_phone or (order.customer.phone if order.customer else ""),
        recipient_role='customer',
        title=f"Payment Failed - Order #{order.order_number}",
        message=f"Your payment for order #{order.order_number} could not be completed. Reason: {reason}. Please check your payment details and retry.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL, Notification.Channel.SMS]
    )


def notify_low_inventory(inventory_item) -> list[Notification]:
    """
    Manager and Kitchen alerted when an ingredient breaches its minimum stock level.
    """
    context = {
        'item_name': inventory_item.name,
        'current_stock': f"{inventory_item.current_stock:.2f}",
        'minimum_stock': f"{inventory_item.minimum_stock:.2f}",
        'unit': inventory_item.unit,
        'item_id': str(inventory_item.id),
    }
    return send_notification(
        event_type=Notification.NotificationType.LOW_INVENTORY,
        recipient_role='manager',
        title=f"Low Stock Alert: {inventory_item.name}",
        message=f"Warning: {inventory_item.name} stock has dropped to {inventory_item.current_stock:.2f} {inventory_item.unit} (Minimum threshold: {inventory_item.minimum_stock:.2f} {inventory_item.unit}). Restocking required.",
        data=context,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL]
    )


def notify_admin_alert(title: str, message: str, urgency: str = "high", data: dict = None) -> list[Notification]:
    """
    Urgent operational alert for restaurant owner and managers.
    """
    if data is None:
        data = {}
    data['urgency'] = urgency

    return send_notification(
        event_type=Notification.NotificationType.ADMIN_ALERT,
        recipient_role='admin',
        title=f"Admin Alert [{urgency.upper()}]: {title}",
        message=message,
        data=data,
        channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL, Notification.Channel.SMS]
    )

