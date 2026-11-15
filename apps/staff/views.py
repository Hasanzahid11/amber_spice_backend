from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CanManageStaff, IsRestaurantStaff
from .models import StaffAttendance, StaffMember, StaffShift
from .serializers import (
    StaffAttendanceSerializer,
    StaffMemberSerializer,
    StaffShiftSerializer,
)


class StaffPermissionHelper(permissions.BasePermission):
    """
    Allows staff viewing for all restaurant staff members,
    while restricting roster/staff profile modifications to Managers and Owner/Admins.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return (
                getattr(request.user, 'is_restaurant_staff', False)
                or getattr(request.user, 'is_owner_or_admin', False)
                or request.user.is_staff
                or request.user.has_restaurant_permission('staff:view')
                or request.user.has_restaurant_permission('staff:manage')
            )
        return request.user.has_restaurant_permission('staff:manage') or getattr(request.user, 'is_owner_or_admin', False) or request.user.is_staff


class StaffMemberViewSet(viewsets.ModelViewSet):
    """
    Staff Profile & Team Management API:
    - View, filter, and manage staff members, roles, shifts, and assigned sections.
    - Real-time duty status and clock-in / clock-out attendance tracking.
    """
    queryset = StaffMember.objects.select_related('user').all()
    serializer_class = StaffMemberSerializer
    permission_classes = [StaffPermissionHelper]
    filterset_fields = ['role', 'shift', 'status', 'assigned_section', 'is_active']
    search_fields = ['name', 'phone', 'email', 'assigned_section']

    @action(detail=False, methods=['get'], url_path='on-duty')
    def on_duty(self, request):
        """
        GET /api/v1/staff/on-duty/
        Lists all staff members currently active on duty.
        """
        active_staff = self.get_queryset().filter(status=StaffMember.Status.ACTIVE, is_active=True)
        serializer = self.get_serializer(active_staff, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='clock-in')
    def clock_in(self, request, pk=None):
        """
        POST /api/v1/staff/<id>/clock-in/
        Clocks in the employee and updates status to ACTIVE.
        """
        staff_member = self.get_object()
        notes = request.data.get('notes', '')
        att = staff_member.clock_in(notes=notes)

        return Response({
            'message': f"{staff_member.name} clocked in successfully.",
            'attendance': StaffAttendanceSerializer(att).data,
            'staff': StaffMemberSerializer(staff_member).data,
        })

    @action(detail=True, methods=['post'], url_path='clock-out')
    def clock_out(self, request, pk=None):
        """
        POST /api/v1/staff/<id>/clock-out/
        Clocks out the employee, computes hours worked, and updates status to OFF_DUTY.
        """
        staff_member = self.get_object()
        notes = request.data.get('notes', '')
        att = staff_member.clock_out(notes=notes)

        return Response({
            'message': f"{staff_member.name} clocked out successfully.",
            'attendance': StaffAttendanceSerializer(att).data if att else None,
            'staff': StaffMemberSerializer(staff_member).data,
        })

    @action(detail=True, methods=['post'], url_path='toggle-break')
    def toggle_break(self, request, pk=None):
        """
        POST /api/v1/staff/<id>/toggle-break/
        Switches between on break and active duty.
        """
        staff_member = self.get_object()
        new_status = staff_member.toggle_break()

        return Response({
            'message': f"{staff_member.name} status is now {new_status}.",
            'status': new_status,
            'staff': StaffMemberSerializer(staff_member).data,
        })

    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """
        GET /api/v1/staff/<id>/attendance/
        Historical attendance records for this staff member.
        """
        staff_member = self.get_object()
        records = staff_member.attendance_records.all()
        serializer = StaffAttendanceSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def schedules(self, request, pk=None):
        """
        GET /api/v1/staff/<id>/schedules/
        Assigned shift schedules for this staff member.
        """
        staff_member = self.get_object()
        shifts = staff_member.shifts.all()
        serializer = StaffShiftSerializer(shifts, many=True)
        return Response(serializer.data)


class StaffShiftViewSet(viewsets.ModelViewSet):
    """
    Roster & Shift Schedules API:
    - View and schedule shifts for kitchen staff, servers, drivers, and front desk.
    """
    queryset = StaffShift.objects.select_related('staff_member').all()
    serializer_class = StaffShiftSerializer
    permission_classes = [StaffPermissionHelper]
    filterset_fields = ['staff_member', 'shift_date', 'status', 'station']
    search_fields = ['title', 'station', 'staff_member__name']


class StaffAttendanceViewSet(viewsets.ModelViewSet):
    """
    Staff Attendance & Working Hours API:
    - Clock in/out logs, break durations, and total shift hours worked.
    """
    queryset = StaffAttendance.objects.select_related('staff_member').all()
    serializer_class = StaffAttendanceSerializer
    permission_classes = [StaffPermissionHelper]
    filterset_fields = ['staff_member', 'status']
    search_fields = ['staff_member__name', 'notes']
