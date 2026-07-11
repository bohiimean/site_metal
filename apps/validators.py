"""Общие валидаторы загружаемых изображений.

Живут вне конкретного приложения, чтобы их могли использовать и catalog,
и references без перекрёстных импортов между models.py.
"""
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.template.defaultfilters import filesizeformat

# Настройки ограничений загрузки
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 МБ
MIN_IMAGE_SIDE = 1000               # px по большей стороне — чтобы не мылило при зуме

validate_image_extension = FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)

UPLOAD_HELP_TEXT = (
    'JPG, PNG или WebP, до 10 МБ, минимум 1000px по большей стороне. '
    'Фон лучше однотонный (белый/светлый) — на сайте фото вписывается целиком, '
    'без обрезки.'
)


def validate_image_filesize(f):
    """Ограничение размера файла."""
    if f and getattr(f, 'size', None) and f.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f'Файл слишком большой ({filesizeformat(f.size)}). '
            f'Максимум — {filesizeformat(MAX_IMAGE_SIZE)}.'
        )


def validate_image_dimensions(f):
    """Минимальное разрешение изображения (по большей стороне)."""
    try:
        width, height = get_image_dimensions(f)
    except Exception:
        return  # не изображение — отсекут ImageField и extension-валидатор
    if not width or not height:
        return
    if max(width, height) < MIN_IMAGE_SIDE:
        raise ValidationError(
            f'Слишком маленькое изображение ({width}×{height}px). '
            f'Нужно минимум {MIN_IMAGE_SIDE}px по большей стороне, '
            'иначе оно будет размытым при увеличении.'
        )


# Готовый набор для validators=[...] на ImageField
IMAGE_UPLOAD_VALIDATORS = [
    validate_image_extension,
    validate_image_filesize,
    validate_image_dimensions,
]
