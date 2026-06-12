"""Admin dashboard data + sidebar badge callbacks for Unfold."""

from decimal import Decimal

from django.db.models import Count, Sum

from . import constants
from .models import Order, Product

CURRENCY = constants.CURRENCY_SYMBOL


def _money(value):
    return f'{CURRENCY} {(value or Decimal("0")):,.0f}'


def dashboard_callback(request, context):
    """Inject KPI cards + recent orders into the admin index context."""
    orders = Order.objects.all()
    paid = orders.filter(payment_status=constants.PaymentStatus.PAID)

    revenue = paid.aggregate(s=Sum('total'))['s'] or Decimal('0')
    total_orders = orders.count()
    pending = orders.filter(status=constants.OrderStatus.PENDING).count()
    unpaid = orders.filter(payment_status=constants.PaymentStatus.UNPAID).count()
    active_products = Product.objects.filter(is_active=True).count()
    on_sale = sum(1 for p in Product.objects.filter(is_active=True) if p.is_on_sale)

    context['kpi_cards'] = [
        {
            'title': 'Revenue (paid)', 'value': _money(revenue),
            'icon': 'payments', 'footer': f'{paid.count()} paid order(s)',
        },
        {
            'title': 'Orders', 'value': total_orders,
            'icon': 'shopping_bag', 'footer': f'{pending} pending',
        },
        {
            'title': 'Awaiting payment', 'value': unpaid,
            'icon': 'account_balance_wallet', 'footer': 'COD to collect',
        },
        {
            'title': 'Active products', 'value': active_products,
            'icon': 'checkroom', 'footer': f'{on_sale} on sale',
        },
    ]
    context['recent_orders'] = (
        orders.order_by('-created_at')[:8]
    )
    return context


# -- Sidebar badges ---------------------------------------------------------
def pending_orders_badge(request):
    count = Order.objects.filter(status=constants.OrderStatus.PENDING).count()
    return count or None
