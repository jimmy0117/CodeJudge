from social_django.strategy import DjangoStrategy


class DBDjangoStrategy(DjangoStrategy):
    """
    覆寫 social-auth 的設定讀取，讓 Google OAuth 憑證優先從資料庫讀取。
    若資料庫沒有設定則 fallback 到環境變數（settings.py）。
    """

    def setting(self, name, default=None, backend=None):
        if backend and getattr(backend, 'name', '') == 'google-oauth2':
            try:
                from accounts.models import SiteSettings
                site = SiteSettings.get_solo()
                if name == 'GOOGLE_OAUTH2_KEY' and site.google_oauth_client_id:
                    return site.google_oauth_client_id
                if name == 'GOOGLE_OAUTH2_SECRET' and site.google_oauth_client_secret:
                    return site.google_oauth_client_secret
            except Exception:
                pass  # DB 尚未就緒時安全 fallback
        return super().setting(name, default, backend)
