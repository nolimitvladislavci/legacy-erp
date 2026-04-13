from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create UserProfile for every new User."""
    if created:
        from accounts.models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
