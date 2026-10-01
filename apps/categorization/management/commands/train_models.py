from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.categorization.services import train_user_model


class Command(BaseCommand):
    help = "Retrain every user's personal categorization model."

    def handle(self, *args, **options):
        trained = sum(
            train_user_model(user) is not None for user in get_user_model().objects.iterator()
        )
        self.stdout.write(self.style.SUCCESS(f"Trained {trained} model(s)."))
