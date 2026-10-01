from django.apps import AppConfig


class InsightsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.insights"

    def ready(self) -> None:
        from . import receivers  # noqa: F401
