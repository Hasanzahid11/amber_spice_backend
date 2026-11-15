try:
    from celery import shared_task
except (ImportError, ModuleNotFoundError):
    # Graceful fallback decorator when Celery is not installed in the environment
    def shared_task(*args, **kwargs):
        def decorator(func):
            def delay(*call_args, **call_kwargs):
                return func(*call_args, **call_kwargs)
            func.delay = delay
            return func
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

from django.utils import timezone


@shared_task
def process_new_order_notification(order_id):
    """
    Background asynchronous task triggered when an order is created.
    Communicates via Redis broker when Celery is running, or falls back to synchronous execution.
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
