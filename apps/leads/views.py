import html
import json
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.catalog.models import Product
from .captcha import client_ip, verify_captcha
from .models import Lead

logger = logging.getLogger(__name__)

# Ограничения на входящую корзину — защита от DoS через раздутый JSON
MAX_CART_ITEMS = 100
MAX_QTY_PER_ITEM = 999
MAX_STR_LEN = 500

# Выбранные параметры позиции — читаемые строки (SKU в системе нет)
PARAM_FIELDS = ['material', 'steel_grade', 'finish', 'color',
                'size', 'length', 'height']


def _build_cart_snapshot(client_items):
    """Строит cart_snapshot из клиентских данных; название товара берёт из БД
    по slug. Параметры (материал/марка/обработка/цвет/размер/длина/высота) —
    читаемые строки выбора клиента: слепок не ломается при правках каталога.
    Цены нет — её называет менеджер. Если slug не найден — позиция всё равно
    сохраняется с пометкой, чтобы менеджер видел, что клиент пытался заказать.
    """
    if not isinstance(client_items, list):
        return []

    # Собираем валидные позиции из входа, отсекая мусор.
    # Ключ позиции — товар + все параметры: разные исполнения = разные строки.
    normalized = []
    seen_keys = set()
    for raw in client_items[:MAX_CART_ITEMS]:
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get('slug', ''))[:300].strip()
        if not slug:
            continue

        params = {
            f: str(raw.get(f) or '')[:200].strip() or None
            for f in PARAM_FIELDS
        }
        # note — свободный комментарий (например, «свой цвет: RAL 6005»)
        note = str(raw.get('note') or '')[:MAX_STR_LEN].strip() or None

        key = (slug, note, *params.values())
        if key in seen_keys:
            continue
        seen_keys.add(key)

        try:
            qty = int(raw.get('qty', 1))
        except (ValueError, TypeError):
            qty = 1
        qty = max(1, min(qty, MAX_QTY_PER_ITEM))

        normalized.append({'slug': slug, 'qty': qty, 'note': note, **params})

    if not normalized:
        return []

    # Один запрос за всеми товарами
    products = {
        p.slug: p for p in Product.objects
        .filter(slug__in=[it['slug'] for it in normalized])
    }

    snapshot = []
    for it in normalized:
        p = products.get(it['slug'])
        row = {'slug': it['slug'], 'qty': it['qty']}
        if p:
            row['name'] = p.name
            row['product_id'] = p.pk
            row['is_active'] = p.is_active
            row['in_stock'] = p.in_stock
        else:
            # Товар не найден в БД — удалён или клиент прислал мусор.
            # Сохраняем факт запроса для менеджера.
            row['name'] = '⚠ Товар не найден в каталоге'
            row['is_active'] = False
        for f in PARAM_FIELDS + ['note']:
            if it[f]:
                row[f] = it[f]
        snapshot.append(row)

    return snapshot


def _send_telegram(lead_id):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        lead = Lead.objects.get(pk=lead_id)
        e = html.escape  # экранируем всё, что пришло от клиента
        name_e = e(lead.name)
        phone_e = e(lead.phone)

        if lead.source == 'cart' and lead.cart_snapshot:
            def item_lines(it):
                spec = ' / '.join(
                    str(it[f]) for f in ('material', 'steel_grade', 'finish')
                    if it.get(f)
                )
                dims = ' · '.join(
                    f'{label} {it[f]}' for f, label in
                    (('size', 'размер'), ('length', 'длина'), ('height', 'высота'))
                    if it.get(f)
                )
                return (
                    f"• {e(str(it.get('name', '?')))} × {int(it.get('qty', 1))}"
                    + (f"\n   ⚙ {e(spec)}" if spec else '')
                    + (f"\n   🎨 {e(str(it.get('color')))}" if it.get('color') else '')
                    + (f"\n   📐 {e(dims)}" if dims else '')
                    + (f"\n   💬 {e(str(it.get('note')))}" if it.get('note') else '')
                )
            lines = '\n'.join(item_lines(it) for it in lead.cart_snapshot)
            text = f"🛒 <b>Новая заявка #{lead.pk}</b>\n{name_e}, {phone_e}\n\n{lines}"
        else:
            text = f"📞 <b>Заявка на звонок #{lead.pk}</b>\n{name_e}, {phone_e}"

        if lead.comment:
            text += f"\n\n💬 {e(lead.comment)}"

        site_url = getattr(settings, 'SITE_URL', '')
        if site_url:
            text += f'\n\n🔗 <a href="{e(site_url)}{e(lead.get_admin_url())}">Открыть в админке</a>'

        requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'},
            timeout=3,
        )
    except Exception:
        logger.exception('Telegram notification failed for lead %s', lead_id)


