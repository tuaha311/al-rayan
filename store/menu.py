"""The storefront's main menu, shared by the desktop bar, its hover dropdowns,
the mobile drawer and the footer.

Each entry links to a filtered shop page. Category entries get a dropdown of
the fabrics actually stocked in them, plus a banner image (the category's own
image, else a product photo from it) for the dropdown and the drawer card.
Built in three queries, so it stays live without any cache to invalidate.
"""

from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils.http import urlencode

from .models import Category, Product, ProductImage

# (label, query params, category slug or None, accent)
MAIN_MENU = [
    ('Shop All', {}, None, False),
    ('Hand Painted', {'category': 'hand-painted'}, 'hand-painted', False),
    ('Embroidered', {'category': 'embroidered'}, 'embroidered', False),
    ('3D Embellished', {'category': '3d-embellished'}, '3d-embellished', False),
    ('Digital Printed', {'category': 'digital-printed'}, 'digital-printed', False),
    ('Formals', {'category': 'formals'}, 'formals', False),
    ('Bridal Couture', {'category': 'bridal-couture'}, 'bridal-couture', False),
    ('Shawls', {'category': 'shawls'}, 'shawls', False),
    ('Sale', {'on_sale': '1'}, None, True),
]


def _url(base, params):
    return f'{base}?{urlencode(params)}' if params else base


def _subtree_ids(root, children_of):
    ids, frontier = {root.pk}, [root.pk]
    while frontier:
        nxt = [c for pk in frontier for c in children_of.get(pk, ()) if c not in ids]
        ids.update(nxt)
        frontier = nxt
    return ids


def main_menu():
    shop = reverse('store:product_list')
    categories = list(Category.objects.filter(is_active=True))
    by_slug = {c.slug: c for c in categories}
    children_of = {}
    for c in categories:
        children_of.setdefault(c.parent_id, []).append(c.pk)

    # (category_id, fabric name, fabric slug) for every stocked combination.
    stocked = set(
        Product.objects.active().filter(fabric__isnull=False)
        .values_list('category_id', 'fabric__name', 'fabric__slug')
    )
    # Primary product photos, best first: featured, then newest.
    photos = list(
        ProductImage.objects.filter(is_primary=True, product__is_active=True)
        .order_by('-product__is_featured', '-product__created_at')
        .values_list('product__category_id', 'image')
    )

    def photo_in(ids=None):
        for cat_id, path in photos:
            if ids is None or cat_id in ids:
                return default_storage.url(path)
        return ''

    menu = []
    for label, params, slug, accent in MAIN_MENU:
        item = {'label': label, 'url': _url(shop, params), 'accent': accent,
                'children': [], 'image': ''}
        if slug:
            category = by_slug.get(slug)
            if not category:
                # Not seeded/active — a link to an empty page is worse than none.
                continue
            ids = _subtree_ids(category, children_of)
            fabrics = sorted({(name, fslug) for cat_id, name, fslug in stocked if cat_id in ids})
            item['children'] = [
                {'label': name, 'url': _url(shop, {**params, 'fabric': fslug})}
                for name, fslug in fabrics
            ]
            item['image'] = category.image.url if category.image else photo_in(ids)
        elif not params:
            # "Shop All" drops down the top-level categories themselves.
            item['children'] = [
                {'label': c.name, 'url': _url(shop, {'category': c.slug})}
                for c in sorted(
                    (c for c in categories if c.parent_id is None),
                    key=lambda c: (c.sort_order, c.name),
                )
            ]
            item['image'] = photo_in()
        else:
            item['image'] = photo_in()
        menu.append(item)
    return menu
