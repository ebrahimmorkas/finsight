from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Budget
from .services import send_due_alerts


@shared_task
def check_budgets_for_user(user_id: int) -> int:
    return send_due_alerts(get_user_model().objects.get(pk=user_id))


@shared_task
def check_all_budgets() -> int:
    user_ids = Budget.objects.values_list("user_id", flat=True).distinct()
    return sum(check_budgets_for_user(user_id) for user_id in user_ids)
