import json
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .models import Lead

logger = logging.getLogger(__name__)


def _send_telegram(lead_id):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        lead = Lead.objects.get(pk=lead_id)
        if lead.source == 'cart' and lead.cart_snapshot:
            lines = '\n'.join(
                f"• {it.get('name', '?')} × {it.get('qty', 1)} — {it.get('price', '?')} ₽/{it.get('unit', '')}"
                for it in lead.cart_snapshot
            )
            text = f"🛒 <b>Новая заявка #{lead.pk}</b>\n{lead.name}, {lead.phone}\n\n{lines}"
        else:
            text = f"📞 <b>Заявка на звонок #{lead.pk}</b>\n{lead.name}, {lead.phone}"

        if lead.comment:
            text += f"\n\n💬 {lead.comment}"

        site_url = getattr(settings, 'SITE_URL', '')
        if site_url:
            text += f'\n\n🔗 <a href="{site_url}{lead.get_admin_url()}">Открыть в админке</a>'

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

    phone = (data.get('phone') or '').strip()
    if len(phone) < 5:
        return JsonResponse({'ok': False, 'error': 'Укажите номер телефона'})

    if not data.get('agree'):
        return JsonResponse(
            {'ok': False, 'error': 'Необходимо согласие на обработку персональных данных'}
        )

    cart_snapshot = data.get('cart_snapshot', [])
    if not isinstance(cart_snapshot, list):
        cart_snapshot = []

    with transaction.atomic():
        lead = Lead.objects.create(
            name=(data.get('name') or '').strip(),
            phone=phone,
            comment=(data.get('comment') or '').strip(),
            cart_snapshot=cart_snapshot,
            source='cart',
            consent_pdn=True,
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
        })

    phone = request.POST.get('phone', '').strip()
    name = request.POST.get('name', '').strip()
    comment = request.POST.get('comment', '').strip()

    if len(phone) < 5:
        return render(request, 'leads/_callback_form.html', {
            'error': 'Укажите номер телефона',
            'name': name,
            'phone': phone,
        })

    if not request.POST.get('agree'):
        return render(request, 'leads/_callback_form.html', {
            'error': 'Необходимо согласие на обработку персональных данных',
            'name': name,
            'phone': phone,
        })

    with transaction.atomic():
        lead = Lead.objects.create(
            name=name,
            phone=phone,
            comment=comment,
            cart_snapshot=[],
            source='callback_request',
            consent_pdn=True,
        )
        lead_id = lead.pk
        transaction.on_commit(lambda: _send_telegram(lead_id))

    return render(request, 'leads/_callback_success.html', {'lead': lead})
