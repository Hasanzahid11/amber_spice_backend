from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.profiles.models import UserAddress
from apps.profiles.serializers import UserAddressSerializer
from apps.profiles.services import AddressService


class UserAddressViewSet(viewsets.ModelViewSet):
    """
    CRUD API for user's saved Dublin delivery addresses:
    GET    /api/v1/profiles/addresses/
    POST   /api/v1/profiles/addresses/
    GET    /api/v1/profiles/addresses/<id>/
    PATCH  /api/v1/profiles/addresses/<id>/
    DELETE /api/v1/profiles/addresses/<id>/
    POST   /api/v1/profiles/addresses/<id>/set-default/
    """
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return UserAddress.objects.none()
        return AddressService.get_user_addresses(self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        AddressService.delete_address(self.request.user, instance.id)

    @extend_schema(responses={200: UserAddressSerializer})
    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        address = AddressService.set_default_address(request.user, self.get_object().pk)
        serializer = self.get_serializer(address)
        return Response(serializer.data, status=status.HTTP_200_OK)
