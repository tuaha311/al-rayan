"""Seed a clean database with the Floral Finesse women's couture catalogue.

Floral Finesse (instagram.com/floral.finesse) is a Pakistani couture label:
"Bespoke storytelling couture | Hand painting • Embroidery • 3D artistry".
Their highlights (Digital Printed, Embroidery, Shawls, 3D Embellished, art
look book) map onto the categories below, alongside Formals and Bridal Couture.

Every product and category gets a photo from seed_media/floral/. These are
free-licence Pexels stock photos standing in for the label's own shoots (see
seed_media/floral/CREDITS.md) — replace them with real product photography
before launch.

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
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
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
    ProductImage,
    ProductVariant,
    Season,
    ShippingRate,
    StoreSetting,
)

D = Decimal

MEDIA_DIR = Path(__file__).resolve().parent / 'seed_media' / 'floral'


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
    ('Fuchsia', '#C2185B'),
    ('Red', '#B3202A'),
    ('Mauve', '#B784A7'),
    ('Lilac', '#C8A2C8'),
    ('Plum', '#5E2750'),
    ('Maroon', '#5A1A22'),
    ('Powder Blue', '#B0C4DE'),
    ('Royal Blue', '#2840A0'),
    ('Navy', '#1F2A44'),
    ('Teal', '#1F6F78'),
    ('Mint', '#BDE3C9'),
    ('Sage Green', '#9CAF88'),
    ('Olive', '#708238'),
    ('Emerald', '#0B6E4F'),
    ('Mustard', '#C9A227'),
    ('Mocha', '#7B5E4B'),
    ('Black', '#1A1A1A'),
]

# (name, parent_slug or None, sort_order, description, image)
# Images are Pexels photos (free licence) bundled in seed_media/floral/.
CATEGORIES = [
    ('Women', None, 1, 'Couture and prêt for women.', 'pexels-33023960.jpg'),
    ('Hand Painted', 'women', 1,
     'One-of-a-kind pieces painted by hand — wearable art.', 'pexels-36634896.jpg'),
    ('Embroidered', 'women', 2,
     'Thread, zari and resham embroidery on premium bases.', 'pexels-33210512.jpg'),
    ('3D Embellished', 'women', 3,
     'Sculpted florals, appliqué and dimensional hand-work.', 'pexels-6018532.jpg'),
    ('Digital Printed', 'women', 4,
     'Vivid digital prints on lawn, cambric and silk.', 'pexels-7200995.jpg'),
    ('Formals', 'women', 5,
     'Evening and festive formals — lehengas, anarkalis and jacket sets.',
     'pexels-39299504.jpg'),
    ('Bridal Couture', 'women', 6,
     'Made-to-order bridal lehengas and ghararas for every event.', 'pexels-8497817.jpg'),
    ('Shawls', None, 2, 'Hand-painted and embroidered shawls and wraps.', 'pexels-4972976.jpg'),
]

# Each product: sku, name, category slug, fabric, season, price, featured,
# colours, a one-line pitch and its photo. Couture pieces are sold per
# suit/piece; digital printed unstitched fabric is sold by length
# (by_meters=True).
#
# An optional ``gallery`` lists extra shots shown after the main photo on the
# product page — a filename, or (filename, colour) to tie the shot to that
# colour variant. With no alternate angles in the stock set, these borrow
# photos of similar pieces from the same category.
#
# Prices follow the bands a Pakistani luxury atelier charges in PKR (prêt
# ~15k–60k, luxury/semi-formal ~45k–250k, formals ~165k–400k, bridal
# ~450k–900k, shawls ~95k–220k).
PRODUCTS = [
    # --- Hand Painted -----------------------------------------------------
    dict(sku='FF-HP-001', name='Gul-e-Rana Hand Painted Silk Suit', category='hand-painted',
         fabric='Pure Silk', season='Festive', price=98000, featured=True,
         colors=['Blush Pink', 'Ivory'], image='pexels-35902078.jpg',
         gallery=['pexels-36634896.jpg', 'pexels-36104913.jpg'],
         pitch='Rose-garden motifs hand painted across the shirt and dupatta.'),
    dict(sku='FF-HP-002', name='Mor Bagh Hand Painted Organza Suit', category='hand-painted',
         fabric='Organza', season='Festive', price=128000, featured=True,
         colors=['Mint', 'Champagne'], image='pexels-36104913.jpg',
         pitch='Peacock-garden story told in fine brushwork on organza.'),
    dict(sku='FF-HP-003', name='Tapestry Tales Hand Painted Raw Silk Suit', category='hand-painted',
         fabric='Raw Silk', season='All Season', price=86000, featured=False,
         colors=['Royal Blue', 'Maroon'], image='pexels-35902071.jpg',
         pitch='Folk-tapestry birds and vines painted on a raw silk base.'),
    dict(sku='FF-HP-004', name='Neel Kamal Hand Painted Lawn Suit', category='hand-painted',
         fabric='Lawn', season='Summer', price=45000, featured=False,
         colors=['Powder Blue', 'Ivory'], image='pexels-36090363.jpg',
         pitch='Lotus ponds painted on breathable lawn for summer days.'),
    dict(sku='FF-HP-005', name='Gulnar Hand Painted Chiffon Suit', category='hand-painted',
         fabric='Chiffon', season='Festive', price=74000, featured=False,
         colors=['Blush Pink', 'Lilac'], image='pexels-36634896.jpg',
         pitch='Pomegranate blossoms painted along a sweeping chiffon dupatta.'),
    dict(sku='FF-HP-006', name='Sunehri Dhoop Hand Painted Lehenga', category='hand-painted',
         fabric='Raw Silk', season='Festive', price=145000, featured=True,
         colors=['Mustard', 'Peach'], image='pexels-19345934.jpg',
         pitch='A mehndi lehenga painted with marigold borders in warm gold.'),
    # --- Embroidered ------------------------------------------------------
    dict(sku='FF-EM-001', name='Zarnigar Embroidered Chiffon Suit', category='embroidered',
         fabric='Chiffon', season='Festive', price=76000, featured=True,
         colors=['Red', 'Emerald', 'Plum'], image='pexels-33210508.jpg',
         pitch='Zari and resham florals on chiffon with a scalloped dupatta.'),
    dict(sku='FF-EM-002', name='Noor Jahan Embroidered Raw Silk Suit', category='embroidered',
         fabric='Raw Silk', season='Festive', price=118000, featured=False,
         colors=['Mocha', 'Maroon'], image='pexels-27603276.jpg',
         pitch='Mughal-inspired jaal embroidery with hand-finished borders.'),
    dict(sku='FF-EM-003', name='Bahar Embroidered Lawn Suit', category='embroidered',
         fabric='Lawn', season='Summer', price=38000, featured=False,
         colors=['Mint', 'Peach', 'Lilac'], image='pexels-34182932.jpg',
         pitch='Spring blossoms embroidered on the neckline and sleeves.'),
    dict(sku='FF-EM-004', name='Shab-e-Velvet Embroidered Suit', category='embroidered',
         fabric='Velvet', season='Winter', price=135000, featured=False,
         colors=['Black', 'Emerald', 'Maroon'], image='pexels-28390542.jpg',
         pitch='Deep velvet with antique-gold tilla embroidery.'),
    dict(sku='FF-EM-005', name='Chandni Chikankari Lawn Suit', category='embroidered',
         fabric='Lawn', season='Summer', price=42000, featured=False,
         colors=['Lilac', 'Ivory'], image='pexels-36325842.jpg',
         pitch='Shadow-work chikankari scattered over a soft lawn shirt.'),
    dict(sku='FF-EM-006', name='Aab-e-Hayat Embroidered Organza Suit', category='embroidered',
         fabric='Organza', season='Festive', price=88000, featured=False,
         colors=['Teal', 'Powder Blue'], image='pexels-34182980.jpg',
         pitch='Sequin-lit resham vines on a crisp organza dupatta.'),
    dict(sku='FF-EM-007', name='Shehnaz Embroidered Velvet Suit', category='embroidered',
         fabric='Velvet', season='Winter', price=140000, featured=False,
         colors=['Plum', 'Black'], image='pexels-35340689.jpg',
         pitch='Plum velvet with a dabka-worked yoke and gold-edged dupatta.'),
    # --- 3D Embellished ---------------------------------------------------
    dict(sku='FF-3D-001', name='Gulposh 3D Floral Organza Suit', category='3d-embellished',
         fabric='Organza', season='Festive', price=185000, featured=True,
         colors=['Lilac', 'Ivory'], image='pexels-3460676.jpg',
         gallery=['pexels-6018532.jpg', 'pexels-5721528.jpg'],
         pitch='Hand-sculpted 3D blooms cascading over sheer organza.'),
    dict(sku='FF-3D-002', name='Titli 3D Embellished Chiffon Suit', category='3d-embellished',
         fabric='Chiffon', season='Festive', price=165000, featured=False,
         colors=['Peach', 'Powder Blue'], image='pexels-36325948.jpg',
         pitch='Butterfly appliqué and pearl detailing with a flowing dupatta.'),
    dict(sku='FF-3D-003', name='Saffron Garden 3D Silk Suit', category='3d-embellished',
         fabric='Pure Silk', season='Festive', price=245000, featured=False,
         colors=['Olive', 'Mustard'], image='pexels-39299445.jpg',
         pitch='Dimensional marigolds and hand-beading on pure silk.'),
    dict(sku='FF-3D-004', name='Gulabi 3D Embellished Gown', category='3d-embellished',
         fabric='Organza', season='Festive', price=210000, featured=False,
         colors=['Blush Pink'], image='pexels-5721528.jpg',
         pitch='A floor-length gown strewn with 3D petals and crystal dew.'),
    # --- Digital Printed (unstitched, by length) --------------------------
    dict(sku='FF-DP-001', name='Phulkari Digital Printed Lawn', category='digital-printed',
         fabric='Lawn', season='Summer', price=14500, by_meters=True,
         meters=D('3.00'), extra=3800, maxx=D('1.50'), featured=True,
         colors=['Emerald', 'Mustard'], image='pexels-7200995.jpg',
         pitch='Phulkari-inspired print with a printed chiffon dupatta.'),
    dict(sku='FF-DP-002', name='Botanica Digital Printed Cambric', category='digital-printed',
         fabric='Cambric', season='All Season', price=16800, by_meters=True,
         meters=D('3.00'), extra=4200, maxx=D('1.50'), featured=False,
         colors=['Sage Green', 'Ivory'], image='pexels-29413592.jpg',
         pitch='Botanical illustration print on soft cambric.'),
    dict(sku='FF-DP-003', name='Kashi Tiles Digital Printed Khaddar', category='digital-printed',
         fabric='Khaddar', season='Winter', price=18500, by_meters=True,
         meters=D('3.00'), extra=4600, maxx=D('1.50'), featured=False,
         colors=['Navy', 'Maroon'], image='pexels-29413606.jpg',
         pitch='Multan kashi-tile geometry printed on warm khaddar.'),
    dict(sku='FF-DP-004', name='Silk Route Digital Printed Silk', category='digital-printed',
         fabric='Pure Silk', season='Festive', price=26000, by_meters=True,
         meters=D('2.50'), extra=8500, maxx=D('1.00'), featured=False,
         colors=['Navy', 'Champagne'], image='pexels-28213811.jpg',
         pitch='Caravan-and-arch print on pure silk for evening wear.'),
    dict(sku='FF-DP-005', name='Lavender Fields Digital Printed Lawn', category='digital-printed',
         fabric='Lawn', season='Summer', price=15500, by_meters=True,
         meters=D('3.00'), extra=3900, maxx=D('1.50'), featured=False,
         colors=['Lilac', 'Champagne'], image='pexels-36104968.jpg',
         pitch='Wild-lavender sprigs printed edge to edge with a matching dupatta.'),
    # --- Formals ----------------------------------------------------------
    dict(sku='FF-FM-001', name='Mehtab Embellished Velvet Lehenga', category='formals',
         fabric='Velvet', season='Winter', price=385000, featured=True,
         colors=['Black', 'Maroon'], image='pexels-37962746.jpg',
         gallery=[('pexels-39299452.jpg', 'Black'), ('pexels-28390542.jpg', 'Maroon')],
         pitch='Midnight velvet lehenga with a kamdani-worked net dupatta.'),
    dict(sku='FF-FM-002', name='Zeba Gota Raw Silk Anarkali', category='formals',
         fabric='Raw Silk', season='Festive', price=265000, featured=False,
         colors=['Champagne', 'Ivory'], image='pexels-9418537.jpg',
         pitch='A flared anarkali edged in gota and finished with a tissue dupatta.'),
    dict(sku='FF-FM-003', name='Sitara Sequinned Organza Kurta Set', category='formals',
         fabric='Organza', season='Festive', price=168000, featured=False,
         colors=['Mocha', 'Black'], image='pexels-35485409.jpg',
         pitch='Hand-sequinned organza kurta with straight pants and dupatta.'),
    dict(sku='FF-FM-004', name='Raat ki Rani Net Formal', category='formals',
         fabric='Chiffon', season='Festive', price=210000, featured=False,
         colors=['Black'], image='pexels-39299452.jpg',
         pitch='Black-on-black resham and crystal work on layered chiffon.'),
    dict(sku='FF-FM-005', name='Zaitoon Jacket Set', category='formals',
         fabric='Raw Silk', season='All Season', price=240000, featured=False,
         colors=['Olive', 'Plum'], image='pexels-39299441.jpg',
         pitch='An embroidered olive jacket over a slip, with a plum velvet shawl.'),
    dict(sku='FF-FM-006', name='Hara Bagh Lehenga Set', category='formals',
         fabric='Raw Silk', season='Festive', price=195000, featured=False,
         colors=['Emerald'], image='pexels-28405815.jpg',
         pitch='Emerald lehenga with gold lotus motifs and a cropped choli.'),
    dict(sku='FF-FM-007', name='Gulabi Shaam Lehenga', category='formals',
         fabric='Organza', season='Festive', price=225000, featured=False,
         colors=['Fuchsia', 'Blush Pink'], image='pexels-37628608.jpg',
         gallery=['pexels-28405815.jpg', 'pexels-39299504.jpg'],
         pitch='Mirror-worked pink lehenga with a sheer organza dupatta.'),
    # --- Bridal Couture ---------------------------------------------------
    dict(sku='FF-BR-001', name='Laal Jora Bridal Lehenga', category='bridal-couture',
         fabric='Velvet', season='Festive', price=895000, featured=True,
         colors=['Maroon', 'Red'], image='pexels-12791932.jpg',
         gallery=[('pexels-13124449.jpg', 'Red'), ('pexels-30167011.jpg', 'Maroon'),
                  'pexels-8497817.jpg', 'pexels-16125951.jpg'],
         pitch='A heritage baraat lehenga in zardozi, dabka and naqshi.'),
    dict(sku='FF-BR-002', name='Mehr-un-Nisa Bridal Gharara', category='bridal-couture',
         fabric='Raw Silk', season='Festive', price=760000, featured=False,
         colors=['Maroon'], image='pexels-30167011.jpg',
         gallery=['pexels-12791932.jpg', 'pexels-8497817.jpg'],
         pitch='Traditional gharara with a kamdani dupatta and gota-trimmed kurti.'),
    dict(sku='FF-BR-003', name='Noor-e-Sahar Walima Lehenga', category='bridal-couture',
         fabric='Organza', season='Festive', price=640000, featured=False,
         colors=['Ivory', 'Champagne'], image='pexels-16125951.jpg',
         gallery=['pexels-8497817.jpg', 'pexels-35591476.jpg', 'pexels-7578483.jpg'],
         pitch='Ivory and antique-gold walima lehenga with pearl-strewn borders.'),
    dict(sku='FF-BR-004', name='Mehndi Rang Lehenga', category='bridal-couture',
         fabric='Raw Silk', season='Festive', price=465000, featured=False,
         colors=['Mustard', 'Fuchsia'], image='pexels-35591476.jpg',
         gallery=[('pexels-19345934.jpg', 'Mustard'), ('pexels-7578483.jpg', 'Fuchsia')],
         pitch='Turmeric-yellow mehndi lehenga with a contrast pink dupatta.'),
    dict(sku='FF-BR-005', name='Shehzadi Bridal Lehenga', category='bridal-couture',
         fabric='Velvet', season='Winter', price=820000, featured=False,
         colors=['Red'], image='pexels-13124449.jpg',
         gallery=['pexels-12791932.jpg', 'pexels-30167011.jpg', 'pexels-8497817.jpg'],
         pitch='Classic red bridal with a fully worked kalidar skirt.'),
    dict(sku='FF-BR-006', name='Gulnaar Baraat Lehenga', category='bridal-couture',
         fabric='Raw Silk', season='Festive', price=700000, featured=False,
         colors=['Fuchsia', 'Maroon'], image='pexels-7578483.jpg',
         gallery=[('pexels-37628608.jpg', 'Fuchsia'), ('pexels-12791932.jpg', 'Maroon'),
                  'pexels-13124449.jpg', 'pexels-8497817.jpg'],
         pitch='Magenta baraat lehenga with jamawar-inspired gold work.'),
    # --- Shawls -----------------------------------------------------------
    dict(sku='FF-SH-001', name='Chinar Hand Painted Pashmina Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=165000, featured=True,
         colors=['Red', 'Ivory'], image='pexels-4972908.jpg',
         gallery=['pexels-4972976.jpg', 'pexels-13103385.jpg'],
         pitch='Autumn chinar leaves hand painted along the pallu.'),
    dict(sku='FF-SH-002', name='Kashida Embroidered Pashmina Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=220000, featured=False,
         colors=['Teal', 'Champagne', 'Plum'], image='pexels-13103385.jpg',
         pitch='Kashmiri kashida embroidery on a soft pashmina blend.'),
    dict(sku='FF-SH-003', name='Velvet Tilla Shawl', category='shawls',
         fabric='Velvet', season='Winter', price=195000, featured=False,
         colors=['Black', 'Emerald'], image='pexels-20436271.jpg',
         pitch='Velvet wrap edged with hand-worked tilla borders.'),
    dict(sku='FF-SH-004', name='Neelam Embroidered Pashmina Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=140000, featured=False,
         colors=['Navy'], image='pexels-38537257.jpg',
         pitch='Sapphire pashmina with an ivory sozni-embroidered border.'),
    dict(sku='FF-SH-005', name='Barf Phool Embroidered Shawl', category='shawls',
         fabric='Pashmina', season='Winter', price=98000, featured=False,
         colors=['Ivory'], image='pexels-5561553.jpg',
         pitch='Snow-white wrap with pastel florals and hand-knotted fringe.'),
    dict(sku='FF-SH-006', name='Banafsha Pashmina Stole', category='shawls',
         fabric='Pashmina', season='Winter', price=95000, featured=False,
         colors=['Plum'], image='pexels-33411297.jpg',
         pitch='A violet stole light enough for evenings into early spring.'),
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
        for name, parent_slug, order, desc, image in CATEGORIES:
            obj, _ = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={'name': name, 'parent': out.get(parent_slug),
                          'sort_order': order, 'description': desc},
            )
            # Only fill a gap — never replace an image uploaded in the admin.
            if not obj.image:
                obj.image = self._store_media(image, 'categories')
                obj.save(update_fields=['image'])
            out[obj.slug] = obj
        self.stdout.write(f'  Categories: {len(out)}')
        return out

    def _seed_products(self):
        count = variants = photos = 0
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
            by_color = {}
            for idx, color_name in enumerate(data['colors']):
                color = self.colors[color_name]
                by_color[color_name], _ = ProductVariant.objects.update_or_create(
                    product=product, color=color,
                    defaults={
                        'sku': f"{product.sku}-{color.slug[:3].upper()}",
                        'price_delta': D('0.00'),
                        'stock': max(base_stock - idx * 2, 2),
                        'is_active': True,
                    },
                )
                variants += 1
            photos += self._attach_photos(
                product, data['image'], data.get('gallery', ()), by_color)
        self.stdout.write(
            f'  Products: {count}  (variants: {variants}, photos: {photos})')

    def _store_media(self, filename, folder):
        """Copy a bundled photo into media storage once; return its stored name.

        A fixed name (no upload_to suffixing) keeps re-runs and --flush from
        piling up duplicate files.
        """
        name = f'{folder}/{filename}'
        if not default_storage.exists(name):
            with open(MEDIA_DIR / filename, 'rb') as fh:
                name = default_storage.save(name, File(fh))
        return name

    def _attach_photos(self, product, main, gallery, by_color):
        """Attach the main photo plus any gallery shots; return how many."""
        folder = f'products/{product.slug}'
        shots = [(main, None)] + [
            (s, None) if isinstance(s, str) else s for s in gallery
        ]
        names = []
        for order, (filename, color_name) in enumerate(shots):
            name = self._store_media(filename, folder)
            names.append(name)
            ProductImage.objects.update_or_create(
                product=product, image=name,
                defaults={
                    'alt_text': product.name if order == 0
                    else f'{product.name} — view {order + 1}',
                    'is_primary': order == 0,
                    'sort_order': order,
                    'variant': by_color.get(color_name),
                },
            )
        # Drop photos an earlier version of this seed attached, keep any added
        # by hand in the admin.
        product.images.filter(image__startswith=f'{folder}/pexels-') \
            .exclude(image__in=names).delete()
        return len(names)

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

        # Flat Rs 10,000 off one hand-painted signature piece.
        make('Tapestry Tales Offer', constants.DiscountType.FIXED, 10000,
             products=list(Product.objects.filter(sku='FF-HP-003')),
             priority=10, code='TAPESTRY10K')

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
