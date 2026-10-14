"""Admin dashboard data + sidebar badge callbacks for Unfold.

The dashboard opens on what needs doing today (orders to confirm or ship,
cash to collect, stock running out), each card a link to that exact list.
"""

from decimal import Decimal

from django.db.models import Case, Count, F, Sum, When
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from . import constants
from .constants import LOW_STOCK_THRESHOLD, OrderStatus, PaymentStatus
from .models import Discount, Order, Product

CURRENCY = constants.CURRENCY_SYMBOL

TO_SHIP = (OrderStatus.CONFIRMED, OrderStatus.PROCESSING)
OUT_FOR_DELIVERY = (OrderStatus.SHIPPED, OrderStatus.DELIVERED)


def _money(value):
    return f'{CURRENCY} {(value or Decimal("0")):,.0f}'


def _orders(query=''):
    return reverse('admin:store_order_changelist') + query


def _products(query=''):
    return reverse('admin:store_product_changelist') + query


def _stock_counts():
    totals = (
        Product.objects.filter(is_active=True, track_inventory=True)
        .annotate(_vcount=Count('variants'), _vstock=Coalesce(Sum('variants__stock'), 0))
        .annotate(_total=Case(When(_vcount__gt=0, then=F('_vstock')), default=F('stock')))
        .values_list('_total', flat=True)
    )
    sold_out = sum(1 for t in totals if t == 0)
    low = sum(1 for t in totals if 0 < t <= LOW_STOCK_THRESHOLD)
    return sold_out, low


def dashboard_callback(request, context):
    orders = Order.objects.all()
    new = orders.filter(status=OrderStatus.PENDING).count()
    to_ship = orders.filter(status__in=TO_SHIP).count()
    to_collect = orders.filter(
        status__in=OUT_FOR_DELIVERY, payment_status=PaymentStatus.UNPAID,
    )
    sold_out, low = _stock_counts()

    context['todo_cards'] = [
        {
            'title': 'New orders to confirm', 'value': new, 'icon': 'notifications',
            'link': _orders(f'?status__exact={OrderStatus.PENDING}'),
            'footer': 'Call or WhatsApp the customer, then confirm',
            'urgent': new > 0,
        },
        {
            'title': 'Ready to send', 'value': to_ship, 'icon': 'package_2',
            'link': _orders('?status__in=confirmed,processing'),
            'footer': 'Confirmed, waiting to be shipped',
            'urgent': to_ship > 0,
        },
        {
            'title': 'Cash to collect', 'value': _money(to_collect.aggregate(s=Sum('total'))['s']),
            'icon': 'account_balance_wallet',
            'link': _orders(f'?status__in=shipped,delivered&payment_status__exact={PaymentStatus.UNPAID}'),
            'footer': f'{to_collect.count()} shipped order(s) not yet paid',
            'urgent': False,
        },
        {
            'title': 'Sold out', 'value': sold_out, 'icon': 'production_quantity_limits',
            'link': _products('?stock=out&is_active__exact=1'),
            'footer': f'{low} more running low' if low else 'Nothing running low',
            'urgent': sold_out > 0,
        },
    ]

    month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = orders.filter(created_at__gte=month_start).exclude(
        status__in=(OrderStatus.CANCELLED, OrderStatus.RETURNED),
    )
    paid = orders.filter(payment_status=PaymentStatus.PAID)
    live_sales = sum(1 for d in Discount.objects.filter(is_active=True) if d.is_live())
    context['kpi_cards'] = [
        {'title': 'Orders this month', 'value': this_month.count(),
         'footer': f'worth {_money(this_month.aggregate(s=Sum("total"))["s"])}'},
        {'title': 'Money received', 'value': _money(paid.aggregate(s=Sum('total'))['s']),
         'footer': f'from {paid.count()} paid order(s), all time'},
        {'title': 'Products on the website', 'value': Product.objects.filter(is_active=True).count(),
         'footer': f'{Product.objects.filter(is_active=False).count()} hidden'},
        {'title': 'Sales running', 'value': live_sales,
         'footer': 'discounts live right now'},
    ]
    context['quick_links'] = [
        {'title': 'Add a product', 'icon': 'add_circle', 'link': reverse('admin:store_product_add')},
        {'title': 'Start a sale', 'icon': 'sell', 'link': reverse('admin:store_discount_add')},
        {'title': 'Take a phone order', 'icon': 'call', 'link': reverse('admin:store_order_add')},
        {'title': 'View the website', 'icon': 'storefront', 'link': '/', 'new_tab': True},
    ]
    recent = list(orders.order_by('-created_at')[:8])
    for o in recent:
        o.status_text = 'New' if o.status == OrderStatus.PENDING else o.get_status_display()
        o.status_kind = {
            OrderStatus.PENDING: 'warning', OrderStatus.DELIVERED: 'success',
            OrderStatus.CANCELLED: 'danger', OrderStatus.RETURNED: 'danger',
        }.get(o.status, 'info')
    context['recent_orders'] = recent
    context['all_orders_link'] = _orders()
    return context


# -- Sidebar badges ---------------------------------------------------------
def pending_orders_badge(request):
    count = Order.objects.filter(status=OrderStatus.PENDING).count()
    return count or None
