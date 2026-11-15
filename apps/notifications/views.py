from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagerOrAdmin
from .models import Notification, NotificationTemplate, NotificationPreference
from .serializers import (
    NotificationSerializer,
    NotificationTemplateSerializer,
    NotificationPreferenceSerializer,
    SendNotificationRequestSerializer,
)
from .services import send_notification


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Inbox & Notification Management ViewSet.
    - Customers: view their personal order & payment updates, mark read.
    - Staff (Admin, Kitchen, Manager): view assigned and role-based notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Notification.objects.all()

        # If Owner/Admin or Manager: can see all or filter by role
        if user.is_owner_or_admin or user.is_manager:
            role_param = self.request.query_params.get('role', None)
            if role_param:
                qs = qs.filter(recipient_role=role_param)
            return qs

        # Kitchen Staff: see kitchen role notifications + personal
        if getattr(user, 'is_kitchen_staff', False) or user.role == 'kitchen_staff':
            return qs.filter(Q(recipient=user) | Q(recipient_role='kitchen'))

        # Delivery Staff: see delivery role notifications + personal
        if getattr(user, 'is_delivery_staff', False) or user.role == 'delivery_staff':
            return qs.filter(Q(recipient=user) | Q(recipient_role='delivery'))

        # Standard Customer: only their own notifications
        return qs.filter(
            Q(recipient=user) |
            (Q(recipient_email=user.email) if user.email else Q()) |
            (Q(recipient_phone=user.phone) if user.phone else Q())
        )

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        POST /api/v1/notifications/<id>/mark-read/
        Marks a single notification as read.
        """
        notif = self.get_object()
        notif.mark_read()
        return Response({
            'message': 'Notification marked as read.',
            'id': str(notif.id),
            'isRead': notif.is_read,
            'readAt': notif.read_at.isoformat() if notif.read_at else None
        })

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        POST /api/v1/notifications/mark-all-read/
        Marks all unread notifications in user's inbox as read.
        """
        user_notifications = self.get_queryset().filter(is_read=False)
        count = user_notifications.count()
        user_notifications.update(
            is_read=True,
            read_at=timezone.now(),
            status=Notification.Status.READ
        )
        return Response({
            'message': f"Marked {count} notification(s) as read.",
            'markedCount': count
        })

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        GET /api/v1/notifications/unread-count/
        Returns integer count of unread notifications for badge display.
        """
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unreadCount': count})

    @action(detail=False, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def send(self, request):
        """
        POST /api/v1/notifications/send/
        Admin manual broadcast or target alert across channels.
        """
        req_serializer = SendNotificationRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        vdata = req_serializer.validated_data

        notifs = send_notification(
            event_type=vdata['notification_type'],
            recipient_email=vdata.get('recipient_email', ''),
            recipient_phone=vdata.get('recipient_phone', ''),
            recipient_role=vdata.get('recipient_role', ''),
            title=vdata['title'],
            message=vdata['message'],
            data=vdata.get('data', {}),
            channels=vdata.get('channels', None)
        )

        return Response({
            'message': f"Successfully created and dispatched {len(notifs)} notification(s).",
            'notifications': NotificationSerializer(notifs, many=True).data
        }, status=status.HTTP_201_CREATED)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for Notification message templates.
    Restricted to Manager and Owner/Admin.
    """
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsManagerOrAdmin]


class NotificationPreferenceView(APIView):
    """
    GET /api/v1/notifications/preferences/
    PUT/PATCH /api/v1/notifications/preferences/
    Manages channel preferences (Email, SMS, WhatsApp, Push) for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        prefs = NotificationPreference.get_or_create_for_user(request.user)
        serializer = NotificationPreferenceSerializer(prefs)
        return Response(serializer.data)

    def put(self, request):
        prefs = NotificationPreference.get_or_create_for_user(request.user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Notification preferences updated successfully.',
            'preferences': serializer.data
        })

    def patch(self, request):
        return self.put(request)

