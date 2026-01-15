#apps/contract_core/admin.py
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from apps.companies.permissions import ContractPermission
from .models import (
    Region,
    District,
    Contract,
    InterimAct,
    ProtectionObject,
    Ak,
)


class DistrictInline(admin.TabularInline):
    model = District
    extra = 1


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    inlines = [DistrictInline]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("region", "name")
    list_filter = ("region",)
    search_fields = ("name",)


class InterimActInline(admin.TabularInline):
    model = InterimAct
    extra = 0
    fields = ("title", "date", "file")


class ProtectionObjectInline(admin.TabularInline):
    model = ProtectionObject
    extra = 0
    fields = ("name", "region", "district", "address", "subcontractor")


class AkInline(admin.TabularInline):
    model = Ak
    extra = 0
    fields = ("number", "name", "address")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "type",
        "status",
        "customer",
        "executor",
        "total_sum",
        "date_start",
        "date_end",
        "is_trash",
        "is_archived",
        "creator",
    )
    list_filter = (
        "type",
        "status",
        "is_trash",
        "is_archived",
        "executor__kind",
        "created_at",
    )
    search_fields = ("number", "customer", "inn")
    date_hierarchy = "date_start"
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "final_act_present")
    fieldsets = (
        (
            "Служебное",
            {"fields": ("type", "is_trash", "is_archived", "status", "creator")},
        ),
        (
            "Основные сведения",
            {
                "fields": (
                    "number",
                    "date_concluded",
                    "customer",
                    "inn",
                    ("date_start", "date_end"),
                    "executor",
                    "note",
                )
            },
        ),
        ("Файлы", {"fields": ("file",)}),
        ("Финансы", {"fields": ("total_sum", "monthly_sum", "advance")}),
        ("Акт итоговый", {"fields": ("final_act_date", "final_act_present")}),
    )
    inlines = [InterimActInline, ProtectionObjectInline]



    def get_queryset(self, request):
        return super().get_queryset(request).select_related("executor", "creator")


    def get_readonly_fields(self, request, obj=None):
        """Динамически блокируем поля в зависимости от роли."""
        if obj is None:
            return super().get_readonly_fields(request, obj)

        perm = ContractPermission(request.user, obj.executor)
        ro = list(self.readonly_fields)

        if not perm.can_edit_systems:
            ro.extend(["gos_services", "oko", "spolokh"])

        if not perm.can_edit_sign_stage:
            ro.extend([
                "contract_to_be_signed",
                "contract_signed",
                "contract_signed_in_trading_platform",
                "contract_signed_in_EDO",
                "contract_original_received",
                "contract_termination",
            ])
        return ro

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True
        perm = ContractPermission(request.user, obj.executor)
        return perm.can_delete()


@admin.register(InterimAct)
class InterimActAdmin(admin.ModelAdmin):
    list_display = ("contract", "title", "date")
    list_filter = ("date",)
    search_fields = ("contract__number", "title")
    date_hierarchy = "date"


@admin.register(ProtectionObject)
class ProtectionObjectAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "district", "subcontractor")
    list_filter = ("region", "subcontractor")
    search_fields = ("name", "address")
    inlines = [AkInline]


@admin.register(Ak)
class AkAdmin(admin.ModelAdmin):
    list_display = (
        "protection_object",
        "number",
        "name",
        "address",
    )
    list_filter = (
        "protection_object__contract__type",  # ← было contract__type
    )
    search_fields = (
        "protection_object__contract__number",
        "name",
        "address",
    )