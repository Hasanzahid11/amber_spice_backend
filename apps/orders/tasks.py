from celery import shared_task
from django.utils import timezone


@shared_task
def process_new_order_notification(order_id):
    """
    Background asynchronous task triggered when an order is created.
    Communicates via Redis broker.
    """
    from .models import Order
    try:
        order = Order.objects.get(id=order_id)
        # In a real environment, this can push to WebSocket channels, email customer,
        # or send thermal print commands to kitchen stations.
        print(f"[{timezone.now()}] [Celery] Processed notification for Order #{order.order_number}")
        return f"Order {order.order_number} processed successfully"
    except Order.DoesNotExist:
        return f"Order {order_id} not found"

