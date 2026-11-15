from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.menu.models import Dish
from .models import InventoryItem, Recipe, StockMovement
from .utils import convert_quantity


def calculate_order_consumption(items_data: list[dict]) -> dict:
    """
    Calculates recipe-based ingredient consumption for a set of menu items and quantities.
    Example: 10 portions of Chicken Biryani (200g chicken, 100g rice, 20g sauce per portion)
    -> 2000g (2.0kg) chicken, 1000g (1.0kg) rice, 200g (0.2kg) sauce.

    Items data can be provided as:
    [{'dish_id': 1, 'quantity': 10}, ...] or [{'dish': dish_instance, 'quantity': 10}, ...]
    """
    consumed_map = defaultdict(lambda: {
        'item': None,
        'quantity': Decimal('0.000'),
        'unit': '',
        'cost': Decimal('0.00'),
    })

    untracked_dishes = []
    total_food_cost = Decimal('0.00')

    for entry in items_data:
        dish = entry.get('dish')
        if not dish and entry.get('dish_id'):
            dish = Dish.objects.filter(id=entry.get('dish_id')).first()

        if not dish:
            continue

        quantity = int(entry.get('quantity', 1))
        if quantity <= 0:
            continue

        recipe = getattr(dish, 'recipe', None)
        if not recipe or not recipe.is_active:
            untracked_dishes.append({
                'dish_id': dish.id,
                'dish_name': dish.name,
                'quantity': quantity,
                'reason': 'No active recipe defined'
            })
            continue

        multiplier = Decimal(str(quantity)) / Decimal(str(recipe.yield_portions))

        for rec_ing in recipe.ingredients.select_related('inventory_item').all():
            item = rec_ing.inventory_item
            req_qty = rec_ing.quantity * multiplier
            converted_qty = convert_quantity(req_qty, rec_ing.unit, item.unit)
            ing_cost = (converted_qty * item.purchase_price).quantize(Decimal('0.01'))

            data = consumed_map[item.id]
            data['item'] = item
            data['quantity'] += converted_qty
            data['unit'] = item.unit
            data['cost'] += ing_cost
            total_food_cost += ing_cost

    consumed_list = []
    insufficient_items = []

    for item_id, data in consumed_map.items():
        item = data['item']
        qty_needed = data['quantity'].quantize(Decimal('0.001'))
        curr_stock = item.current_stock.quantize(Decimal('0.001'))
        remaining = (curr_stock - qty_needed).quantize(Decimal('0.001'))
        has_sufficient = remaining >= Decimal('0.000')

        if not has_sufficient:
            insufficient_items.append({
                'item_id': item.id,
                'name': item.name,
                'category': item.category,
                'current_stock': float(curr_stock),
                'required_quantity': float(qty_needed),
                'shortage': float(abs(remaining)),
                'unit': item.unit,
            })

        reorder_threshold = item.reorder_level if item.reorder_level > 0 else item.minimum_stock
        reorder_alert = remaining <= reorder_threshold if reorder_threshold > 0 else False

        consumed_list.append({
            'item_id': item.id,
            'name': item.name,
            'category': item.category,
            'unit': item.unit,
            'quantity_consumed': float(qty_needed),
            'current_stock': float(curr_stock),
            'projected_remaining_stock': float(remaining),
            'has_sufficient_stock': has_sufficient,
            'cost': float(data['cost']),
            'reorder_alert': reorder_alert,
        })

    return {
        'total_food_cost': float(total_food_cost.quantize(Decimal('0.01'))),
        'can_fulfill': len(insufficient_items) == 0,
        'consumed_ingredients': consumed_list,
        'insufficient_items': insufficient_items,
        'untracked_dishes': untracked_dishes,
    }


