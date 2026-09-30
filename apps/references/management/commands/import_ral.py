"""
Загружает в справочник «Цвета» полный каталог RAL Classic — 213 оттенков
с русскими названиями и HEX.

Данные лежат в apps/references/data/ral_classic.csv (источник —
colorscheme.ru/ral-colors/ral-classic.html), сеть команде не нужна.
HEX у RAL — всегда экранное приближение: сам стандарт задан физическими
образцами краски.

Цвет ищется по RAL-коду («RAL 9010» и «ral9010» — один цвет). Недостающие
создаются; уже заведённые по умолчанию не трогаются — менеджер мог
переименовать цвет или поправить HEX под своё покрытие. Палитры
(ColorPalette) и привязки к обработкам товаров команда не меняет.

Использование:
    python manage.py import_ral            # добавить недостающие
    python manage.py import_ral --update   # + перезаписать название/HEX/группу у существующих
    python manage.py import_ral --dry-run  # только показать, что изменится
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.references.models import Color

DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'ral_classic.csv'

# Первая цифра кода RAL — тон (так каталог и устроен)
GROUP_BY_DIGIT = {
    '1': 'yellow', '2': 'orange', '3': 'red', '4': 'violet', '5': 'blue',
    '6': 'green', '7': 'gray', '8': 'brown',
}
# 9-я серия смешанная: белые, чёрные и алюминиевые
BLACK_9 = {'RAL 9004', 'RAL 9005', 'RAL 9011', 'RAL 9017'}


def normalize_code(code):
    """'ral9010', 'RAL  9010' → 'RAL 9010'."""
    digits = ''.join(ch for ch in code if ch.isdigit())
    return f'RAL {digits}' if digits else ''


def color_group(code, effect):
    # Перламутр и «железный блеск» — к металлику: такие покрытия ищут
    # по эффекту, а не по тону
    if effect in ('pearl', 'iron'):
        return 'metallic'
    digit = code[4]
    if digit == '9':
        return 'black' if code in BLACK_9 else 'white'
    return GROUP_BY_DIGIT[digit]


def load_rows():
    with DATA_FILE.open(encoding='utf-8') as f:
        return [
            {
                'ral_code':    row['code'],
                'name':        row['name'],
                'hex_code':    row['hex'],
                'color_group': color_group(row['code'], row['effect']),
            }
            for row in csv.DictReader(f)
        ]


class Command(BaseCommand):
    help = 'Загружает полный каталог RAL Classic (213 цветов) в справочник цветов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update', action='store_true',
            help='Перезаписать название, HEX и группу у уже заведённых RAL-цветов',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Ничего не записывать, только показать изменения',
        )

    def handle(self, *args, **options):
        rows = load_rows()
        existing = {}
        for c in Color.objects.exclude(ral_code=''):
            existing.setdefault(normalize_code(c.ral_code), c)

        to_create, to_update, differs = [], [], []
        for row in rows:
            color = existing.get(row['ral_code'])
            if color is None:
                to_create.append(Color(**row))
                continue
            changed = [f for f in ('name', 'hex_code', 'color_group', 'ral_code')
                       if getattr(color, f) != row[f]]
            if not changed:
                continue
            if options['update']:
                for f in changed:
                    setattr(color, f, row[f])
                to_update.append(color)
            else:
                differs.append((color, row))

        verbose = options['verbosity'] > 1 or options['dry_run']
        if verbose:
            for c in to_create:
                self.stdout.write(f'+ {c.ral_code} {c.name} {c.hex_code}')
            for c in to_update:
                self.stdout.write(f'~ {c.ral_code} → {c.name} {c.hex_code} [{c.color_group}]')
            for c, row in differs:
                self.stdout.write(
                    f'  {c.ral_code}: «{c.name}» {c.hex_code} [{c.color_group}]'
                    f' — в каталоге «{row["name"]}» {row["hex_code"]} [{row["color_group"]}]'
                )

        if not options['dry_run']:
            with transaction.atomic():
                Color.objects.bulk_create(to_create)
                Color.objects.bulk_update(
                    to_update, ['name', 'hex_code', 'color_group', 'ral_code'],
                )

        prefix = '[dry-run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}RAL Classic: добавлено {len(to_create)}, '
            f'обновлено {len(to_update)}, всего в каталоге {len(rows)}'
        ))
        if differs:
            self.stdout.write(
                f'{len(differs)} уже заведённых цветов отличаются от каталога '
                f'названием, HEX или группой — оставлены как есть '
                f'(посмотреть: --dry-run, перезаписать: --update)'
            )
