import urllib.parse
import jwt
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str):
    try:
        decoded = jwt.decode(token_str, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = decoded.get('user_id')
        if not user_id:
            return None
        return User.objects.filter(id=user_id, is_active=True).first()
    except Exception:
        return None


class OperationsConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for live operations feed:
    Broadcasts real-time events to Managers, Admins, and Operations staff.
    Connects to /ws/operations/
    """
    GROUP_NAME = 'admin_operations'

    async def connect(self):
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = urllib.parse.parse_qs(query_string)
        token = params.get('token', [None])[0]

        user = None
        if token:
            user = await get_user_from_token(token)

        # Allow authenticated staff/admin or dev fallback
        if user and (user.is_staff or user.is_superuser or user.role in ['admin', 'super_admin', 'manager']):
            self.user = user
        elif settings.DEBUG:
            self.user = user  # allow dev connection
        else:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send_json({
            'type': 'connection.established',
            'channel': 'operations',
            'user': self.user.username if self.user else 'guest_dev',
            'role': getattr(self.user, 'role', 'admin') if self.user else 'admin',
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type')
        if msg_type == 'ping':
            await self.send_json({'type': 'pong'})

    # Channel Layer Event Handlers
    async def order_created(self, event):
        await self.send_json({
            'type': 'order.created',
            'order': event['order'],
            'notification': event.get('notification'),
        })

    async def order_status_updated(self, event):
        await self.send_json({
            'type': 'order.status_updated',
            'order': event['order'],
            'notification': event.get('notification'),
        })

    async def stock_alert(self, event):
        await self.send_json({
            'type': 'stock.alert',
            'alert': event.get('alert'),
        })

    async def customer_arrived(self, event):
        await self.send_json({
            'type': 'customer.arrived',
            'order': event['order'],
            'notification': event.get('notification'),
        })


class KitchenConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for Kitchen Display System (KDS):
    Broadcasts real-time tickets to Chefs and Kitchen Staff.
    Connects to /ws/kitchen/
    """
    GROUP_NAME = 'kitchen_kds'

    async def connect(self):
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = urllib.parse.parse_qs(query_string)
        token = params.get('token', [None])[0]

        user = None
        if token:
            user = await get_user_from_token(token)

        if user and (user.is_staff or user.is_superuser or user.role in ['admin', 'super_admin', 'manager', 'kitchen_staff', 'chef']):
            self.user = user
        elif settings.DEBUG:
            self.user = user
        else:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send_json({
            'type': 'connection.established',
            'channel': 'kitchen_kds',
            'user': self.user.username if self.user else 'guest_chef',
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type')
        if msg_type == 'ping':
            await self.send_json({'type': 'pong'})

    # Channel Layer Event Handlers
    async def kitchen_ticket_received(self, event):
        await self.send_json({
            'type': 'kitchen.ticket_received',
            'ticket': event['ticket'],
            'notification': event.get('notification'),
        })

    async def kitchen_ticket_updated(self, event):
        await self.send_json({
            'type': 'kitchen.ticket_updated',
            'ticket': event['ticket'],
        })

    async def customer_arrived(self, event):
        await self.send_json({
            'type': 'customer.arrived',
            'order': event['order'],
            'notification': event.get('notification'),
        })
