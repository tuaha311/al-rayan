"""Session-based shopping cart for the storefront.

Guest-friendly (no login required) — the cart lives in the Django session as a
plain dict and prices are always recomputed from the live catalogue, so active
discounts apply automatically. On checkout it is converted into a real Order.
"""

from decimal import Decimal

from .constants import LOW_STOCK_THRESHOLD
from .models import Product, ProductVariant

CART_SESSION_KEY = 'cart'
ZERO = Decimal('0.00')


def _line_key(product_id, variant_id, additional_meters, size=''):
    key = f'{product_id}:{variant_id or 0}:{additional_meters}'
    return f'{key}:{size}' if size else key


def _pool(product, variant, size):
    """Identify the stock count a line draws on: its colour, narrowed to its
    size once that colour's stock is split by size. Lines that differ only
    in extra length (or in size, before the split) share one count."""
    split = product.splits_stock_by_size(variant)
    return (product.id, variant.id if variant else None, size if split else '')


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = self.session[CART_SESSION_KEY] = {}
        self.cart = cart

    # -- mutations ----------------------------------------------------------
    def add(self, product, variant=None, additional_meters=ZERO, quantity=1,
            replace=False, size=''):
        quantity = max(int(quantity), 1)
        additional_meters = str(Decimal(additional_meters or 0).quantize(Decimal('0.01')))
        variant_id = variant.id if variant else None
        key = _line_key(product.id, variant_id, additional_meters, size)
        existing = self.cart.get(key)
        if existing and not replace:
            existing['quantity'] += quantity
        else:
            self.cart[key] = {
                'product_id': product.id,
                'variant_id': variant_id,
                'additional_meters': additional_meters,
                'size': size,
                'quantity': quantity,
            }
        self.save()

    def set_quantity(self, key, quantity):
        if key in self.cart:
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                return
            if quantity <= 0:
                self.remove(key)
            else:
                self.cart[key]['quantity'] = quantity
                self.save()

    def remove(self, key):
        if key in self.cart:
            del self.cart[key]
            self.save()

    def clear(self):
        self.session[CART_SESSION_KEY] = self.cart = {}
        self.save()

    def save(self):
        self.session.modified = True

    # -- reads --------------------------------------------------------------
    def __iter__(self):
        products = {
            p.id: p for p in Product.objects.filter(
                id__in=[row['product_id'] for row in self.cart.values()]
            ).select_related('category', 'fabric')
        }
        variant_ids = [row['variant_id'] for row in self.cart.values() if row['variant_id']]
        variants = {
            v.id: v for v in ProductVariant.objects.filter(id__in=variant_ids)
            .select_related('color')
        }
        lines, in_pool = [], {}
        for key, row in self.cart.items():
            product = products.get(row['product_id'])
            if product is None:
                continue  # product was deleted; skip stale line
            variant = variants.get(row['variant_id'])
            # Lines saved before sizes existed have no 'size'.
            size = row.get('size', '')
            pool = _pool(product, variant, size)
            in_pool[pool] = in_pool.get(pool, 0) + row['quantity']
            lines.append((key, row, product, variant, size, pool))

        for key, row, product, variant, size, pool in lines:
            extra = Decimal(row['additional_meters'])
            unit_price = product.price_for(extra, variant)
            quantity = row['quantity']
            left = product.stock_left(variant, size)
            # What this line may hold once its pool-mates take their share.
            max_quantity = None if left is None else max(left - (in_pool[pool] - quantity), 0)
            yield {
                'key': key,
                'product': product,
                'variant': variant,
                'color_name': variant.color.name if variant else '',
                'size': size,
                'additional_meters': extra,
                'quantity': quantity,
                'unit_price': unit_price,
                'line_total': unit_price * quantity,
                'stock_left': left,
                'max_quantity': max_quantity,
                'low_stock': left is not None and left <= LOW_STOCK_THRESHOLD,
                'over_stock': max_quantity is not None and quantity > max_quantity,
            }

    def quantity_in_pool(self, product, variant, size):
        """Units already in the cart drawing on the same stock as this choice."""
        pool = _pool(product, variant, size)
        return sum(
            line['quantity'] for line in self
            if _pool(line['product'], line['variant'], line['size']) == pool
        )

    def __len__(self):
        return sum(row['quantity'] for row in self.cart.values())

    @property
    def subtotal(self):
        return sum((line['line_total'] for line in self), ZERO)

    @property
    def is_empty(self):
        return not self.cart

    @property
    def has_stock_problems(self):
        return any(line['over_stock'] for line in self)
