from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .constants import ANDROID_APK_PATH, ANDROID_APP_VERSION
from .forms import CheckoutForm
from .models import (
    Category,
    Color,
    Fabric,
    Order,
    Product,
    ProductVariant,
    Season,
    ShippingRate,
)

ZERO = Decimal('0.00')
PAGE_SIZE = 12


def _active_products():
    return (
        Product.objects.filter(is_active=True)
        .select_related('category', 'fabric', 'season')
        .prefetch_related('variants__color', 'images')
    )


def _on_sale_ids(products):
    """Ids of products currently carrying a live discount."""
    return [p.id for p in products if p.is_on_sale]


# ---------------------------------------------------------------------------
# Storefront pages
# ---------------------------------------------------------------------------
def home(request):
    products = _active_products()
    featured = list(products.filter(is_featured=True)[:8])
    if len(featured) < 4:
        featured = list(products[:8])
    new_arrivals = list(products.order_by('-created_at')[:8])
    on_sale = [p for p in products if p.is_on_sale][:8]

    shop_categories = (
        Category.objects.filter(is_active=True, products__is_active=True)
        .distinct().order_by('sort_order', 'name')
    )
    return render(request, 'store/home.html', {
        'featured': featured,
        'new_arrivals': new_arrivals,
        'on_sale': on_sale,
        'shop_categories': shop_categories,
    })


def product_list(request):
    products = _active_products()
    active = {}

    cat_slug = request.GET.get('category')
    category = None
    if cat_slug:
        category = Category.objects.filter(slug=cat_slug, is_active=True).first()
        if category:
            products = products.filter(category_id__in=category.descendant_and_self_ids())
            active['category'] = category.slug

    fabric_slug = request.GET.get('fabric')
    if fabric_slug:
        products = products.filter(fabric__slug=fabric_slug)
        active['fabric'] = fabric_slug

    season_slug = request.GET.get('season')
    if season_slug:
        products = products.filter(season__slug=season_slug)
        active['season'] = season_slug

    color_slug = request.GET.get('color')
    if color_slug:
        products = products.filter(variants__color__slug=color_slug,
                                   variants__is_active=True).distinct()
        active['color'] = color_slug

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(short_description__icontains=query)
            | Q(description__icontains=query) | Q(sku__icontains=query)
        )
        active['q'] = query

    if request.GET.get('on_sale'):
        products = products.filter(id__in=_on_sale_ids(products))
        active['on_sale'] = '1'

    sort = request.GET.get('sort', 'newest')
    sort_map = {
        'newest': '-created_at',
        'price-low': 'base_price',
        'price-high': '-base_price',
        'name': 'name',
    }
    products = products.order_by(sort_map.get(sort, '-created_at'))

    paginator = Paginator(products, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    # Preserve filters across pagination links.
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    return render(request, 'store/product_list.html', {
        'page_obj': page,
        'products': page.object_list,
        'total_count': paginator.count,
        'category': category,
        'fabrics': Fabric.objects.filter(is_active=True),
        'seasons': Season.objects.filter(is_active=True),
        'colors': Color.objects.order_by('name'),
        'categories': Category.objects.filter(is_active=True).order_by('sort_order', 'name'),
        'active': active,
        'sort': sort,
        'querystring': querystring,
    })


def product_detail(request, slug):
    product = get_object_or_404(_active_products(), slug=slug)
    variants = list(product.variants.filter(is_active=True).select_related('color'))
    images = list(product.images.all())

    # Meter options: 0 .. max in 0.5 steps.
    meter_options = []
    if product.sold_by_meters and product.max_additional_meters > 0:
        step = Decimal('0.5')
        m = ZERO
        while m <= product.max_additional_meters:
            meter_options.append(m)
            m += step

    # Data for the live price-preview script.
    price_data = {
        'final': str(product.final_price),
        'extraPerMeter': str(product.additional_meter_price),
        'soldByMeters': product.sold_by_meters,
        'variantDeltas': {str(v.id): str(v.price_delta) for v in variants},
    }

    related = list(
        _active_products().filter(category=product.category).exclude(id=product.id)[:4]
    )

    return render(request, 'store/product_detail.html', {
        'product': product,
        'variants': variants,
        'images': images,
        'meter_options': meter_options,
        'price_data': price_data,
        'related': related,
    })


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
def cart_view(request):
    return render(request, 'store/cart.html', {'cart': Cart(request)})


@require_POST
def cart_add(request):
    product = get_object_or_404(Product, id=request.POST.get('product_id'), is_active=True)

    variant = None
    variant_id = request.POST.get('variant_id')
    if variant_id:
        variant = ProductVariant.objects.filter(
            id=variant_id, product=product, is_active=True).first()

    try:
        additional = Decimal(request.POST.get('additional_meters', '0') or '0')
    except (InvalidOperation, TypeError):
        additional = ZERO
    if not product.sold_by_meters or additional < 0:
        additional = ZERO
    if additional > product.max_additional_meters:
        additional = product.max_additional_meters

    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (ValueError, TypeError):
        quantity = 1

    cart = Cart(request)
    cart.add(product, variant, additional, quantity)
    messages.success(request, f'Added “{product.name}” to your cart.')

    if request.POST.get('buy_now'):
        return redirect('store:checkout')
    return redirect('store:cart')


@require_POST
def cart_update(request):
    cart = Cart(request)
    cart.set_quantity(request.POST.get('key', ''), request.POST.get('quantity', '1'))
    return redirect('store:cart')


@require_POST
def cart_remove(request):
    cart = Cart(request)
    cart.remove(request.POST.get('key', ''))
    messages.info(request, 'Item removed from your cart.')
    return redirect('store:cart')


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
def checkout(request):
    cart = Cart(request)
    if cart.is_empty:
        messages.info(request, 'Your cart is empty.')
        return redirect('store:cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.save()
            for line in cart:
                item = order.items.model(order=order)
                item.populate_from(
                    line['product'], line['variant'],
                    line['additional_meters'], line['quantity'],
                )
                item.save()
            order.recalculate_totals()
            cart.clear()
            request.session['recent_order'] = order.order_number
            return redirect('store:order_complete', order_number=order.order_number)
    else:
        form = CheckoutForm()

    # Province → shipping rate map for the live total preview.
    rate_map = {
        r.province: str(r.rate) for r in ShippingRate.objects.filter(is_active=True)
    }
    return render(request, 'store/checkout.html', {
        'cart': cart,
        'form': form,
        'shipping_rates': rate_map,
    })


def order_complete(request, order_number):
    # Only show the confirmation to the session that just placed it.
    if request.session.get('recent_order') != order_number:
        raise Http404
    order = get_object_or_404(Order, order_number=order_number)
    return render(request, 'store/order_complete.html', {'order': order})


# ---------------------------------------------------------------------------
# Android app
# ---------------------------------------------------------------------------
def download_app(request):
    """Serve the Android APK built from mobile/.

    Served through a view rather than as a plain static file so the URL stays
    stable across releases, the browser is told to download (not sniff) it, and
    the file lands with a versioned, recognisable name.
    """
    apk = settings.BASE_DIR / 'static' / ANDROID_APK_PATH
    if not apk.is_file():
        raise Http404('The Al Rayan app is not available for download yet.')
    return FileResponse(
        apk.open('rb'),
        as_attachment=True,
        filename=f'al-rayan-{ANDROID_APP_VERSION}.apk',
        # Android needs this exact type to hand the file to the package
        # installer; anything else and Chrome saves an unopenable blob.
        content_type='application/vnd.android.package-archive',
    )
