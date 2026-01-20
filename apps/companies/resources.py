# apps/companies/resources.py
from import_export import resources, fields
from django.core.exceptions import ValidationError
from .models import Company
from apps.contract_core.validators import inn_validator


class CompanyResource(resources.ModelResource):
    """
    Ресурс для импорта/экспорта компаний.
    Порядок колонок: name, inn, is_customer, is_licensee, is_lab, is_subcontractor
    """

    class Meta:
        model = Company
        fields = ('name', 'inn', 'is_customer', 'is_licensee', 'is_lab', 'is_subcontractor')
        import_id_fields = ()  # Всегда создавать новые записи, не обновлять
        skip_unchanged = True

    def before_import(self, dataset, **kwargs):
        """
        Валидация данных перед импортом.
        """
        errors = []
        headers = dataset.headers or ['name', 'inn', 'is_customer', 'is_licensee', 'is_lab', 'is_subcontractor']  # assume order
        for i, row in enumerate(dataset, start=1):  # rows start from 1 after header
            row_dict = dict(zip(headers, row))
            name = row_dict.get('name')
            inn = row_dict.get('inn')
            is_customer = row_dict.get('is_customer')
            is_licensee = row_dict.get('is_licensee')
            is_lab = row_dict.get('is_lab')
            is_subcontractor = row_dict.get('is_subcontractor')

            # Проверка обязательных полей
            if not name or not inn:
                errors.append(f"Строка {i}: Поля name и inn обязательны.")
                continue

            # Валидация ИНН
            try:
                inn_validator(inn)
            except ValidationError as e:
                errors.append(f"Строка {i}: Неверный ИНН - {e.message}")
                continue

            # Проверка уникальности ИНН в БД
            if Company.objects.filter(inn=inn).exists():
                errors.append(f"Строка {i}: Компания с ИНН {inn} уже существует в базе данных.")
                continue

            # Проверка ролей: хотя бы одна True
            roles = [is_customer, is_licensee, is_lab, is_subcontractor]
            if not any(roles):
                errors.append(f"Строка {i}: Хотя бы одна роль (is_customer, is_licensee, is_lab, is_subcontractor) должна быть True.")
                continue

        if errors:
            raise ValueError("Ошибки в данных таблицы:\n" + "\n".join(errors))

    def before_import_row(self, row, **kwargs):
        """
        Подготовка строки перед импортом (уже валидировано в before_import).
        """
        # Можно добавить дополнительную обработку, если нужно
        pass
