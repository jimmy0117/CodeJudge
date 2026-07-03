from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = '帳號管理'

    def ready(self):
        import accounts.models  # noqa: F401 – registers signals
