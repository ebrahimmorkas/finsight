from django.contrib import admin

from .models import CategorizationRule, UserModel


@admin.register(CategorizationRule)
class CategorizationRuleAdmin(admin.ModelAdmin):
    list_display = ["user", "field", "pattern", "category", "priority"]
    search_fields = ["pattern", "user__email"]


@admin.register(UserModel)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ["user", "samples", "classes", "accuracy", "trained_at"]
    exclude = ["blob"]
    readonly_fields = ["samples", "classes", "accuracy", "trained_at"]
