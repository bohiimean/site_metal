from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.pages.models import Page

# Драфты статических страниц: slug → (заголовок, файл с HTML-контентом).
# Существующие страницы не перезаписываются — источник истины после
# первой загрузки — админка.
DRAFTS = {
    'politika-konfidentsialnosti': (
        'Политика обработки персональных данных',
        'docs/politika-konfidentsialnosti.html',
    ),
}


def _strip_leading_comment(html):
    """Убирает служебный HTML-комментарий (инструкцию) в начале файла."""
    text = html.lstrip()
    if text.startswith('<!--'):
        end = text.find('-->')
        if end != -1:
            return text[end + 3:].lstrip('\n')
    return html


class Command(BaseCommand):
    help = 'Создаёт статические страницы из драфтов в docs/ (существующие не трогает)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Перезаписать контент существующих страниц драфтом',
        )

    def handle(self, *args, **options):
        for slug, (title, rel_path) in DRAFTS.items():
            exists = Page.objects.filter(slug=slug).exists()
            if exists and not options['force']:
                self.stdout.write(f'– {slug}: уже существует, пропущено (перезапись: --force)')
                continue

            path = Path(settings.BASE_DIR) / rel_path
            if not path.exists():
                self.stderr.write(f'✗ {slug}: файл {rel_path} не найден')
                continue

            content = _strip_leading_comment(path.read_text(encoding='utf-8'))
            Page.objects.update_or_create(
                slug=slug,
                defaults={'title': title, 'content': content, 'seo_title': title},
            )
            verb = 'обновлена' if exists else 'создана'
            self.stdout.write(self.style.SUCCESS(f'✓ {slug}: страница {verb}'))