@transaction.atomic
def deduct_order_inventory(order, performed_by=None) -> list[StockMovement]:
    """
    Executes actual stock deduction for a placed order based on recipes of its items.
    Idempotent: will not deduct the same order twice.
    """
    if order.inventory_movements.exists():
        return list(order.inventory_movements.all())

    # Build items data from order.items
    items_data = []
    for item in order.items.all():
        if item.dish:
            items_data.append({
                'dish': item.dish,
                'quantity': item.quantity,
            })

    if not items_data:
        return []

    consumption_summary = calculate_order_consumption(items_data)
    movements = []

    for ing in consumption_summary['consumed_ingredients']:
        item = InventoryItem.objects.select_for_update().get(id=ing['item_id'])
        qty_to_deduct = Decimal(str(ing['quantity_consumed']))

        previous_stock = item.current_stock
        new_stock = previous_stock - qty_to_deduct
        item.current_stock = new_stock
        item.save(update_fields=['current_stock', 'last_restocked', 'updated_at'])

        movement = StockMovement.objects.create(
            inventory_item=item,
            movement_type=StockMovement.MovementType.CONSUMPTION,
            quantity=-qty_to_deduct,
            previous_stock=previous_stock,
            new_stock=new_stock,
            unit_cost=item.purchase_price,
            total_cost=qty_to_deduct * item.purchase_price,
            reference=order.order_number,
            order=order,
            performed_by=performed_by,
            notes=f"Order {order.order_number} ({order.customer_name}) consumption"
        )
        movements.append(movement)

    return movements


@transaction.atomic
def restock_inventory_item(
    item: InventoryItem,
    quantity: Decimal,
    purchase_price: Decimal = None,
    supplier: str = None,
    batch_number: str = None,
    expiry_date=None,
    performed_by=None,
    notes: str = ""
) -> StockMovement:
    """Restocks inventory item and logs the purchase transaction."""
    qty = Decimal(str(quantity))
    previous_stock = item.current_stock
    new_stock = previous_stock + qty

    item.current_stock = new_stock
    update_fields = ['current_stock', 'last_restocked', 'updated_at']

    if purchase_price is not None:
        item.purchase_price = Decimal(str(purchase_price))
        update_fields.append('purchase_price')

    if supplier:
        item.supplier = supplier
        update_fields.append('supplier')

    if batch_number:
        item.batch_number = batch_number
        update_fields.append('batch_number')

    if expiry_date:
        item.expiry_date = expiry_date
        update_fields.append('expiry_date')

    item.save(update_fields=update_fields)

    unit_cost = item.purchase_price
    total_cost = qty * unit_cost

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.PURCHASE,
        quantity=qty,
        previous_stock=previous_stock,
        new_stock=new_stock,
        unit_cost=unit_cost,
        total_cost=total_cost,
        reference=f"RESTOCK-{timezone.now().strftime('%Y%m%d')}",
        performed_by=performed_by,
        notes=notes or f"Restocked {qty} {item.unit}"
    )
    return movement


@transaction.atomic
def record_waste(
    item: InventoryItem,
    quantity: Decimal,
    reason: str = "",
    performed_by=None
) -> StockMovement:
    """Records kitchen food waste, spoilage, or damaged ingredients."""
    qty = Decimal(str(quantity))
    previous_stock = item.current_stock
    new_stock = max(Decimal('0.000'), previous_stock - qty)

    item.current_stock = new_stock
    item.save(update_fields=['current_stock', 'updated_at'])

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.WASTE,
        quantity=-qty,
        previous_stock=previous_stock,
        new_stock=new_stock,
        unit_cost=item.purchase_price,
        total_cost=qty * item.purchase_price,
        reference="WASTE-LOG",
        performed_by=performed_by,
        notes=reason or "Kitchen spoilage / waste"
    )
    return movement


@transaction.atomic
def adjust_stock(
    item: InventoryItem,
    new_stock: Decimal,
    reason: str = "",
    performed_by=None
) -> StockMovement:
    """Reconciles physical count differences during inventory auditing."""
    target_stock = Decimal(str(new_stock))
    previous_stock = item.current_stock
    delta = target_stock - previous_stock

    item.current_stock = target_stock
    item.save(update_fields=['current_stock', 'updated_at'])

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.ADJUSTMENT,
        quantity=delta,
        previous_stock=previous_stock,
        new_stock=target_stock,
        unit_cost=item.purchase_price,
        total_cost=abs(delta) * item.purchase_price,
        reference="STOCK-AUDIT",
        performed_by=performed_by,
        notes=reason or f"Stock adjusted from {previous_stock} to {target_stock}"
    )
    return movement

