# apps/contract_core/resources.py
from import_export import resources, fields
from import_export.widgets import BooleanWidget
from .models import Company, Ak
from .validators import inn_validator
from django.core.exceptions import ValidationError


class CustomBooleanWidget(BooleanWidget):
    """Кастомный виджет для корректной обработки 1/0 из Excel."""

    def clean(self, value, row=None, *args, **kwargs):
        if value is None or value == '':
            return False

        # Преобразуем в строку для проверки
        val_str = str(value).strip().lower()

        # True значения: 1, true, yes, да, t, y
        if val_str in ('1', 'true', 'yes', 'да', 't', 'y', 'on'):
            return True

        # False значения: 0, false, no, нет, f, n, пусто
        return False

    def render(self, value, obj=None):
        return 1 if value else 0


class CompanyResource(resources.ModelResource):
    """Ресурс для импорта/экспорта компаний."""

    # Явно определяем поля с кастомным виджетом
    is_customer = fields.Field(
        column_name='is_customer',
        attribute='is_customer',
        widget=CustomBooleanWidget()
    )
    is_licensee = fields.Field(
        column_name='is_licensee',
        attribute='is_licensee',
        widget=CustomBooleanWidget()
    )
    is_laboratory = fields.Field(
        column_name='is_laboratory',
        attribute='is_laboratory',
        widget=CustomBooleanWidget()
    )
    is_subcontractor = fields.Field(
        column_name='is_subcontractor',
        attribute='is_subcontractor',
        widget=CustomBooleanWidget()
    )

    class Meta:
        model = Company
        fields = ('name', 'inn', 'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor')
        export_order = fields
        import_id_fields = ()  # всегда создавать новые записи
        skip_unchanged = True

    def before_import(self, dataset, **kwargs):
        """Валидация данных перед импортом."""
        errors = []
        headers = dataset.headers or ['name', 'inn', 'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor']

        for i, row in enumerate(dataset, start=1):
            row_dict = dict(zip(headers, row))

            name = row_dict.get('name')
            inn = row_dict.get('inn')
            is_customer = row_dict.get('is_customer')
            is_licensee = row_dict.get('is_licensee')
            is_laboratory = row_dict.get('is_laboratory')
            is_subcontractor = row_dict.get('is_subcontractor')

            # Обязательные поля
            if not name or not inn:
                errors.append(f"Строка {i}: Поля name и inn обязательны.")
                continue

            # Валидация ИНН
            try:
                inn_validator(inn)
            except ValidationError as e:
                errors.append(f"Строка {i}: {e.message}")
                continue

            # Уникальность ИНН в базе
            if Company.objects.filter(inn=inn).exists():
                errors.append(f"Строка {i}: ИНН {inn} уже существует в базе.")
                continue

            # Хотя бы одна роль True (проверяем через CustomBooleanWidget логику)
            def is_true(val):
                if val is None or val == '':
                    return False
                return str(val).strip().lower() in ('1', 'true', 'yes', 'да', 't', 'y', 'on')

            roles = [is_customer, is_licensee, is_laboratory, is_subcontractor]
            if not any(is_true(r) for r in roles):
                errors.append(
                    f"Строка {i}: Хотя бы одна роль должна быть True (1, yes, true, да). Получено: customer={is_customer}, licensee={is_licensee}, lab={is_laboratory}, sub={is_subcontractor}")
                continue

        if errors:
            raise ValueError("Ошибки импорта:\n" + "\n".join(errors))


class AkResource(resources.ModelResource):
    """Ресурс для импорта/экспорта АК."""
    class Meta:
        model = Ak
        fields = ('number', 'name', 'address', 'district')
        export_order = fields
        import_id_fields = ()
        skip_unchanged = True

    def before_import(self, dataset, **kwargs):
        """Валидация перед импортом."""
        errors = []
        for i, row in enumerate(dataset, start=1):
            number = row[0] if len(row) > 0 else None
            name = row[1] if len(row) > 1 else None
            address = row[2] if len(row) > 2 else None
            district_id = row[3] if len(row) > 3 else None

            if not number or not name or not address:
                errors.append(f"Строка {i}: Поля number, name, address обязательны.")
                continue

            # Уникальность: номер + район
            if district_id and Ak.objects.filter(number=number, district_id=district_id).exists():
                errors.append(f"Строка {i}: АК с номером {number} уже существует в этом районе.")
                continue

        if errors:
            raise ValueError("Ошибки импорта:\n" + "\n".join(errors))