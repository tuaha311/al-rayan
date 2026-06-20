"""Template context shared across every storefront page."""

from .cart import Cart
from .models import Category, StoreSetting


def storefront(request):
    # Top-level active categories that actually have products, for the nav.
    nav_categories = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .order_by('sort_order', 'name')
    )
    cart = Cart(request)
    return {
        'store_settings': StoreSetting.load(),
        'nav_categories': nav_categories,
        'cart_count': len(cart),
        'cart_subtotal': cart.subtotal,
    }
