#apps/contract_core/admin.py
from django.contrib import admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from apps.identity.permissions import ContractPermission
from .models import ContractSettings

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


# class AkInline(admin.TabularInline):
#     model = Ak
#     extra = 0
#     fields = ("number", "name", "address")


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
        "executor__is_licensee",
        "created_at",
    )
    search_fields = ("number", "customer__name", "customer__inn")
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
    #inlines = [AkInline]



class AkResource(resources.ModelResource):
    """Импорт АК с привязкой к региону и району."""
    # колонки Excel:  номер | название | адрес | регион | район | protection_object_id (необязательно)
    region = fields.Field(
        column_name="регион",
        attribute="region",
        widget=ForeignKeyWidget(Region, field="name")
    )
    district = fields.Field(
        column_name="район",
        attribute="district",
        widget=ForeignKeyWidget(District, field="name")
    )
    protection_objects = fields.Field(
        column_name="protection_object_id",
        attribute="protection_objects",
        widget=ForeignKeyWidget(ProtectionObject, field="id")
    )

    class Meta:
        model = Ak
        import_id_fields = ("number",)   # номер АК уникален
        skip_unchanged = True
        fields = ("number", "name", "address", "region", "district", "protection_objects")

    def before_import_row(self, row, **kwargs):
        """
        Перед сохранением строки находим конкретный район по паре «регион + район».
        Если в Excel не указан protection_object_id – оставляем пустым.
        """
        region_name = row.get("регион")
        district_name = row.get("район")

        if region_name and district_name:
            try:
                region = Region.objects.get(name=region_name)
                district = District.objects.get(region=region, name=district_name)
                row["region"] = region.id
                row["district"] = district.id
            except (Region.DoesNotExist, District.DoesNotExist):
                raise ValueError(
                    f"Не найдена пара «регион: {region_name}, район: {district_name}» в справочнике."
                )
        else:
            row["region"] = None
            row["district"] = None



@admin.register(Ak)
class AkAdmin(ImportExportModelAdmin):
    resource_classes = [AkResource]   # подключаем импорт/экспорт

    list_display = ("number", "name", "address", "region", "district")
    list_filter = ("region", "district")
    search_fields = ("number", "name", "address")
    filter_horizontal = ("protection_objects",)   # M2M-виджет



@admin.register(ContractSettings)
class ContractSettingsAdmin(admin.ModelAdmin):
    list_display = ("days_before_expires", "longterm_status_time", "oneoff_status_time")
    fields = ("days_before_expires", "longterm_status_time", "oneoff_status_time")

