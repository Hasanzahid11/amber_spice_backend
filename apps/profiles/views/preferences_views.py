from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.profiles.serializers import UserPreferencesSerializer
from apps.profiles.services import ProfileService


class UserPreferencesView(APIView):
    """
    GET   /api/v1/profiles/preferences/
    PATCH /api/v1/profiles/preferences/
    Dietary constraints, spice tolerance, allergy flags & notification preferences.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserPreferencesSerializer})
    def get(self, request):
        preferences = ProfileService.get_or_create_preferences(request.user)
        serializer = UserPreferencesSerializer(preferences)
        return Response(serializer.data)

    @extend_schema(responses={200: UserPreferencesSerializer})
    def patch(self, request):
        preferences = ProfileService.get_or_create_preferences(request.user)
        serializer = UserPreferencesSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

