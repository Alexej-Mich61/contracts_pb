# apps/contract_core/resources.py
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.core.exceptions import ValidationError
from .models import Ak, Region, District, validate_region_code_exists, validate_district_code_exists


class RegionCodeWidget(ForeignKeyWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(Region, *args, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        try:
            return Region.objects.get(region_code=value)
        except Region.DoesNotExist:
            raise ValueError(f"Регион с кодом '{value}' не найден.")

    def render(self, value, obj=None):
        if value:
            return value.region_code
        return ""


class DistrictCodeWidget(ForeignKeyWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(District, *args, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        # Need region_code from row
        region_code = row.get('region')
        if not region_code:
            raise ValueError("Код региона обязателен для поиска района.")
        try:
            region = Region.objects.get(region_code=region_code)
            return District.objects.get(district_code=value, region=region)
        except Region.DoesNotExist:
            raise ValueError(f"Регион с кодом '{region_code}' не найден.")
        except District.DoesNotExist:
            raise ValueError(f"Район с кодом '{value}' не найден для региона '{region_code}'.")

    def render(self, value, obj=None):
        if value:
            return value.district_code
        return ""


class AkResource(resources.ModelResource):
    """
    Ресурс для импорта/экспорта АК.
    Порядок колонок: number, name, address
    """

    class Meta:
        model = Ak
        fields = ('number', 'name', 'address')
        import_id_fields = ('number',)
        skip_unchanged = True

    def before_import(self, dataset, **kwargs):
        """
        Валидация данных перед импортом.
        """
        errors = []
        headers = dataset.headers or ['number', 'name', 'address']  # assume order
        for i, row in enumerate(dataset, start=1):  # rows start from 1 after header
            row_dict = dict(zip(headers, row))
            number = row_dict.get('number')
            name = row_dict.get('name')
            address = row_dict.get('address')

            # Проверка обязательных полей
            if not number or not name or not address:
                errors.append(f"Строка {i}: Все поля обязательны (number, name, address).")
                continue

            # Проверка уникальности в БД
            if Ak.objects.filter(number=number).exists():
                errors.append(f"Строка {i}: АК с номером {number} уже существует в базе данных.")
                continue

        if errors:
            raise ValueError("Ошибки в данных таблицы:\n" + "\n".join(errors))

    def before_import_row(self, row, **kwargs):
        """
        Подготовка строки перед импортом (уже валидировано в before_import).
        """
        # Можно добавить дополнительную обработку, если нужно
        pass