@ratelimit(key='ip', rate='10/m', method='POST', block=False)
@require_POST
def submit_cart(request):
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'ok': False, 'error': 'Слишком много запросов. Попробуйте позже.'},
            status=429,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Неверный формат запроса'}, status=400)

    phone = str(data.get('phone') or '')[:MAX_STR_LEN].strip()
    if len(phone) < 5:
        return JsonResponse({'ok': False, 'error': 'Укажите номер телефона'})

    if not data.get('agree'):
        return JsonResponse(
            {'ok': False, 'error': 'Необходимо согласие на обработку персональных данных'}
        )

    if not verify_captcha(str(data.get('captcha_token') or ''), client_ip(request)):
        return JsonResponse(
            {'ok': False, 'error': 'Не пройдена проверка «Я не робот». Попробуйте ещё раз.'}
        )

    cart_snapshot = _build_cart_snapshot(data.get('cart_snapshot'))

    contact_method = str(data.get('contact_method') or 'phone')
    if contact_method not in dict(Lead.CONTACT_CHOICES):
        contact_method = 'phone'
    contact_value = str(data.get('contact_value') or '')[:200].strip()

    with transaction.atomic():
        lead = Lead.objects.create(
            name=(str(data.get('name') or ''))[:MAX_STR_LEN].strip(),
            phone=phone[:30],
            contact_method=contact_method,
            contact_value=contact_value,
            comment=(str(data.get('comment') or ''))[:MAX_STR_LEN].strip(),
            cart_snapshot=cart_snapshot,
            source='cart',
            consent_pdn=bool(data.get('agree')),
        )
        lead_id = lead.pk
        transaction.on_commit(lambda: _send_telegram(lead_id))

    return JsonResponse({'ok': True, 'id': lead.pk})


@ratelimit(key='ip', rate='10/m', method='POST', block=False)
@require_POST
def submit_callback(request):
    if getattr(request, 'limited', False):
        return render(request, 'leads/_callback_form.html', {
            'error': 'Слишком много запросов. Попробуйте позже.',
            'name': request.POST.get('name', ''),
            'phone': request.POST.get('phone', ''),
            'comment': request.POST.get('comment', ''),
        })

    phone = request.POST.get('phone', '')[:MAX_STR_LEN].strip()
    name = request.POST.get('name', '')[:MAX_STR_LEN].strip()
    comment = request.POST.get('comment', '')[:MAX_STR_LEN].strip()

    if len(phone) < 5:
        return render(request, 'leads/_callback_form.html', {
            'error': 'Укажите номер телефона',
            'name': name,
            'phone': phone,
            'comment': comment,
        })

    if not request.POST.get('agree'):
        return render(request, 'leads/_callback_form.html', {
            'error': 'Необходимо согласие на обработку персональных данных',
            'name': name,
            'phone': phone,
            'comment': comment,
        })

    # Виджет SmartCaptcha кладёт токен в скрытое поле smart-token
    if not verify_captcha(request.POST.get('smart-token', ''), client_ip(request)):
        return render(request, 'leads/_callback_form.html', {
            'error': 'Не пройдена проверка «Я не робот». Попробуйте ещё раз.',
            'name': name,
            'phone': phone,
            'comment': comment,
        })

    with transaction.atomic():
        lead = Lead.objects.create(
            name=name,
            phone=phone,
            comment=comment,
            cart_snapshot=[],
            source='callback_request',
            consent_pdn=bool(request.POST.get('agree')),
        )
        lead_id = lead.pk
        transaction.on_commit(lambda: _send_telegram(lead_id))

    return render(request, 'leads/_callback_success.html', {'lead': lead})
