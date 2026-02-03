# apps/identity/management/commands/create_system_user.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Создаёт или проверяет системного пользователя для уведомлений и чат-бота'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='system',
            help='Имя пользователя (по умолчанию: system)'
        )
        parser.add_argument(
            '--email',
            default='system@company.local',
            help='Email системного пользователя'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пересоздать пользователя, если существует'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        force = options['force']

        existing = User.objects.filter(username=username).first()

        if existing and not force:
            self.stdout.write(self.style.WARNING(
                f'Системный пользователь "{username}" уже существует (ID: {existing.pk}).'
            ))
            return

        if existing and force:
            self.stdout.write(self.style.WARNING(
                f'Удаляем существующего пользователя "{username}" и создаём заново.'
            ))
            existing.delete()

        user = User.objects.create(
            username=username,
            email=email,
            first_name='Система',
            last_name='Уведомления',
            is_system=True,
            is_active=True,
            date_joined=timezone.now(),
        )
        user.set_unusable_password()  # запрет логина паролем
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Системный пользователь создан: {user.username} (ID: {user.pk})'
        ))