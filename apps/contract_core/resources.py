# apps/contract_core/resources.py
from import_export import resources, fields

from .models import Ak


class AkResource(resources.ModelResource):
    """
    Ресурс для импорта/экспорта АК.
    Порядок колонок: number, name, address
    """

    class Meta:
        model = Ak
        fields = ('number', 'name', 'address')
        import_id_fields = ()  # Всегда создавать новые записи, не обновлять
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

            # Убрал проверку уникальности, так как может быть несколько АК с одинаковым номером в разных регионах/районах

        if errors:
            raise ValueError("Ошибки в данных таблицы:\n" + "\n".join(errors))

    def before_import_row(self, row, **kwargs):
        """
        Подготовка строки перед импортом (уже валидировано в before_import).
        """
        # Можно добавить дополнительную обработку, если нужно
        pass
