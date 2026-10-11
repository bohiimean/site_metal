from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# Поля параметров в слепках заявок до справочника параметров — старые заявки
# и корзины из localStorage покупателей хранят их так
LEGACY_PARAM_FIELDS = [('size', 'Размер'), ('length', 'Длина'), ('height', 'Высота')]


def cart_item_params(item):
    """Выбранные параметры позиции слепка: [(название, значение)].

    Новый формат — item['params'] = [{name, value}], старый — поля
    size / length / height. Битые записи пропускаются.
    """
    result = []
    params = item.get('params')
    if isinstance(params, list):
        for p in params:
            if not isinstance(p, dict):
                continue
            name, value = p.get('name'), p.get('value')
            if isinstance(name, str) and isinstance(value, str) and name and value:
                result.append((name, value))
    for field, label in LEGACY_PARAM_FIELDS:
        if item.get(field):
            result.append((label, str(item[field])))
    return result


class LeadStatus(models.Model):
    """Статус заявки — справочник, который ведут менеджеры.

    Один статус отмечен «для новых заявок»: его получает каждая заявка
    с сайта. Статус, на котором есть заявки, удалить нельзя — только
    выключить; выключенный не предлагается при смене статуса.
    """
    name = models.CharField('Название', max_length=50)
    color = models.CharField(
        'Цвет', max_length=7, default='#6b7280',
        help_text='HEX-цвет метки статуса, например #3b82f6',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_default = models.BooleanField(
        'Для новых заявок', default=False,
        help_text='Этот статус получает каждая новая заявка с сайта. '
                  'Может быть только один — отметка снимется с прежнего.',
    )
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Статус заявки'
        verbose_name_plural = 'Статусы заявок'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.is_default and not self.is_active:
            raise ValidationError({
                'is_active': 'Статус для новых заявок нельзя выключить — '
                             'сначала отметьте «для новых» другой статус.',
            })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            LeadStatus.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    @classmethod
    def get_default(cls):
        """Статус для новой заявки: отмеченный «для новых», иначе первый активный."""
        active = cls.objects.filter(is_active=True)
        return active.filter(is_default=True).first() or active.first()


class Lead(models.Model):
    SOURCE_CHOICES = [
        ('cart',             'Из корзины'),
        ('callback_request', 'Заявка на звонок'),
    ]
    CONTACT_CHOICES = [
        ('phone',    'Звонок'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('max',      'MAX'),
        ('email',    'Почта'),
    ]

    name = models.CharField('Имя', max_length=200)
    phone = models.CharField('Телефон', max_length=30)
    contact_method = models.CharField(
        'Способ связи', max_length=20,
        choices=CONTACT_CHOICES, default='phone',
    )
    contact_value = models.CharField(
        'Контакт для связи', max_length=200, blank=True,
        help_text='Ник/ссылка Telegram, номер WhatsApp или почта — если выбран не звонок',
    )
    comment = models.TextField('Комментарий', blank=True)
    cart_snapshot = models.JSONField(
        'Состав корзины', default=list, blank=True,
        help_text='Слепок корзины на момент отправки: [{name, slug, qty, '
                  'material, steel_grade, finish, color, params: [{name, value}], note}]. '
                  'В заявках до справочника параметров вместо params — size, length, height.',
    )
    source = models.CharField(
        'Источник', max_length=20,
        choices=SOURCE_CHOICES, default='cart',
    )
    # null — только на случай пустого справочника; новая заявка получает
    # статус «для новых» в save()
    status = models.ForeignKey(
        LeadStatus, on_delete=models.PROTECT,
        null=True, related_name='leads',
        verbose_name='Статус',
    )
    consent_pdn = models.BooleanField(
        'Согласие на обработку ПДн', default=False,
    )
    # Две отдельные галочки: согласие на обработку ПДн (152-ФЗ) и принятие
    # условий продажи — разные юридические действия. К каждой — редакция
    # текста, действовавшая при отправке. PROTECT: принятую редакцию нельзя
    # удалить, пока на неё ссылается заявка.
    pdn_revision = models.ForeignKey(
        'pages.PageRevision', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+',
        verbose_name='Редакция политики ПДн',
    )
    consent_terms = models.BooleanField(
        'Принял условия продажи', default=False,
    )
    terms_revision = models.ForeignKey(
        'pages.PageRevision', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+',
        verbose_name='Редакция условий продажи',
    )
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.name} ({self.status or "без статуса"})'

    def save(self, *args, **kwargs):
        if self.status_id is None:
            self.status = LeadStatus.get_default()
        super().save(*args, **kwargs)

    def get_admin_url(self):
        from django.urls import reverse
        return reverse('admin:leads_lead_change', args=[self.pk])


class LeadNote(models.Model):
    """Запись в истории заявки: заметка менеджера или смена статуса.

    Записи не редактируются — это история. Автор хранится и ссылкой, и
    именем: удалили пользователя — имя в истории остаётся.
    """
    KIND_CHOICES = [
        ('note',   'Заметка'),
        ('status', 'Смена статуса'),
    ]
    MAX_LENGTH = 2000

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE,
        related_name='notes', verbose_name='Заявка',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Автор',
    )
    author_name = models.CharField('Имя автора', max_length=150, blank=True)
    kind = models.CharField('Тип', max_length=10, choices=KIND_CHOICES, default='note')
    text = models.TextField('Текст')
    created_at = models.DateTimeField('Когда', auto_now_add=True)

    class Meta:
        verbose_name = 'Заметка по заявке'
        verbose_name_plural = 'Заметки по заявке'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'#{self.lead_id} {self.author_name}: {self.text[:50]}'

    @staticmethod
    def name_of(user):
        return (user.get_full_name() or user.get_username()) if user else ''

    @classmethod
    def log_status_change(cls, lead, old, new, user):
        """Пишет смену статуса в историю; без изменения — ничего."""
        if old == new:
            return None
        return cls.objects.create(
            lead=lead, author=user, author_name=cls.name_of(user), kind='status',
            text=f'Статус: {old or "—"} → {new or "—"}',
        )
