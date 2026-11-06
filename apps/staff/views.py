from rest_framework import viewsets
from apps.accounts.permissions import CanManageStaff
from .models import StaffMember
from .serializers import StaffMemberSerializer


class StaffMemberViewSet(viewsets.ModelViewSet):
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [CanManageStaff]
    filterset_fields = ['role', 'shift', 'status', 'assigned_section']
    search_fields = ['name', 'phone', 'assigned_section']
