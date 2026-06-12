"""Seed the store with a realistic Pakistani men's-cloth catalogue.

Usage:
    python manage.py seed_store              # idempotent: create/update data
    python manage.py seed_store --flush       # wipe store data first, then seed
    python manage.py seed_store --with-superuser   # also create an admin login

All money is in PKR. Re-running without --flush is safe; records are matched
by their natural keys (slug / sku / name) and updated in place.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from store import constants
from store.models import (
    Cart,
    Category,
    Color,
    Discount,
    Fabric,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Season,
    ShippingRate,
    StoreSetting,
)

D = Decimal


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
FABRICS = [
    ('Khadi', 'Hand-woven textured cotton, breathable and rugged.'),
    ('Cotton', 'Soft all-rounder, ideal for everyday summer wear.'),
    ('Wash & Wear', 'Low-maintenance poly-cotton blend that needs no ironing.'),
    ('Karandi', 'Slightly heavy winter-weight weave with a fine texture.'),
    ('Boski', 'Premium silky finish, a wedding-season favourite.'),
    ('Latha', 'Classic fine cotton, smooth and lightweight.'),
    ('Linen', 'Crisp, airy and naturally textured.'),
]

SEASONS = [
    ('Summer', 1),
    ('Winter', 2),
    ('All Season', 3),
]

COLORS = [
    ('White', '#FFFFFF'),
    ('Off White', '#F4F1EA'),
    ('Cream', '#F3E9D2'),
    ('Sand', '#D8C3A5'),
    ('Beige', '#D9C8A9'),
    ('Grey', '#9AA0A6'),
    ('Charcoal', '#36454F'),
    ('Black', '#1A1A1A'),
    ('Navy Blue', '#1F2A44'),
    ('Steel Blue', '#4A6A8A'),
    ('Sky Blue', '#8EB8E5'),
    ('Bottle Green', '#0B3D2E'),
    ('Olive', '#6B7A3A'),
    ('Mustard', '#C9A227'),
    ('Maroon', '#5A1A22'),
    ('Wine', '#6E1B2E'),
    ('Brown', '#5B4636'),
    ('Rust', '#9C5B34'),
]

# (name, parent_slug or None, sort_order)
CATEGORIES = [
    ('Men', None, 1),
    ('Unstitched Suits', 'men', 1),
    ('Premium Suits', 'men', 2),
    ('Waistcoats', 'men', 3),
    # Future departments — created so the structure is ready to grow into.
    ('Women', None, 2),
    ('Accessories', None, 3),
    ('Bags', 'accessories', 1),
    ('Footwear', 'accessories', 2),
]

# Each product: sku, name, category slug, fabric, season, base_price,
# base_meters, per-extra-meter, max extra meters, featured, colour list.
PRODUCTS = [
    # --- Unstitched Suits -------------------------------------------------
    dict(sku='AR-KHD-001', name='Khadi Classic Unstitched Suit', category='unstitched-suits',
         fabric='Khadi', season='Winter', price=3200, meters=D('3.50'), extra=950, maxx=D('2.0'),
         featured=True, colors=['Off White', 'Charcoal', 'Bottle Green', 'Rust']),
    dict(sku='AR-KHD-002', name='Khadi Textured Unstitched Suit', category='unstitched-suits',
         fabric='Khadi', season='Winter', price=3500, meters=D('3.50'), extra=1000, maxx=D('2.0'),
         featured=False, colors=['Navy Blue', 'Maroon', 'Grey']),
    dict(sku='AR-WNW-001', name='Wash & Wear Premium Unstitched Suit', category='unstitched-suits',
         fabric='Wash & Wear', season='All Season', price=4200, meters=D('3.50'), extra=1200, maxx=D('2.5'),
         featured=True, colors=['White', 'Steel Blue', 'Sand', 'Black']),
    dict(sku='AR-WNW-002', name='Wash & Wear Everyday Unstitched Suit', category='unstitched-suits',
         fabric='Wash & Wear', season='All Season', price=3300, meters=D('3.50'), extra=950, maxx=D('2.0'),
         featured=False, colors=['Sky Blue', 'Beige', 'Charcoal']),
    dict(sku='AR-COT-001', name='Cotton Summer Unstitched Suit', category='unstitched-suits',
         fabric='Cotton', season='Summer', price=2600, meters=D('3.50'), extra=800, maxx=D('2.0'),
         featured=False, colors=['White', 'Cream', 'Sky Blue', 'Mustard']),
    dict(sku='AR-COT-002', name='Cotton Comfort Unstitched Suit', category='unstitched-suits',
         fabric='Cotton', season='Summer', price=2400, meters=D('3.50'), extra=750, maxx=D('2.0'),
         featured=False, colors=['Off White', 'Sand', 'Olive']),
    dict(sku='AR-LAT-001', name='Latha Fine Unstitched Suit', category='unstitched-suits',
         fabric='Latha', season='Summer', price=2200, meters=D('4.00'), extra=600, maxx=D('2.0'),
         featured=False, colors=['White', 'Off White', 'Grey']),
    dict(sku='AR-LIN-001', name='Linen Breeze Unstitched Suit', category='unstitched-suits',
         fabric='Linen', season='Summer', price=3800, meters=D('3.50'), extra=1100, maxx=D('2.5'),
         featured=True, colors=['Beige', 'Steel Blue', 'Olive', 'Charcoal']),
    dict(sku='AR-KAR-001', name='Karandi Winter Unstitched Suit', category='unstitched-suits',
         fabric='Karandi', season='Winter', price=4500, meters=D('3.50'), extra=1300, maxx=D('2.0'),
         featured=True, colors=['Charcoal', 'Bottle Green', 'Maroon', 'Navy Blue']),
    dict(sku='AR-KAR-002', name='Karandi Heavyweight Unstitched Suit', category='unstitched-suits',
         fabric='Karandi', season='Winter', price=5200, meters=D('3.50'), extra=1500, maxx=D('2.0'),
         featured=False, colors=['Brown', 'Wine', 'Steel Blue']),
    # --- Premium Suits ----------------------------------------------------
    dict(sku='AR-BSK-001', name='Boski Signature Unstitched Suit', category='premium-suits',
         fabric='Boski', season='All Season', price=8500, meters=D('3.50'), extra=2400, maxx=D('2.5'),
         featured=True, colors=['Off White', 'Sand', 'Steel Blue', 'Black']),
    dict(sku='AR-BSK-002', name='Boski Royal Unstitched Suit', category='premium-suits',
         fabric='Boski', season='All Season', price=9500, meters=D('3.50'), extra=2700, maxx=D('2.5'),
         featured=False, colors=['Charcoal', 'Navy Blue', 'Maroon']),
    dict(sku='AR-KHD-PRM-001', name='Khadi Heritage Premium Suit', category='premium-suits',
         fabric='Khadi', season='Winter', price=6200, meters=D('3.50'), extra=1800, maxx=D('2.0'),
         featured=False, colors=['Bottle Green', 'Rust', 'Charcoal']),
    # --- Waistcoats (sold per piece, not by meters) -----------------------
    dict(sku='AR-WST-001', name='Premium Waistcoat', category='waistcoats',
         fabric='Boski', season='All Season', price=3500, by_meters=False,
         featured=False, colors=['Black', 'Navy Blue', 'Maroon']),
    dict(sku='AR-WST-002', name='Classic Cotton Waistcoat', category='waistcoats',
         fabric='Cotton', season='All Season', price=2200, by_meters=False,
         featured=False, colors=['Charcoal', 'Beige', 'Bottle Green']),
]


class Command(BaseCommand):
    help = 'Seed the store with categories, fabrics, products, pricing and demo orders.'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete existing store data before seeding.')
        parser.add_argument('--with-superuser', action='store_true',
                            help='Create an admin/admin12345 superuser if none exists.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            self._flush()

        self.fabrics = self._seed_fabrics()
        self.seasons = self._seed_seasons()
        self.colors = self._seed_colors()
        self.categories = self._seed_categories()
        self._seed_products()
        self._seed_discounts()
        self._seed_shipping()
        self._seed_settings()
        self._seed_orders()

        if options['with_superuser']:
            self._seed_superuser()

        self.stdout.write(self.style.SUCCESS('\n✔ Store seeded successfully.'))
        self._summary()

    # -- steps --------------------------------------------------------------
    def _flush(self):
        self.stdout.write('Flushing existing store data…')
        for model in (OrderItem, Order, Cart, Discount, ProductVariant,
                      Product, Category, Color, Fabric, Season,
                      ShippingRate, StoreSetting):
            model.objects.all().delete()

    def _seed_fabrics(self):
        out = {}
        for order, (name, desc) in enumerate(FABRICS, 1):
            obj, _ = Fabric.objects.update_or_create(
                name=name, defaults={'description': desc, 'sort_order': order},
            )
            out[name] = obj
        self.stdout.write(f'  Fabrics: {len(out)}')
        return out

    def _seed_seasons(self):
        out = {}
        for name, order in SEASONS:
            obj, _ = Season.objects.update_or_create(
                name=name, defaults={'sort_order': order},
            )
            out[name] = obj
        self.stdout.write(f'  Seasons: {len(out)}')
        return out

    def _seed_colors(self):
        out = {}
        for name, hex_code in COLORS:
            obj, _ = Color.objects.update_or_create(
                name=name, defaults={'hex_code': hex_code},
            )
            out[name] = obj
        self.stdout.write(f'  Colors: {len(out)}')
        return out

    def _seed_categories(self):
        out = {}
        for name, parent_slug, order in CATEGORIES:
            parent = out.get(parent_slug)
            obj, _ = Category.objects.update_or_create(
                slug=_slug(name),
                defaults={'name': name, 'parent': parent, 'sort_order': order},
            )
            out[obj.slug] = obj
        self.stdout.write(f'  Categories: {len(out)}')
        return out

    def _seed_products(self):
        count = variants = 0
        for data in PRODUCTS:
            by_meters = data.get('by_meters', True)
            product, _ = Product.objects.update_or_create(
                sku=data['sku'],
                defaults={
                    'name': data['name'],
                    'category': self.categories[data['category']],
                    'fabric': self.fabrics.get(data['fabric']),
                    'season': self.seasons.get(data['season']),
                    'short_description': f"{data['fabric']} unstitched fabric — premium "
                                         f"quality for the {data['season'].lower()} season."
                                         if by_meters else
                                         f"{data['fabric']} stitched piece.",
                    'description': (
                        f"{data['name']} crafted from fine {data['fabric'].lower()} fabric. "
                        "Tailor-ready unstitched cloth; extend the length to suit your "
                        "preference." if by_meters else
                        f"{data['name']} in {data['fabric'].lower()}."
                    ),
                    'base_price': D(data['price']),
                    'sold_by_meters': by_meters,
                    'base_meters': data.get('meters', D('0.00')) if by_meters else D('0.00'),
                    'additional_meter_price': D(data.get('extra', 0)) if by_meters else D('0.00'),
                    'max_additional_meters': data.get('maxx', D('0.00')) if by_meters else D('0.00'),
                    'is_featured': data.get('featured', False),
                    'is_active': True,
                    'track_inventory': True,
                    'stock': 0,
                },
            )
            count += 1
            for idx, color_name in enumerate(data['colors']):
                color = self.colors[color_name]
                # Vary stock a little; let the first colour carry more stock.
                stock = 25 - idx * 4
                ProductVariant.objects.update_or_create(
                    product=product, color=color,
                    defaults={
                        'sku': f"{product.sku}-{color.slug[:3].upper()}",
                        'price_delta': D('0.00'),
                        'stock': max(stock, 3),
                        'is_active': True,
                    },
                )
                variants += 1
        self.stdout.write(f'  Products: {count}  (variants: {variants})')

    def _seed_discounts(self):
        now = timezone.now()
        cat = self.categories

        def make(name, dtype, value, *, products=None, categories=None,
                 start=None, end=None, priority=0, code=''):
            obj, _ = Discount.objects.update_or_create(
                name=name,
                defaults={
                    'code': code, 'discount_type': dtype, 'value': D(value),
                    'start_at': start, 'end_at': end, 'priority': priority,
                    'is_active': True,
                },
            )
            obj.products.set(products or [])
            obj.categories.set(categories or [])
            return obj

        # 10% off every unstitched suit (category-wide, percentage).
        make('Unstitched Suit Sale', constants.DiscountType.PERCENTAGE, 10,
             categories=[cat['unstitched-suits']], priority=1, code='SUIT10')

        # Eid Special — 20% off premium suits, time-boxed.
        make('Eid Special — Premium', constants.DiscountType.PERCENTAGE, 20,
             categories=[cat['premium-suits']],
             start=now - timedelta(days=1), end=now + timedelta(days=30),
             priority=5, code='EID20')

        # Flat Rs 500 off two specific Karandi winter suits (fixed amount).
        karandi = Product.objects.filter(sku__in=['AR-KAR-001', 'AR-KAR-002'])
        make('Winter Karandi Offer', constants.DiscountType.FIXED, 500,
             products=list(karandi), priority=3, code='WINTER500')

        # Clearance — deeper 25% off a single product (beats the category sale).
        clearance = Product.objects.filter(sku='AR-COT-002')
        make('Cotton Clearance', constants.DiscountType.PERCENTAGE, 25,
             products=list(clearance), priority=10, code='CLEAR25')

        self.stdout.write(f'  Discounts: {Discount.objects.count()}')

    def _seed_shipping(self):
        rates = {
            constants.PROVINCE_PUNJAB: 200,
            constants.PROVINCE_SINDH: 250,
            constants.PROVINCE_KPK: 250,
            constants.PROVINCE_BALOCHISTAN: 300,
            constants.PROVINCE_ICT: 200,
            constants.PROVINCE_GB: 350,
            constants.PROVINCE_AJK: 300,
        }
        for province, rate in rates.items():
            ShippingRate.objects.update_or_create(
                province=province, defaults={'rate': D(rate), 'is_active': True},
            )
        self.stdout.write(f'  Shipping rates: {len(rates)}')

    def _seed_settings(self):
        s = StoreSetting.load()
        s.store_name = 'Al Rayan'
        s.default_shipping_fee = D('250.00')
        s.free_shipping_threshold = D('10000.00')
        s.cod_enabled = True
        s.contact_phone = '+92 300 1234567'
        s.contact_email = 'orders@alrayan.pk'
        s.save()
        self.stdout.write('  Store settings: configured')

    def _seed_orders(self):
        # Build a couple of representative orders if none exist yet.
        if Order.objects.exists():
            self.stdout.write('  Orders: skipped (already present)')
            return

        def line(order, sku, color=None, extra=D('0.00'), qty=1):
            product = Product.objects.get(sku=sku)
            variant = None
            if color:
                variant = product.variants.filter(color__name=color).first()
            item = OrderItem(order=order)
            item.populate_from(product, variant, extra, qty)
            item.save()

        # Order 1 — delivered & paid, with extended length.
        o1 = Order.objects.create(
            full_name='Ahmed Raza', phone='+92 301 2345678',
            email='ahmed.raza@example.com',
            address_line='House 12, Street 5, Model Town', city='Lahore',
            province=constants.PROVINCE_PUNJAB, postal_code='54000',
            status=constants.OrderStatus.DELIVERED,
            customer_note='Please pack neatly.',
        )
        line(o1, 'AR-KAR-001', color='Charcoal', extra=D('1.00'))
        line(o1, 'AR-WNW-001', color='Steel Blue')
        o1.recalculate_totals()
        o1.mark_paid()

        # Order 2 — pending COD, multiple quantities.
        o2 = Order.objects.create(
            full_name='Bilal Hussain', phone='+92 333 9876543',
            address_line='Flat 4B, Clifton Block 2', city='Karachi',
            province=constants.PROVINCE_SINDH,
            status=constants.OrderStatus.PENDING,
        )
        line(o2, 'AR-COT-001', color='Mustard', qty=2)
        line(o2, 'AR-BSK-001', color='Sand', extra=D('0.50'))
        o2.recalculate_totals()

        # Order 3 — confirmed, premium with Eid discount applied.
        o3 = Order.objects.create(
            full_name='Usman Tariq', phone='+92 321 4567890',
            email='usman@example.com',
            address_line='Sector F-8/3', city='Islamabad',
            province=constants.PROVINCE_ICT,
            status=constants.OrderStatus.CONFIRMED,
        )
        line(o3, 'AR-BSK-002', color='Navy Blue')
        o3.recalculate_totals()

        self.stdout.write(f'  Orders: {Order.objects.count()} demo orders created')

    def _seed_superuser(self):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('  Superuser: already exists (skipped)')
            return
        User.objects.create_superuser('admin', 'admin@alrayan.pk', 'admin12345')
        self.stdout.write(self.style.WARNING(
            '  Superuser created → username: admin  password: admin12345'))

    def _summary(self):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('Catalogue summary'))
        for p in Product.objects.select_related('fabric', 'category').order_by('sku'):
            sale = ''
            if p.is_on_sale:
                sale = f"  → Rs {p.final_price:,.0f}  (-{p.savings_percentage}%)"
            self.stdout.write(
                f"  {p.sku:<16} {p.name[:34]:<34} Rs {p.base_price:>7,.0f}{sale}")


def _slug(name):
    from django.utils.text import slugify
    return slugify(name)
