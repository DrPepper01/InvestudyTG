from django.core.management.base import BaseCommand

from tg_app.telegram_bot import main


class Command(BaseCommand):
    help = 'Запуск Telegram бота поддержки'

    def handle(self, *args, **options):
        main()
