from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import DeliveryEvent, DeliveryJob, Order, OrderEvent, RiderProfile


class DeliveryWorkflow:
    @staticmethod
    def job(order):
        job, _ = DeliveryJob.objects.get_or_create(order=order, defaults={
            'stage': 'assigned' if order.assigned_delivery_staff_id else 'unassigned',
        })
        return job

    @staticmethod
    def event(order, actor, action, note='', amount=None):
        DeliveryEvent.objects.create(order=order, actor=actor, action=action, note=note, amount=amount)

    @staticmethod
    def clear_issue(job):
        job.issue_code = ''
        job.issue_note = ''
        job.issue_reported_at = None

    @classmethod
    def assign(cls, order, rider, actor):
        job = cls.job(order)
        if order.assigned_delivery_staff_id == rider.id and job.stage != 'unassigned':
            return
        if job.stage in ['picked_up', 'arrived', 'returning', 'returned', 'delivered']:
            raise ValidationError({'detail': 'An order already picked up cannot be reassigned.'})
        if job.issue_code:
            cls.event(order, actor, 'issue_resolved', 'Reassigned before pickup.')
        cls.clear_issue(job)
        job.stage = 'assigned'
        job.accepted_at = None
        job.save()
        order.assigned_delivery_staff = rider
        order.save(update_fields=['assigned_delivery_staff', 'updated_at'])
        cls.event(order, actor, 'assigned', f'Assigned to {rider.get_full_name() or rider.username}.')

    @staticmethod
    def require_duty(user):
        profile, _ = RiderProfile.objects.select_for_update().get_or_create(user=user)
        if not profile.on_duty:
            raise ValidationError({'detail': 'Start your shift before accepting or progressing deliveries.'})

    @staticmethod
    def set_order_status(order, status):
        if order.status != status:
            order.status = status
            order.save(update_fields=['status', 'updated_at'])
            OrderEvent.objects.create(order=order, status=status)

    @classmethod
    def progress(cls, order, user, action):
        job = cls.job(order)
        stages = {
            'accept': ('assigned', 'accepted', 'accepted_at'),
            'pickup': ('accepted', 'picked_up', 'picked_up_at'),
            'arrive': ('picked_up', 'arrived', 'arrived_at'),
            'complete': ('arrived', 'delivered', 'delivered_at'),
        }
        previous, target, timestamp = stages[action]
        if order.status == 'cancelled':
            raise ValidationError({'detail': 'This order has been cancelled.'})
        # Replays acknowledge the saved transition without creating duplicate events.
        if getattr(job, timestamp) is not None:
            return
        cls.require_duty(user)
        if job.issue_code:
            raise ValidationError({'detail': 'Dispatch must resolve the reported issue before you continue.'})
        if job.stage != previous:
            raise ValidationError({'detail': f'Cannot {action} a delivery at stage {job.stage}.'})
        if action == 'pickup' and order.status != 'ready':
            raise ValidationError({'detail': 'Wait until the kitchen marks this order ready.'})
        if action in ['arrive', 'complete'] and order.status != 'out_for_delivery':
            raise ValidationError({'detail': 'This order is not out for delivery.'})
        job.stage = target
        setattr(job, timestamp, timezone.now())
        job.save()
        if action == 'pickup':
            cls.set_order_status(order, 'out_for_delivery')
        elif action == 'complete':
            cls.set_order_status(order, 'delivered')
        cls.event(order, user, target)

    @classmethod
    def decline(cls, order, user, note):
        job = cls.job(order)
        if job.stage not in ['assigned', 'accepted'] or order.status not in ['pending', 'preparing', 'ready']:
            raise ValidationError({'detail': 'Only an assignment not yet picked up can be declined. Report an issue instead.'})
        cls.event(order, user, 'declined', note)
        if job.issue_code:
            cls.event(order, user, 'issue_resolved', 'Assignment declined before pickup.')
        cls.clear_issue(job)
        job.stage = 'unassigned'
        job.accepted_at = None
        job.save()
        order.assigned_delivery_staff = None
        order.save(update_fields=['assigned_delivery_staff', 'updated_at'])

    @classmethod
    def report_issue(cls, order, user, code, note):
        job = cls.job(order)
        if order.status in ['delivered', 'cancelled']:
            raise ValidationError({'detail': 'Report issues before completing a delivery.'})
        if job.issue_code:
            if job.issue_code == code and job.issue_note == note:
                return
            raise ValidationError({'detail': 'An issue is already open. Contact dispatch and wait for resolution.'})
        job.issue_code, job.issue_note, job.issue_reported_at = code, note, timezone.now()
        job.save()
        cls.event(order, user, 'issue_reported', f'{code}: {note}')

    @classmethod
    def resolve_issue(cls, order, user, note):
        job = cls.job(order)
        if not job.issue_code:
            return
        cls.event(order, user, 'issue_resolved', note)
        cls.clear_issue(job)
        job.save()

    @classmethod
    def record_cash(cls, order, user):
        if order.payment_method != 'cash' or order.status != 'delivered' or order.payment_status == 'refunded':
            raise ValidationError({'detail': 'Record cash only after delivery or collection handover.'})
        if order.payment_status == 'paid':
            return
        order.payment_status = 'paid'
        order.save(update_fields=['payment_status', 'updated_at'])
        if order.dining_type == 'delivery':
            job = cls.job(order)
            job.cash_collected_at = timezone.now()
            job.save()
            cls.event(order, user, 'cash_collected', amount=order.total_amount)

    @classmethod
    def request_return(cls, order, user, note):
        job = cls.job(order)
        if job.stage == 'returning':
            return
        if order.status != 'out_for_delivery' or job.stage not in ['picked_up', 'arrived'] or not job.issue_code:
            raise ValidationError({'detail': 'Approve a return only for an in-transit delivery with a reported issue.'})
        cls.event(order, user, 'return_requested', note)
        cls.clear_issue(job)
        job.stage = 'returning'
        job.return_requested_at = timezone.now()
        job.save()

    @classmethod
    def confirm_return(cls, order, user):
        job = cls.job(order)
        if job.stage == 'returned':
            return
        cls.require_duty(user)
        if job.stage != 'returning' or job.issue_code:
            raise ValidationError({'detail': 'Dispatch must approve this return and resolve any issue first.'})
        job.stage = 'returned'
        job.returned_at = timezone.now()
        job.save()
        cls.set_order_status(order, 'cancelled')
        cls.event(order, user, 'returned', 'Order returned to restaurant staff. No payment or refund was performed.')

    @classmethod
    def sync_operator_status(cls, order, user, status):
        if order.dining_type != 'delivery' or not order.assigned_delivery_staff_id:
            return
        job = cls.job(order)
        if job.stage in ['returning', 'returned'] and status in ['out_for_delivery', 'delivered']:
            raise ValidationError({'detail': 'This delivery has an approved return. Confirm its return to restaurant staff instead.'})
        if job.issue_code and status in ['out_for_delivery', 'delivered']:
            raise ValidationError({'detail': 'Resolve the delivery issue before progressing this order.'})
        transitions = {'out_for_delivery': ('picked_up', 'picked_up_at'), 'delivered': ('delivered', 'delivered_at')}
        if status in transitions:
            job.stage, timestamp = transitions[status]
            if getattr(job, timestamp) is None:
                setattr(job, timestamp, timezone.now())
                cls.event(order, user, job.stage, 'Confirmed by restaurant operations.')
            job.save()
        elif status == 'cancelled':
            job.stage = 'cancelled'
            cls.clear_issue(job)
            job.save()
            cls.event(order, user, 'cancelled')

    @staticmethod
    def allowed_actions(order, user):
        if not user.has_restaurant_permission('deliveries:update_status'):
            return []
        job = getattr(order, 'delivery_job', None)
        if not job or order.status == 'cancelled':
            return []
        if order.status == 'delivered':
            return ['collect-cash'] if order.payment_method == 'cash' and order.payment_status == 'pending' else []
        if job.issue_code:
            return ['decline'] if job.stage in ['assigned', 'accepted'] else []
        actions = ['report-issue']
        if job.stage in ['assigned', 'accepted']:
            actions.append('decline')
        profile = getattr(user, 'rider_profile', None)
        if profile and profile.on_duty:
            if job.stage == 'assigned':
                actions.append('accept')
            elif job.stage == 'accepted' and order.status == 'ready':
                actions.append('pickup')
            elif job.stage == 'picked_up':
                actions.append('arrive')
            elif job.stage == 'arrived':
                actions.append('complete')
            elif job.stage == 'returning':
                actions.append('confirm-return')
        return actions
