from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Notification
from .serializers import NotificationSerializer


@extend_schema_view(
    list=extend_schema(description='List live operational notifications for staff/admin with unread filtering.'),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False) or not getattr(user, 'is_authenticated', False):
            return Notification.objects.none()
        queryset = Notification.objects.all()

        # Role-based visibility
        if not (user.is_superuser or user.role in ['admin', 'super_admin', 'manager']):
            if user.role in ['kitchen_staff', 'chef']:
                queryset = queryset.filter(target_role__in=['kitchen', 'all'])
            elif user.role == 'delivery_staff':
                queryset = queryset.filter(target_role__in=['delivery', 'all'])
            else:
                queryset = queryset.filter(user=user)

        # Unread filter
        unread_only = self.request.query_params.get('unread')
        if unread_only and unread_only.lower() in ['true', '1']:
            queryset = queryset.filter(is_read=False)

        return queryset[:50]  # return last 50 notifications

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        queryset = self.get_queryset().filter(is_read=False)
        count = queryset.update(is_read=True)
        return Response({'message': f'Marked {count} notifications as read.', 'markedCount': count})

    @action(detail=True, methods=['patch'], url_path='read')
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)
