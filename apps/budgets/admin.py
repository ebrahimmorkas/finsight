from django.contrib import admin

from .models import Budget, BudgetAlert


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "amount", "warn_at_percent"]
    search_fields = ["user__email", "category__name"]


@admin.register(BudgetAlert)
class BudgetAlertAdmin(admin.ModelAdmin):
    list_display = ["budget", "month", "level", "sent_at"]
    list_filter = ["level"]
