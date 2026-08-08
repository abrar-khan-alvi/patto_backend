from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance: User, created: bool, **kwargs):
    if created:
        UserProfile.objects.create(
            user=instance,
            preferred_language=instance.preferred_language,
            timezone=instance.timezone,
        )
