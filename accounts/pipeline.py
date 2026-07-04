from accounts.models import UserProfile


def ensure_user_profile(backend, user, response, *args, **kwargs):
    """
    社交登入 pipeline：確保每位透過 Google 登入的使用者都有 UserProfile。
    若 signal 已建立則不重複建立（get_or_create）。
    """
    UserProfile.objects.get_or_create(user=user, defaults={'role': 'student'})
