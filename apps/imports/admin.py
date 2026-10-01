from django.contrib import admin

from .models import ImportBatch


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["filename", "user", "account", "imported", "duplicates", "created_at"]
    search_fields = ["filename", "user__email"]
