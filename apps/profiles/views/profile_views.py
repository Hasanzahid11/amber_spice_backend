from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.profiles.serializers import UserProfileSerializer
from apps.profiles.services import ProfileService


class UserProfileView(APIView):
    """
    GET /api/v1/profiles/me/
    PATCH /api/v1/profiles/me/
    Manage the authenticated user's profile, loyalty status, and personal details.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserProfileSerializer})
    def get(self, request):
        profile = ProfileService.get_or_create_profile(request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    @extend_schema(request=UserProfileSerializer, responses={200: UserProfileSerializer})
    def patch(self, request):
        profile = ProfileService.update_profile(request.user, request.data)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

