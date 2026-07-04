from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', '學生'),
        ('teacher', '教師'),
        ('admin', '管理員'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    class Meta:
        verbose_name = '使用者資料'
        verbose_name_plural = '使用者資料'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    def is_teacher_or_admin(self):
        return self.role in ['teacher', 'admin']


class SiteSettings(models.Model):
    """平台全域設定（Singleton，永遠只有 pk=1 那一筆）。"""
    google_oauth_enabled = models.BooleanField(
        default=False, verbose_name='啟用 Google 帳號登入'
    )
    google_oauth_client_id = models.CharField(
        max_length=300, blank=True, verbose_name='Google Client ID'
    )
    google_oauth_client_secret = models.CharField(
        max_length=300, blank=True, verbose_name='Google Client Secret'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='上次更新')

    class Meta:
        verbose_name = '平台設定'
        verbose_name_plural = '平台設定'

    def __str__(self):
        return '平台設定'

    def save(self, *args, **kwargs):
        self.pk = 1  # 強制 Singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'admin' if instance.is_superuser else 'student'
        UserProfile.objects.create(user=instance, role=role)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
