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
ANDROID_APK_PATH = 'app/al-rayan.apk'  # relative to static/
# User-Agent marker the WebView app appends; see mobile/.../MainActivity.kt.
ANDROID_APP_UA_MARKER = 'AlRayanApp'

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
