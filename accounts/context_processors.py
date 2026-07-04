from django.conf import settings as django_settings


def site_settings(request):
    """
    將平台設定注入每個模板 context。
    - site_settings: SiteSettings 物件
    - google_login_available: bool，Google 按鈕是否應顯示
    """
    try:
        from accounts.models import SiteSettings
        obj = SiteSettings.get_solo()
        has_db_key = bool(obj.google_oauth_client_id)
        has_env_key = bool(getattr(django_settings, 'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', ''))
        google_available = obj.google_oauth_enabled and (has_db_key or has_env_key)
    except Exception:
        obj = None
        google_available = False

    return {
        'site_settings': obj,
        'google_login_available': google_available,
    }
