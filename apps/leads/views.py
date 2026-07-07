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

from apps.catalog.models import ProductVariant
from .models import Lead

logger = logging.getLogger(__name__)

# Ограничения на входящую корзину — защита от DoS через раздутый JSON
MAX_CART_ITEMS = 100
MAX_QTY_PER_ITEM = 999
MAX_STR_LEN = 500


def _build_cart_snapshot(client_items):
    """Строит cart_snapshot из клиентских данных, но название/цену/единицу берёт из БД по SKU.

    Клиент управляет только: какой SKU добавить и сколько штук.
    Всё остальное — из БД, чтобы клиент не мог подсунуть цену 1₽ или XSS в названии.
    Если SKU не найден — позиция всё равно сохраняется с пометкой, чтобы менеджер
    видел, что клиент пытался заказать.
    """
    if not isinstance(client_items, list):
        return []

    # Собираем валидные SKU из входа, отсекая мусор
    normalized = []
    seen_skus = set()
    for raw in client_items[:MAX_CART_ITEMS]:
        if not isinstance(raw, dict):
            continue
        sku = str(raw.get('sku', ''))[:MAX_STR_LEN].strip()
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)

        try:
            qty = int(raw.get('qty', 1))
        except (ValueError, TypeError):
            qty = 1
        qty = max(1, min(qty, MAX_QTY_PER_ITEM))

        # note — свободный комментарий (например, «свой цвет: RAL 6005»)
        note = str(raw.get('note') or '')[:MAX_STR_LEN].strip() or None

        # Цена/название/unit, которые видел клиент — сохраняем для сверки,
        # но реальные значения возьмём из БД
        client_price = str(raw.get('price', ''))[:32]

        normalized.append({'sku': sku, 'qty': qty, 'note': note, 'client_price': client_price})

    if not normalized:
        return []

    # Один запрос за всеми вариантами
    skus = [it['sku'] for it in normalized]
    variants = {
        v.sku: v for v in ProductVariant.objects
        .filter(sku__in=skus)
        .select_related('product')
    }

    snapshot = []
    for it in normalized:
        v = variants.get(it['sku'])
        row = {'sku': it['sku'], 'qty': it['qty']}
        if v:
            row['name'] = v.product.name
            row['price'] = str(v.price)
            row['unit'] = v.get_unit_display()
            row['unit_code'] = v.unit
            row['product_id'] = v.product_id
            row['variant_id'] = v.id
            row['is_active'] = v.is_active and v.product.is_active
            row['in_stock'] = v.in_stock
            # Фиксируем расхождение цены — менеджер увидит если клиент видел старую
            if it['client_price'] and it['client_price'] != str(v.price):
                row['client_saw_price'] = it['client_price']
        else:
            # SKU не найден в БД — товар удалён или клиент прислал мусор.
            # Сохраняем факт запроса для менеджера.
            row['name'] = '⚠ SKU не найден в каталоге'
            row['price'] = None
            row['unit'] = ''
            row['is_active'] = False
            if it['client_price']:
                row['client_saw_price'] = it['client_price']
        if it['note']:
            row['note'] = it['note']
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
            lines = '\n'.join(
                f"• {e(str(it.get('name', '?')))} × {int(it.get('qty', 1))}"
                f" — {e(str(it.get('price', '?')))} ₽/{e(str(it.get('unit', '')))}"
                + (f"\n   💬 {e(str(it.get('note')))}" if it.get('note') else '')
                for it in lead.cart_snapshot
            )
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

    cart_snapshot = _build_cart_snapshot(data.get('cart_snapshot'))

    with transaction.atomic():
        lead = Lead.objects.create(
            name=(str(data.get('name') or ''))[:MAX_STR_LEN].strip(),
            phone=phone[:30],
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
