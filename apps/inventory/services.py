from decimal import Decimal
import logging
from django.db import transaction
from django.utils import timezone
from .models import InventoryItem, DishRecipe, StockTransaction, StockAlert

logger = logging.getLogger(__name__)


def calculate_dish_cost_data(dish):
    """
    Computes recipe food cost, food cost %, gross profit margin %,
    and maximum prepareable portions based on available ingredient stock.
    """
    recipe_items = list(dish.recipe_items.select_related('ingredient').all())
    total_cost = Decimal('0.00')
    max_portions = None

    for item in recipe_items:
        cost = item.cost
        total_cost += cost
        if item.quantity > Decimal('0'):
            portions = int(item.ingredient.current_stock // item.quantity)
            if max_portions is None or portions < max_portions:
                max_portions = portions

    if max_portions is None:
        max_portions = 0

    dish_price = Decimal(str(dish.price)) if dish.price else Decimal('0.00')
    food_cost_pct = (total_cost / dish_price * Decimal('100.0')).quantize(Decimal('0.01')) if dish_price > 0 else Decimal('0.00')
    gross_profit = (dish_price - total_cost).quantize(Decimal('0.01'))
    gross_margin_pct = (gross_profit / dish_price * Decimal('100.0')).quantize(Decimal('0.01')) if dish_price > 0 else Decimal('0.00')

    return {
        'dish': dish,
        'recipe_items': recipe_items,
        'total_food_cost': total_cost.quantize(Decimal('0.01')),
        'food_cost_percent': food_cost_pct,
        'gross_profit': gross_profit,
        'gross_margin_percent': gross_margin_pct,
        'max_portions_available': max_portions,
    }


def trigger_stock_alert_if_needed(item, reported_by=None, note=''):
    """
    Triggers a StockAlert and sends real-time notifications if stock is <= minimum_stock.
    Avoids duplicate active alerts within 12 hours.
    """
    if item.current_stock > item.minimum_stock:
        return None

    recent_cutoff = timezone.now() - timezone.timedelta(hours=12)
    existing = StockAlert.objects.filter(item=item, resolved=False, created_at__gte=recent_cutoff).first()
    if existing:
        return existing

    pct = int((item.current_stock / item.minimum_stock * Decimal('100.0'))) if item.minimum_stock > 0 else 0
    pct = max(0, min(100, pct))
    alert_note = note or f"Stock low: {item.current_stock} {item.unit} remaining (min: {item.minimum_stock} {item.unit})"
    
    alert = StockAlert.objects.create(
        item=item,
        reported_by=reported_by,
        stock_remaining_percent=pct,
        note=alert_note,
        resolved=False,
    )

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.notifications.models import Notification
        channel_layer = get_channel_layer()
        if channel_layer:
            alert_payload = {
                'id': str(alert.id),
                'ingredientName': item.name,
                'stockRemainingPercent': alert.stock_remaining_percent,
                'note': alert.note,
                'reporterName': reported_by.username if reported_by else 'System / Auto-depletion',
                'createdAt': alert.created_at.isoformat(),
            }
            notif = Notification.objects.create(
                type=Notification.NotificationType.STOCK_ALERT,
                target_role='admin',
                title=f"Low Stock: {item.name}",
                message=f"{item.name} is at {alert.stock_remaining_percent}% stock ({item.current_stock} {item.unit} left).",
                data=alert_payload,
            )
            async_to_sync(channel_layer.group_send)(
                'admin_operations',
                {
                    'type': 'stock.alert',
                    'alert': alert_payload,
                    'notification': {
                        'id': notif.id,
                        'type': notif.type,
                        'title': notif.title,
                        'message': notif.message,
                        'createdAt': notif.created_at.isoformat(),
                    },
                }
            )
    except Exception as e:
        logger.warning("Could not dispatch stock alert broadcast: %s", e)

    return alert


@transaction.atomic
def deplete_order_inventory(order, user=None):
    """
    Idempotently depletes inventory stock for all items in an order based on their DishRecipe BOM.
    Records StockTransaction records for full auditability and triggers alerts if stock drops below minimum.
    """
    if not order or not order.pk:
        return []

    # Idempotency check: don't deplete twice for the same order
    already_depleted = StockTransaction.objects.filter(
        order=order,
        transaction_type=StockTransaction.TransactionType.CONSUMPTION
    ).exists()
    if already_depleted:
        return []

    transactions = []
    order_items = list(order.items.select_related('dish').all())

    for oi in order_items:
        if not oi.dish:
            continue

        recipe_items = list(DishRecipe.objects.filter(dish=oi.dish).select_related('ingredient'))
        for r_item in recipe_items:
            ing = InventoryItem.objects.select_for_update().get(pk=r_item.ingredient_id)
            required_qty = (Decimal(str(r_item.quantity)) * Decimal(str(oi.quantity))).quantize(Decimal('0.001'))
            
            # Reduce stock (do not drop below 0)
            new_stock = max(Decimal('0.00'), ing.current_stock - required_qty)
            ing.current_stock = new_stock
            ing.save(update_fields=['current_stock', 'last_restocked'])

            unit_cost = ing.cost_per_unit or Decimal('0.0000')
            total_cost = (required_qty * unit_cost).quantize(Decimal('0.01'))

            tx = StockTransaction.objects.create(
                item=ing,
                transaction_type=StockTransaction.TransactionType.CONSUMPTION,
                quantity_delta=-required_qty,
                unit_cost=unit_cost,
                total_cost=total_cost,
                balance_after=new_stock,
                order=order,
                created_by=user,
                notes=f"Order #{order.order_number}: {oi.quantity}x {oi.name} ({r_item.quantity} {r_item.unit or ing.unit}/portion)"
            )
            transactions.append(tx)

            # Trigger alert if stock is now low or critical
            trigger_stock_alert_if_needed(ing, reported_by=user)

    return transactions


@transaction.atomic
def restore_order_inventory(order, user=None):
    """
    Restores inventory when an order is cancelled, if it had previously been depleted.
    """
    if not order or not order.pk:
        return []

    consumptions = list(StockTransaction.objects.filter(
        order=order,
        transaction_type=StockTransaction.TransactionType.CONSUMPTION
    ).select_related('item'))

    if not consumptions:
        return []

    # Check if already restored
    already_restored = StockTransaction.objects.filter(
        order=order,
        transaction_type=StockTransaction.TransactionType.ADJUSTMENT,
        notes__startswith="Restocked from cancelled"
    ).exists()
    if already_restored:
        return []

    restored = []
    for tx in consumptions:
        ing = InventoryItem.objects.select_for_update().get(pk=tx.item_id)
        restore_qty = abs(tx.quantity_delta)
        new_stock = ing.current_stock + restore_qty
        ing.current_stock = new_stock
        ing.save(update_fields=['current_stock', 'last_restocked'])

        unit_cost = ing.cost_per_unit or Decimal('0.0000')
        total_cost = (restore_qty * unit_cost).quantize(Decimal('0.01'))

        adj = StockTransaction.objects.create(
            item=ing,
            transaction_type=StockTransaction.TransactionType.ADJUSTMENT,
            quantity_delta=restore_qty,
            unit_cost=unit_cost,
            total_cost=total_cost,
            balance_after=new_stock,
            order=order,
            created_by=user,
            notes=f"Restocked from cancelled Order #{order.order_number}"
        )
        restored.append(adj)

    return restored
