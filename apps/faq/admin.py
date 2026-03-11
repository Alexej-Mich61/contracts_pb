from django.contrib import admin
from .models import FAQItem, FAQFile


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ["question", "order", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["question", "answer"]
    ordering = ["order", "-created_at"]


@admin.register(FAQFile)
class FAQFileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "uploaded_at"]
    search_fields = ["title", "file"]
    ordering = ["-id"]