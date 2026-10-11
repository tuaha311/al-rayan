"""Seed a clean database with the Floral Finesse women's couture catalogue.

Floral Finesse (instagram.com/floral.finesse) is a Pakistani couture label:
"Bespoke storytelling couture | Hand painting • Embroidery • 3D artistry".
Their highlights (Digital Printed, Embroidery, Shawls, 3D Embellished, art
look book) map onto the categories below.

Usage:
    python manage.py seed_floral                    # idempotent create/update
    python manage.py seed_floral --flush            # wipe store data first
    python manage.py seed_floral --with-superuser   # also create an admin login
    python manage.py seed_floral --demo-orders      # add a few sample orders

All money is in PKR. Re-running without --flush is safe; records are matched
by their natural keys (slug / sku / name) and updated in place.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

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
    ('Lawn', 'Fine, breathable cotton lawn — the summer staple.'),
    ('Cambric', 'Slightly heavier cotton with a soft, smooth hand.'),
    ('Khaddar', 'Textured winter cotton with a warm, rustic weave.'),
    ('Chiffon', 'Sheer and fluid, made for dupattas and festive layers.'),
    ('Organza', 'Crisp, translucent silk-feel fabric that holds 3D work beautifully.'),
    ('Raw Silk', 'Lustrous slub-textured silk, a formal-wear favourite.'),
    ('Pure Silk', 'Smooth, rich silk that takes hand painting like a canvas.'),
    ('Velvet', 'Plush winter-wedding fabric with deep colour.'),
    ('Pashmina', 'Soft, warm wool blend for shawls and wraps.'),
]

SEASONS = [
    ('Summer', 1),
    ('Winter', 2),
    ('Festive', 3),
    ('All Season', 4),
]

COLORS = [
    ('Ivory', '#FFFFF0'),
    ('Champagne', '#F1DDCF'),
    ('Peach', '#F6C1A6'),
    ('Blush Pink', '#F4C2C2'),
    ('Dusty Rose', '#C08081'),
    ('Mauve', '#B784A7'),
    ('Lilac', '#C8A2C8'),
    ('Plum', '#5E2750'),
    ('Maroon', '#5A1A22'),
    ('Powder Blue', '#B0C4DE'),
    ('Teal', '#1F6F78'),
    ('Mint', '#BDE3C9'),
    ('Sage Green', '#9CAF88'),
    ('Emerald', '#0B6E4F'),
    ('Mustard', '#C9A227'),
    ('Black', '#1A1A1A'),
]

# (name, parent_slug or None, sort_order, description)
CATEGORIES = [
    ('Women', None, 1, 'Couture and prêt for women.'),
    ('Hand Painted', 'women', 1,
     'One-of-a-kind pieces painted by hand — wearable art.'),
    ('Embroidered', 'women', 2,
     'Thread, zari and resham embroidery on premium bases.'),
    ('3D Embellished', 'women', 3,
     'Sculpted florals, appliqué and dimensional hand-work.'),
    ('Digital Printed', 'women', 4,
     'Vivid digital prints on lawn, cambric and silk.'),
    ('Shawls', None, 2, 'Hand-painted and embroidered shawls and wraps.'),
]

# Each product: sku, name, category slug, fabric, season, price, featured,
# colours, and a one-line pitch. Couture pieces are sold per suit/piece;
# digital printed unstitched fabric is sold by length (by_meters=True).
PRODUCTS = [
    # --- Hand Painted -----------------------------------------------------
    dict(sku='FF-HP-001', name='Gul-e-Rana Hand Painted Silk Suit', category='hand-painted',
         fabric='Pure Silk', season='Festive', price=34500, featured=True,
         colors=['Ivory', 'Blush Pink'],
         pitch='Rose-garden motifs hand painted across the shirt and dupatta.'),
    dict(sku='FF-HP-002', name='Mor Bagh Hand Painted Organza Suit', category='hand-painted',
         fabric='Organza', season='Festive', price=38000, featured=True,
         colors=['Champagne', 'Mint'],
         pitch='Peacock-garden story told in fine brushwork on organza.'),
    dict(sku='FF-HP-003', name='Tapestry Tales Hand Painted Raw Silk Suit', category='hand-painted',
         fabric='Raw Silk', season='All Season', price=29500, featured=False,
         colors=['Teal', 'Maroon', 'Black'],
         pitch='Folk-tapestry birds and vines painted on a raw silk base.'),
    dict(sku='FF-HP-004', name='Neel Kamal Hand Painted Lawn Suit', category='hand-painted',
         fabric='Lawn', season='Summer', price=18500, featured=False,
         colors=['Powder Blue', 'Ivory'],
         pitch='Lotus ponds painted on breathable lawn for summer days.'),
    # --- Embroidered ------------------------------------------------------
    dict(sku='FF-EM-001', name='Zarnigar Embroidered Chiffon Suit', category='embroidered',
         fabric='Chiffon', season='Festive', price=26500, featured=True,
         colors=['Dusty Rose', 'Emerald', 'Plum'],
         pitch='Zari and resham florals on chiffon with a scalloped dupatta.'),
    dict(sku='FF-EM-002', name='Noor Jahan Embroidered Raw Silk Suit', category='embroidered',
         fabric='Raw Silk', season='Festive', price=31000, featured=False,
         colors=['Maroon', 'Champagne'],
         pitch='Mughal-inspired jaal embroidery with hand-finished borders.'),
    dict(sku='FF-EM-003', name='Bahar Embroidered Lawn Suit', category='embroidered',
         fabric='Lawn', season='Summer', price=12500, featured=False,
         colors=['Mint', 'Peach', 'Lilac'],
         pitch='Spring blossoms embroidered on the neckline and sleeves.'),
    dict(sku='FF-EM-004', name='Shab-e-Velvet Embroidered Suit', category='embroidered',
         fabric='Velvet', season='Winter', price=36000, featured=False,
         colors=['Black', 'Emerald', 'Maroon'],
         pitch='Deep velvet with antique-gold tilla embroidery.'),
    # --- 3D Embellished ---------------------------------------------------
    dict(sku='FF-3D-001', name='Gulposh 3D Floral Organza Suit', category='3d-embellished',
         fabric='Organza', season='Festive', price=48500, featured=True,
         colors=['Ivory', 'Lilac'],
         pitch='Hand-sculpted 3D blooms cascading over sheer organza.'),
    dict(sku='FF-3D-002', name='Titli 3D Embellished Chiffon Suit', category='3d-embellished',
         fabric='Chiffon', season='Festive', price=42000, featured=False,
         colors=['Blush Pink', 'Powder Blue'],
         pitch='Butterfly appliqué and pearl detailing with a flowing dupatta.'),
    dict(sku='FF-3D-003', name='Saffron Garden 3D Silk Suit', category='3d-embellished',
         fabric='Pure Silk', season='Festive', price=55000, featured=False,
         colors=['Mustard', 'Plum'],
         pitch='Dimensional marigolds and hand-beading on pure silk.'),
    # --- Digital Printed (unstitched, by length) --------------------------
    dict(sku='FF-DP-001', name='Phulkari Digital Printed Lawn', category='digital-printed',
         fabric='Lawn', season='Summer', price=6500, by_meters=True,
         meters=D('3.00'), extra=1800, maxx=D('1.50'), featured=True,
         colors=['Peach', 'Teal', 'Mustard'],
         pitch='Phulkari-inspired print with a printed chiffon dupatta.'),
    dict(sku='FF-DP-002', name='Botanica Digital Printed Cambric', category='digital-printed',
         fabric='Cambric', season='All Season', price=7200, by_meters=True,
         meters=D('3.00'), extra=2000, maxx=D('1.50'), featured=False,
         colors=['Sage Green', 'Dusty Rose', 'Ivory'],
         pitch='Botanical illustration print on soft cambric.'),
    dict(sku='FF-DP-003', name='Kashi Tiles Digital Printed Khaddar', category='digital-printed',
         fabric='Khaddar', season='Winter', price=7800, by_meters=True,
         meters=D('3.00'), extra=2200, maxx=D('1.50'), featured=False,
         colors=['Teal', 'Maroon', 'Mustard'],
         pitch='Multan kashi-tile geometry printed on warm khaddar.'),
    dict(sku='FF-DP-004', name='Silk Route Digital Printed Silk', category='digital-printed',
         fabric='Pure Silk', season='Festive', price=11500, by_meters=True,
         meters=D('2.50'), extra=3800, maxx=D('1.00'), featured=False,
         colors=['Plum', 'Champagne'],
         pitch='Caravan-and-arch print on pure silk for evening wear.'),
    # --- Shawls -----------------------------------------------------------
    dict(sku='FF-SH-001', name='Chinar Hand Painted Pashmina Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=16500, featured=True,
         colors=['Ivory', 'Maroon', 'Black'],
         pitch='Autumn chinar leaves hand painted along the pallu.'),
    dict(sku='FF-SH-002', name='Kashida Embroidered Pashmina Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=22000, featured=False,
         colors=['Champagne', 'Teal', 'Plum'],
         pitch='Kashmiri kashida embroidery on a soft pashmina blend.'),
    dict(sku='FF-SH-003', name='Velvet Tilla Shawl', category='shawls',
         fabric='Velvet', season='Winter', price=19500, featured=False,
         colors=['Black', 'Emerald'],
         pitch='Velvet wrap edged with hand-worked tilla borders.'),
]


class Command(BaseCommand):
    help = 'Seed the Floral Finesse women\'s couture catalogue (clean-DB friendly).'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete existing store data before seeding.')
        parser.add_argument('--with-superuser', action='store_true',
                            help='Create an admin/admin12345 superuser if none exists.')
        parser.add_argument('--demo-orders', action='store_true',
                            help='Create a few sample orders (skipped if orders exist).')

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

        if options['demo_orders']:
            self._seed_orders()
        if options['with_superuser']:
            self._seed_superuser()

        self.stdout.write(self.style.SUCCESS('\n✔ Floral Finesse store seeded successfully.'))
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
        for name, parent_slug, order, desc in CATEGORIES:
            obj, _ = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={'name': name, 'parent': out.get(parent_slug),
                          'sort_order': order, 'description': desc},
            )
            out[obj.slug] = obj
        self.stdout.write(f'  Categories: {len(out)}')
        return out

    def _seed_products(self):
        count = variants = 0
        for data in PRODUCTS:
            by_meters = data.get('by_meters', False)
            fabric = data['fabric']
            if by_meters:
                short = (f"Unstitched {fabric.lower()} — {data['meters']} m shirt "
                         f"fabric with dupatta and trouser.")
                tail = ' Need a longer shirt? Add extra length at checkout.'
            else:
                short = f"{data['category'].replace('-', ' ').title()} {fabric.lower()} couture piece."
                tail = ' Each piece is finished by hand, so slight variations are part of its story.'
            product, _ = Product.objects.update_or_create(
                sku=data['sku'],
                defaults={
                    'name': data['name'],
                    'category': self.categories[data['category']],
                    'fabric': self.fabrics[fabric],
                    'season': self.seasons[data['season']],
                    'short_description': short,
                    'description': data['pitch'] + tail,
                    'base_price': D(data['price']),
                    'sold_by_meters': by_meters,
                    'base_meters': data['meters'] if by_meters else D('0.00'),
                    'additional_meter_price': D(data['extra']) if by_meters else D('0.00'),
                    'max_additional_meters': data['maxx'] if by_meters else D('0.00'),
                    'is_featured': data['featured'],
                    'is_active': True,
                    'track_inventory': True,
                    'stock': 0,
                },
            )
            count += 1
            # Couture is made in small runs; printed fabric carries more stock.
            base_stock = 20 if by_meters else 6
            for idx, color_name in enumerate(data['colors']):
                color = self.colors[color_name]
                ProductVariant.objects.update_or_create(
                    product=product, color=color,
                    defaults={
                        'sku': f"{product.sku}-{color.slug[:3].upper()}",
                        'price_delta': D('0.00'),
                        'stock': max(base_stock - idx * 2, 2),
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

        # Store launch — 10% off all digital printed fabric.
        make('Launch Offer — Digital Printed', constants.DiscountType.PERCENTAGE, 10,
             categories=[cat['digital-printed']], priority=1, code='FFLAUNCH10')

        # Winter shawl edit — 15% off shawls for the next six weeks.
        make('Winter Shawl Edit', constants.DiscountType.PERCENTAGE, 15,
             categories=[cat['shawls']],
             start=now - timedelta(days=1), end=now + timedelta(days=42),
             priority=5, code='SHAWL15')

        # Flat Rs 3,000 off one hand-painted signature piece.
        make('Tapestry Tales Offer', constants.DiscountType.FIXED, 3000,
             products=list(Product.objects.filter(sku='FF-HP-003')),
             priority=10, code='TAPESTRY3K')

        self.stdout.write(f'  Discounts: {Discount.objects.count()}')

    def _seed_shipping(self):
        rates = {
            constants.PROVINCE_PUNJAB: 250,
            constants.PROVINCE_SINDH: 300,
            constants.PROVINCE_KPK: 300,
            constants.PROVINCE_BALOCHISTAN: 350,
            constants.PROVINCE_ICT: 250,
            constants.PROVINCE_GB: 400,
            constants.PROVINCE_AJK: 350,
        }
        for province, rate in rates.items():
            ShippingRate.objects.update_or_create(
                province=province, defaults={'rate': D(rate), 'is_active': True},
            )
        self.stdout.write(f'  Shipping rates: {len(rates)}')

    def _seed_settings(self):
        s = StoreSetting.load()
        s.store_name = 'Floral Finesse'
        s.default_shipping_fee = D('300.00')
        s.free_shipping_threshold = D('25000.00')
        s.cod_enabled = True
        s.contact_phone = '+92 300 6047216'  # from the Instagram profile
        s.contact_email = ''                 # not published yet — set in admin
        s.save()
        self.stdout.write('  Store settings: configured')

    def _seed_orders(self):
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

        # Delivered & paid — a festive couture piece plus a shawl.
        o1 = Order.objects.create(
            full_name='Ayesha Malik', phone='+92 301 2345678',
            email='ayesha.malik@example.com',
            address_line='House 22, Street 3, DHA Phase 5', city='Lahore',
            province=constants.PROVINCE_PUNJAB, postal_code='54000',
            status=constants.OrderStatus.DELIVERED,
            customer_note='Gift wrap please.',
        )
        line(o1, 'FF-HP-001', color='Blush Pink')
        line(o1, 'FF-SH-001', color='Ivory')
        o1.recalculate_totals()
        o1.mark_paid()

        # Pending COD — printed fabric with extra length.
        o2 = Order.objects.create(
            full_name='Hira Siddiqui', phone='+92 333 9876543',
            address_line='Flat 7C, Clifton Block 5', city='Karachi',
            province=constants.PROVINCE_SINDH,
            status=constants.OrderStatus.PENDING,
        )
        line(o2, 'FF-DP-001', color='Peach', extra=D('0.50'), qty=2)
        o2.recalculate_totals()

        # Confirmed — 3D embellished statement piece.
        o3 = Order.objects.create(
            full_name='Mahnoor Qureshi', phone='+92 321 4567890',
            email='mahnoor@example.com',
            address_line='Sector F-7/2', city='Islamabad',
            province=constants.PROVINCE_ICT,
            status=constants.OrderStatus.CONFIRMED,
        )
        line(o3, 'FF-3D-001', color='Ivory')
        o3.recalculate_totals()

        self.stdout.write(f'  Orders: {Order.objects.count()} demo orders created')

    def _seed_superuser(self):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('  Superuser: already exists (skipped)')
            return
        User.objects.create_superuser('admin', 'admin@example.com', 'admin12345')
        self.stdout.write(self.style.WARNING(
            '  Superuser created → username: admin  password: admin12345'))

    def _summary(self):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('Catalogue summary'))
        for p in Product.objects.select_related('category').order_by('sku'):
            sale = ''
            if p.is_on_sale:
                sale = f"  → Rs {p.final_price:,.0f}  (-{p.savings_percentage}%)"
            self.stdout.write(
                f"  {p.sku:<10} {p.name[:40]:<40} Rs {p.base_price:>7,.0f}{sale}")
