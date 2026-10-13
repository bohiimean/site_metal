import re

_NUMBER = re.compile(r'(\d+(?:[.,]\d+)?)')


def natural_sort_key(value):
    """Ключ сортировки значений параметров «по числу»: 2.7 < 3 < 10,
    20×20 < 40×20 < 100×20. Десятичная запятая понимается как точка.
    Числа идут раньше текста в той же позиции."""
    key = []
    for part in _NUMBER.split(str(value)):
        if not part:
            continue
        if _NUMBER.fullmatch(part):
            key.append((0, float(part.replace(',', '.')), ''))
        else:
            key.append((1, 0.0, part.lower()))
    return key
