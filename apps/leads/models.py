from django.db import models


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

    name = models.CharField('Имя', max_length=200)
    phone = models.CharField('Телефон', max_length=30)
    comment = models.TextField('Комментарий', blank=True)
    cart_snapshot = models.JSONField(
        'Состав корзины', default=list, blank=True,
        help_text='Слепок корзины на момент отправки: [{name, sku, qty, unit, color, note}]',
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
