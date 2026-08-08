from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import EmailOTP
from apps.accounts.serializers import (
    AvatarUploadSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RegisterSerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
)
from apps.accounts.services import (
    create_or_update_user,
    revoke_session,
    rotate_refresh_token,
    send_otp,
    verify_otp_and_issue_tokens,
)


def token_response(tokens):
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "Bearer",
        "access_expires_at": tokens.access_expires_at,
        "refresh_expires_at": tokens.refresh_expires_at,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = create_or_update_user(
            email=serializer.validated_data["email"],
            preferred_language=serializer.validated_data["preferred_language"],
            timezone_name=serializer.validated_data["timezone"],
        )
        send_otp(email=user.email, purpose=EmailOTP.Purpose.EMAIL_VERIFICATION)
        return Response({"detail": "Verification code sent."}, status=status.HTTP_202_ACCEPTED)


class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_otp(
            email=serializer.validated_data["email"],
            purpose=serializer.validated_data["purpose"],
        )
        return Response({"detail": "Verification code sent."}, status=status.HTTP_202_ACCEPTED)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, tokens = verify_otp_and_issue_tokens(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
            purpose=serializer.validated_data["purpose"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "email_verified_at": user.email_verified_at,
                    "preferred_language": user.preferred_language,
                    "timezone": user.timezone,
                },
                "tokens": token_response(tokens),
            }
        )


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = rotate_refresh_token(refresh_token=serializer.validated_data["refresh_token"])
        return Response({"tokens": token_response(tokens)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        revoke_session(
            session=request.auth,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user.profile, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MeAvatarView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AvatarUploadSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(request.user.profile, context={"request": request}).data)

    def delete(self, request):
        profile = request.user.profile
        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = ""
            profile.save(update_fields=["avatar", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
