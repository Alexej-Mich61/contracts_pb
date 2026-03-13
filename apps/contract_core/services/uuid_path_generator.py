# apps/contract_core/services/uuid_path_generator.py
"""
Универсальный генератор путей для загрузки файлов с UUID.
Придерживается принципов DRY и SOLID - единая ответственность, открытость для расширения.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from django.utils import timezone


class UUIDPathGenerator:
    """
    Генератор путей для FileField с уникальными именами файлов.

    Usage:
        # В модели:
        file = models.FileField(
            upload_to=UUIDPathGenerator("contracts", keep_original_name=True),
            ...
        )

        # Или с кастомным суффиксом:
        file = models.FileField(
            upload_to=UUIDPathGenerator("invoices", uuid_length=8),
            ...
        )
    """

    def __init__(
            self,
            base_path: str,
            keep_original_name: bool = True,
            uuid_length: int = 6,
            date_format: str = "%Y/%m",
            prefix: Optional[str] = None,
            lowercase_extension: bool = True
    ):
        """
        Args:
            base_path: Базовый путь для загрузки (например, "faq/files" или "contracts")
            keep_original_name: Сохранять ли оригинальное имя файла
            uuid_length: Длина UUID суффикса (рекомендуется 6-8)
            date_format: Формат даты для структуры папок (strftime)
            prefix: Префикс перед именем файла (опционально)
            lowercase_extension: Приводить ли расширение к нижнему регистру
        """
        self.base_path = base_path.strip('/')
        self.keep_original_name = keep_original_name
        self.uuid_length = max(4, min(uuid_length, 32))  # ограничиваем разумными пределами
        self.date_format = date_format
        self.prefix = prefix
        self.lowercase_extension = lowercase_extension

    def _generate_uuid_suffix(self) -> str:
        """Генерирует короткий UUID."""
        return uuid.uuid4().hex[:self.uuid_length]

    def _get_current_date_path(self) -> str:
        """Возвращает путь на основе текущей даты."""
        now = timezone.now()
        return now.strftime(self.date_format)

    def _sanitize_filename(self, filename: str) -> str:
        """
        Очищает имя файла от потенциально опасных символов.
        Сохраняет базовую структуру имени.
        """
        # Убираем путь, оставляем только имя файла
        filename = os.path.basename(filename)

        # Заменяем пробелы на подчеркивания
        filename = filename.replace(' ', '_')

        # Убираем опасные символы, но сохраняем буквы, цифры, точки, дефисы, подчеркивания
        import re
        filename = re.sub(r'[^\w\.\-]', '', filename)

        return filename

    def _build_filename(self, original_name: str, uuid_suffix: str) -> str:
        """
        Строит новое имя файла с UUID.
        """
        path_obj = Path(original_name)
        ext = path_obj.suffix

        if self.lowercase_extension:
            ext = ext.lower()

        if self.keep_original_name:
            # Оригинальное имя без расширения
            stem = path_obj.stem
            new_name = f"{stem}_{uuid_suffix}{ext}"
        else:
            # Только UUID
            new_name = f"{uuid_suffix}{ext}"

        if self.prefix:
            new_name = f"{self.prefix}_{new_name}"

        return new_name

    def __call__(self, instance, filename: str) -> str:
        """
        Django вызывает этот метод при сохранении файла.

        Args:
            instance: Экземпляр модели
            filename: Оригинальное имя загружаемого файла

        Returns:
            Полный путь для сохранения файла
        """
        # Очищаем имя файла
        clean_filename = self._sanitize_filename(filename)

        # Генерируем компоненты пути
        date_path = self._get_current_date_path()
        uuid_suffix = self._generate_uuid_suffix()
        new_filename = self._build_filename(clean_filename, uuid_suffix)

        # Собираем полный путь
        full_path = os.path.join(self.base_path, date_path, new_filename)

        return full_path


# --- Фабричные функции для частых случаев ---

def faq_file_path(instance, filename: str) -> str:
    """
    Путь для файлов FAQ.
    Сохраняет структуру: faq/files/2025/03/имя_файла_a3f7b2.pdf
    """
    generator = UUIDPathGenerator(
        base_path="faq/files",
        keep_original_name=True,
        uuid_length=6
    )
    return generator(instance, filename)


def contract_file_path(instance, filename: str) -> str:
    """
    Путь для файлов договоров.
    Сохраняет структуру: contracts/2025/03/имя_файла_a3f7b2.pdf
    """
    generator = UUIDPathGenerator(
        base_path="contracts",
        keep_original_name=True,
        uuid_length=6
    )
    return generator(instance, filename)


def act_file_path(instance, filename: str) -> str:
    """
    Путь для файлов актов (промежуточных).
    Сохраняет структуру: acts/2025/03/имя_файла_a3f7b2.pdf
    """
    generator = UUIDPathGenerator(
        base_path="acts",
        keep_original_name=True,
        uuid_length=6
    )
    return generator(instance, filename)


def final_act_file_path(instance, filename: str) -> str:
    """
    Путь для файлов итоговых актов.
    Сохраняет структуру: acts_final/2025/03/имя_файла_a3f7b2.pdf
    """
    generator = UUIDPathGenerator(
        base_path="acts_final",
        keep_original_name=True,
        uuid_length=6
    )
    return generator(instance, filename)


def simple_uuid_path(base_path: str, uuid_length: int = 8) -> Callable:
    """
    Фабрика для простых путей с UUID без сохранения оригинального имени.

    Usage:
        file = models.FileField(upload_to=simple_uuid_path("uploads", 8))
    """
    generator = UUIDPathGenerator(
        base_path=base_path,
        keep_original_name=False,
        uuid_length=uuid_length
    )
    return generator