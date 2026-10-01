from django.apps import AppConfig


class CategorizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.categorization"

    def ready(self) -> None:
        from . import receivers  # noqa: F401
