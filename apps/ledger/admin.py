from django.contrib import admin

from .models import Account, Category, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "kind", "currency", "opening_balance"]
    list_filter = ["kind"]
    search_fields = ["name", "user__email"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "kind", "color"]
    list_filter = ["kind"]
    search_fields = ["name", "user__email"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "description", "amount", "category", "categorized_by", "user"]
    list_filter = ["categorized_by", "account__kind"]
    search_fields = ["description", "merchant", "user__email"]
    date_hierarchy = "date"
    list_select_related = ["category", "user"]
