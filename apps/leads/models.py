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


class Lead(models.Model):
    SOURCE_CHOICES = [
        ('cart',             'Из корзины'),
        ('callback_request', 'Заявка на звонок'),
    ]
    STATUS_CHOICES = [
        ('new',         'Новая'),
        ('in_progress', 'В работе'),
        ('closed',      'Закрыта'),
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
    status = models.CharField(
        'Статус', max_length=20,
        choices=STATUS_CHOICES, default='new',
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.name} ({self.get_status_display()})'

    def get_admin_url(self):
        from django.urls import reverse
        return reverse('admin:leads_lead_change', args=[self.pk])
