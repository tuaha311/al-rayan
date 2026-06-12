from decimal import Decimal

from django.conf import settings as django_settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from .. import constants
from .base import TimeStampedModel
from .catalog import Product, ProductVariant
from .pricing import ShippingRate, StoreSetting

ZERO = Decimal('0.00')


class Cart(TimeStampedModel):
    """A working basket tied to a logged-in user or an anonymous session."""

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name='carts',
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        who = self.user or self.session_key or 'anonymous'
        return f'Cart #{self.pk} ({who})'

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), ZERO)

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
    )
    additional_meters = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.quantity} × {self.product.name}'

    @property
    def unit_price(self):
        return self.product.price_for(self.additional_meters, self.variant)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Order(TimeStampedModel):
    """A placed order. Cash-on-delivery for now; admins can mark it paid."""

    order_number = models.CharField(max_length=24, unique=True, blank=True)
    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders',
    )

    # --- Customer & delivery -------------------------------------------------
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    province = models.CharField(max_length=20, choices=constants.PROVINCE_CHOICES)
    postal_code = models.CharField(max_length=12, blank=True)

    # --- Status & payment ----------------------------------------------------
    status = models.CharField(
        max_length=12, choices=constants.OrderStatus.CHOICES,
        default=constants.OrderStatus.PENDING, db_index=True,
    )
    payment_method = models.CharField(
        max_length=12, choices=constants.PaymentMethod.CHOICES,
        default=constants.PaymentMethod.COD,
    )
    payment_status = models.CharField(
        max_length=12, choices=constants.PaymentStatus.CHOICES,
        default=constants.PaymentStatus.UNPAID, db_index=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    # --- Money (snapshotted at checkout) -------------------------------------
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)

    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number or f'Order #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        stamp = timezone.now().strftime('%Y%m%d')
        for _ in range(10):
            candidate = f'AR-{stamp}-{get_random_string(5, "0123456789")}'
            if not Order.objects.filter(order_number=candidate).exists():
                return candidate
        return f'AR-{stamp}-{get_random_string(8, "0123456789")}'

    def recalculate_totals(self, save=True, recompute_shipping=True):
        items = list(self.items.all())
        self.subtotal = sum((i.line_total for i in items), ZERO)
        self.discount_total = sum(
            ((i.unit_original_price - i.unit_price) * i.quantity for i in items),
            ZERO,
        )
        if recompute_shipping:
            self.shipping_fee = ShippingRate.fee_for(self.province, self.subtotal)
        self.total = self.subtotal + self.shipping_fee
        if save:
            super().save(update_fields=[
                'subtotal', 'discount_total', 'shipping_fee', 'total', 'updated_at',
            ])

    def mark_paid(self, save=True):
        self.payment_status = constants.PaymentStatus.PAID
        self.paid_at = timezone.now()
        if save:
            super().save(update_fields=['payment_status', 'paid_at', 'updated_at'])

    @property
    def is_paid(self):
        return self.payment_status == constants.PaymentStatus.PAID

    @property
    def total_items(self):
        return sum(i.quantity for i in self.items.all())


class OrderItem(TimeStampedModel):
    """A line on an order. Product details are snapshotted so historical
    orders stay correct even if the catalogue later changes."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name='order_items',
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
    )

    # Snapshots
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    color_name = models.CharField(max_length=60, blank=True)
    base_meters = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    additional_meters = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)

    unit_original_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO,
        help_text='Unit price before discount (incl. variant & extra length).',
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO,
        help_text='Unit price actually charged, after discount.',
    )
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)

    def __str__(self):
        return f'{self.quantity} × {self.product_name}'

    def populate_from(self, product, variant=None, additional_meters=ZERO, quantity=1):
        """Fill snapshot fields and pricing from a live product."""
        extra = Decimal(additional_meters or 0)
        self.product = product
        self.variant = variant
        self.product_name = product.name
        self.sku = (variant.sku if variant and variant.sku else product.sku)
        self.color_name = variant.color.name if variant else ''
        self.base_meters = product.base_meters if product.sold_by_meters else ZERO
        self.additional_meters = extra if product.sold_by_meters else ZERO

        original_unit = product.base_price
        if variant:
            original_unit += variant.price_delta
        if product.sold_by_meters and extra > 0:
            original_unit += extra * product.additional_meter_price

        self.unit_original_price = original_unit.quantize(Decimal('0.01'))
        self.unit_price = product.price_for(extra, variant)
        self.quantity = quantity
        self.line_total = self.unit_price * quantity
        return self

    def save(self, *args, **kwargs):
        if not self.line_total:
            self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)
