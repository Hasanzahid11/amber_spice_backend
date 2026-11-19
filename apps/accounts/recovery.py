import hashlib
import hmac
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import PasswordRecovery, User


class RecoveryRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RecoveryVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r'^\d{6}$')


class RecoveryConfirmSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    reset_token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(write_only=True)


class RecoveryRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RecoveryRequestSerializer, responses=inline_serializer('RecoveryRequestResponse', fields={'challenge_id': serializers.UUIDField(), 'detail': serializers.CharField()}), description='Public password recovery. Requires a configured email backend. Returns a challenge ID without revealing whether the account exists. Code is never returned by the API.')
    def post(self, request):
        serializer = RecoveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        backend = settings.EMAIL_BACKEND
        if not settings.EMAIL_HOST and backend == 'django.core.mail.backends.smtp.EmailBackend':
            return Response({'detail': 'Password recovery email is not configured. Contact the restaurant or try again after setup.'}, status=503)
        email = serializer.validated_data['email'].lower()
        now = timezone.now()
        if PasswordRecovery.objects.filter(email=email, created_at__gte=now - timedelta(seconds=60)).exists():
            return Response({'detail': 'Wait 60 seconds before requesting another recovery code.'}, status=429)
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        code = str(secrets.randbelow(900000) + 100000)
        challenge = PasswordRecovery.objects.create(user=user, email=email, code_hash=make_password(code), expires_at=now + timedelta(minutes=15))
        if user:
            try:
                send_mail('Your Amber Spice recovery code', f'Your recovery code is {code}. It expires in 15 minutes. If you did not request this, ignore this email.', settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception:
                challenge.delete()
                return Response({'detail': 'The recovery email could not be sent. Please retry later.'}, status=503)
        return Response({'challenge_id': challenge.id, 'detail': 'If the account exists, a recovery code has been sent through the configured email service.'}, status=202)


class RecoveryVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RecoveryVerifySerializer, responses=inline_serializer('RecoveryVerifyResponse', fields={'reset_token': serializers.CharField()}), description='Verify a six-digit emailed code. Maximum five attempts; 15-minute expiry. Returns a single-use reset token.')
    def post(self, request):
        serializer = RecoveryVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            challenge = PasswordRecovery.objects.select_for_update().filter(pk=data['challenge_id']).first()
            if not challenge or challenge.consumed or challenge.expires_at <= timezone.now() or challenge.attempts >= 5:
                return Response({'detail': 'The recovery code is invalid or expired. Request a new code.'}, status=400)
            challenge.attempts += 1
            if not challenge.user_id or not check_password(data['code'], challenge.code_hash):
                challenge.save(update_fields=['attempts'])
                return Response({'detail': 'The recovery code is invalid or expired.'}, status=400)
            token = secrets.token_urlsafe(32)
            challenge.token_hash = hashlib.sha256(token.encode()).hexdigest()
            challenge.verified = True
            challenge.save(update_fields=['attempts', 'verified', 'token_hash'])
        return Response({'reset_token': token})


class RecoveryConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RecoveryConfirmSerializer, responses=inline_serializer('RecoveryConfirmResponse', fields={'detail': serializers.CharField()}), description='Consume the verified challenge and reset token to change the password. Tokens cannot be reused.')
    def post(self, request):
        serializer = RecoveryConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            challenge = PasswordRecovery.objects.select_for_update().filter(pk=data['challenge_id']).first()
            token_hash = hashlib.sha256(data['reset_token'].encode()).hexdigest()
            if not challenge or not challenge.user_id or not challenge.verified or challenge.consumed or challenge.expires_at <= timezone.now() or not hmac.compare_digest(token_hash, challenge.token_hash):
                return Response({'detail': 'Reset session is invalid or expired. Start password recovery again.'}, status=400)
            try:
                validate_password(data['new_password'], challenge.user)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'new_password': list(error.messages)})
            challenge.user.set_password(data['new_password'])
            challenge.user.save(update_fields=['password'])
            PasswordRecovery.objects.filter(user_id=challenge.user_id, consumed=False).update(consumed=True)
        return Response({'detail': 'Password reset. Sign in using the new password.'})
