import secrets

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .delivery_workflow import DeliveryWorkflow


class KitchenHandover:
    @staticmethod
    def can_manage(user):
        return bool(user and user.is_authenticated and user.is_restaurant_staff and not user.is_delivery_staff
                    and (user.has_restaurant_permission('kitchen:update_status') or user.has_restaurant_permission('orders:update_status')))

    @classmethod
    def can_release(cls, order, user):
        job = getattr(order, 'delivery_job', None)
        rider = order.assigned_delivery_staff
        return bool(cls.can_manage(user) and order.status == 'ready' and order.dining_type == 'delivery'
                    and job and job.stage == 'accepted' and not job.issue_code and rider and rider.is_active)

    @staticmethod
    def clear(job):
        job.handed_over_at = None
        job.handed_over_by = None
        job.handover_code = ''
        job.bag_count = 0
        job.packed_items = []
        job.bags_sealed = False
        job.pickup_verified_at = None
        job.delivery_verified_at = None

    @classmethod
    def release(cls, order, user, rider_id, bag_count, items, sealed):
        if not cls.can_release(order, user):
            raise ValidationError({'detail': 'A ready delivery, accepted active rider and no open issue are required for kitchen handover.'})
        if rider_id != order.assigned_delivery_staff_id:
            raise ValidationError({'rider_id': 'The assigned rider changed. Reload the ticket and check the rider again.'})
        if not sealed:
            raise ValidationError({'sealed': 'Check and seal the food bags before handover.'})
        expected = {item.id: item.quantity for item in order.items.all()}
        received = {item['item_id']: item['quantity'] for item in items}
        if not expected or len(received) != len(items) or received != expected:
            raise ValidationError({'items': 'Match every item ID and quantity on this order ticket. Missing, duplicate or different-order items are not allowed.'})
        job = DeliveryWorkflow.job(order)
        if job.handed_over_at and job.bag_count == bag_count:
            return job
        updated = bool(job.handed_over_at)
        job.handed_over_at = timezone.now()
        job.handed_over_by = user
        job.handover_code = ''.join(secrets.choice('ABCDEFGHJKMNPQRSTUVWXYZ23456789') for _ in range(8))
        job.bag_count = bag_count
        job.bags_sealed = True
        job.packed_items = [{'item_id': item.id, 'name': item.name, 'quantity': item.quantity, 'customizations': item.customizations} for item in order.items.all()]
        job.save()
        DeliveryWorkflow.event(order, user, 'handover_updated' if updated else 'kitchen_handover', f'{bag_count} sealed bag(s), all ticket items checked, handed to {order.assigned_delivery_staff.get_full_name() or order.assigned_delivery_staff.username}.')
        return job

    @staticmethod
    def verify(job, order, ticket_code, bag_count, recipient_confirmed=False, delivery=False):
        if not delivery and (not job.handed_over_at or not job.handover_code or not job.bags_sealed):
            raise ValidationError({'detail': 'Wait for the kitchen to record the food handover and attach the ticket.'})
        # Existing in-transit orders retain their original printed order-number
        # verification; new handovers always use the private bag-ticket code.
        expected = job.handover_code or (order.order_number if delivery and job.picked_up_at else '')
        if not expected or not secrets.compare_digest(ticket_code.strip().upper(), expected.upper()):
            raise ValidationError({'ticket_code': 'This bag ticket does not match the selected order. Check the customer, order number and food bags.'})
        if job.bag_count and bag_count != job.bag_count:
            raise ValidationError({'bag_count': 'The number of bags does not match the kitchen handover.'})
        if delivery and not recipient_confirmed:
            raise ValidationError({'recipient_confirmed': 'Check the customer name, delivery address and bag ticket before confirming handover.'})
