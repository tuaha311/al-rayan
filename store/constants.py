"""Shared choices and constants for the store.

Kept in one place so the values used by models, admin and seed data stay
consistent. Pakistan-specific data (provinces, currency) lives here too.
"""

# Currency — the store operates in Pakistani Rupees for now.
CURRENCY_CODE = 'PKR'
CURRENCY_SYMBOL = 'Rs'

# --- Android app -----------------------------------------------------------
# The APK is built from mobile/ and committed to static/app/ so it ships with
# a normal deploy. Bump the version here and in mobile/app/build.gradle.kts
# together — this value only names the downloaded file and labels the UI.
ANDROID_APP_VERSION = '1.0.0'
ANDROID_APK_PATH = 'app/floral-finesse.apk'  # relative to static/
# User-Agent marker the WebView app appends; see mobile/.../MainActivity.kt.
ANDROID_APP_UA_MARKER = 'FloralFinesseApp'

# Administrative units of Pakistan, used for shipping addresses and rates.
PROVINCE_PUNJAB = 'punjab'
PROVINCE_SINDH = 'sindh'
PROVINCE_KPK = 'kpk'
PROVINCE_BALOCHISTAN = 'balochistan'
PROVINCE_ICT = 'ict'
PROVINCE_GB = 'gb'
PROVINCE_AJK = 'ajk'

PROVINCE_CHOICES = [
    (PROVINCE_PUNJAB, 'Punjab'),
    (PROVINCE_SINDH, 'Sindh'),
    (PROVINCE_KPK, 'Khyber Pakhtunkhwa'),
    (PROVINCE_BALOCHISTAN, 'Balochistan'),
    (PROVINCE_ICT, 'Islamabad Capital Territory'),
    (PROVINCE_GB, 'Gilgit-Baltistan'),
    (PROVINCE_AJK, 'Azad Jammu & Kashmir'),
]


# --- Garment sizes ---------------------------------------------------------
# One chart covers every stitched piece. Body measurements in inches, from
# the label's printed Formal Wear size guide.
SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
SIZE_CHOICES = [(s, s) for s in SIZES]

# Product and cart pages warn "Only n left" at or below this many units.
LOW_STOCK_THRESHOLD = 5

# (size, bust, hip, shirt length)
SHIRT_SIZE_CHART = [
    ('XS', 34, 36, 47),
    ('S', 36, 38, 47),
    ('M', 38, 40, 47),
    ('L', 40, 42, 47),
    ('XL', 42, 44, 47),
    ('XXL', 44, 46, 47),
]
# (size, waist, hip)
TROUSER_SIZE_CHART = [
    ('XS', 28, 36),
    ('S', 30, 38),
    ('M', 32, 40),
    ('L', 34, 42),
    ('XL', 36, 44),
    ('XXL', 38, 46),
]


class DiscountType:
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'

    CHOICES = [
        (PERCENTAGE, 'Percentage (%)'),
        (FIXED, f'Fixed amount ({CURRENCY_SYMBOL})'),
    ]


class PaymentMethod:
    COD = 'cod'

    CHOICES = [
        (COD, 'Cash on Delivery'),
    ]


class PaymentStatus:
    UNPAID = 'unpaid'
    PAID = 'paid'
    REFUNDED = 'refunded'

    CHOICES = [
        (UNPAID, 'Unpaid'),
        (PAID, 'Paid'),
        (REFUNDED, 'Refunded'),
    ]


class OrderStatus:
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PROCESSING = 'processing'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    RETURNED = 'returned'

    CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (PROCESSING, 'Processing'),
        (SHIPPED, 'Shipped'),
        (DELIVERED, 'Delivered'),
        (CANCELLED, 'Cancelled'),
        (RETURNED, 'Returned'),
    ]
