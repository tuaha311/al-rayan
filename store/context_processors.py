"""Template context shared across every storefront page."""

from .cart import Cart
from .constants import ANDROID_APP_UA_MARKER, ANDROID_APP_VERSION
from .models import Category, StoreSetting


def storefront(request):
    # Top-level active categories that actually have products, for the nav.
    nav_categories = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .order_by('sort_order', 'name')
    )
    cart = Cart(request)
    # The WebView app brands its User-Agent, so pages can drop anything that
    # only makes sense in a browser — starting with the "get the app" prompt.
    in_app = ANDROID_APP_UA_MARKER in request.META.get('HTTP_USER_AGENT', '')
    return {
        'store_settings': StoreSetting.load(),
        'nav_categories': nav_categories,
        'cart_count': len(cart),
        'cart_subtotal': cart.subtotal,
        'in_mobile_app': in_app,
        'android_app_version': ANDROID_APP_VERSION,
    }
