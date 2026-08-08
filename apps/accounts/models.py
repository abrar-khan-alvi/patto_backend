import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import UserManager


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    preferred_language = models.CharField(max_length=12, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email


def user_avatar_upload_path(instance, filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"avatars/{instance.user_id}/{uuid.uuid4()}.{extension}"


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=120, blank=True)
    pronouns = models.CharField(max_length=80, blank=True)
    avatar = models.ImageField(upload_to=user_avatar_upload_path, blank=True)
    preferred_language = models.CharField(max_length=12, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"profile:{self.user.email}"


class EmailOTP(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        EMAIL_VERIFICATION = "email_verification", "Email verification"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["consumed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} {self.purpose}"


class AuthSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_sessions")
    access_token_hash = models.CharField(max_length=128, unique=True)
    refresh_token_hash = models.CharField(max_length=128, unique=True)
    access_expires_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["access_expires_at"]),
            models.Index(fields=["refresh_expires_at"]),
            models.Index(fields=["revoked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.id}"
