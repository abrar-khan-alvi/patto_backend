from django.urls import path

from apps.accounts.views import (
    LogoutView,
    MeAvatarView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    RegisterView,
    TokenRefreshView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="me"),
    path("me/avatar/", MeAvatarView.as_view(), name="me-avatar"),
]
