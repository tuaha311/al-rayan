from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .. import constants
from .base import TimeStampedModel
from .catalog import Category, Product

ZERO = Decimal('0.00')


class Discount(TimeStampedModel):
    """A sale that reduces price by a percentage or a fixed rupee amount.

    A discount may target individual products and/or whole categories (which
    cascades to every product in that category and its sub-categories). When
    several discounts apply to a product, the one giving the largest saving
    wins, breaking ties by ``priority``.
    """

    name = models.CharField(max_length=120)
    code = models.CharField(
        max_length=30, blank=True,
        help_text='Optional label/coupon code shown internally.',
    )
    discount_type = models.CharField(
        max_length=12, choices=constants.DiscountType.CHOICES,
        default=constants.DiscountType.PERCENTAGE,
    )
    value = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)],
        help_text='Percent (0–100) when type is percentage, else rupees off.',
    )

    products = models.ManyToManyField(
        Product, blank=True, related_name='direct_discounts',
    )
    categories = models.ManyToManyField(
        Category, blank=True, related_name='discounts',
        help_text='Applies to all products in these categories (and below).',
    )

    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0, help_text='Higher wins when two discounts save the same.',
    )

    class Meta:
        ordering = ['-priority', 'name']

    def __str__(self):
        if self.discount_type == constants.DiscountType.PERCENTAGE:
            label = f'{self.value:g}% off'
        else:
            label = f'{constants.CURRENCY_SYMBOL} {self.value:g} off'
        return f'{self.name} ({label})'

    def is_live(self, at=None):
        if not self.is_active:
            return False
        now = at or timezone.now()
        if self.start_at and self.start_at > now:
            return False
        if self.end_at and self.end_at < now:
            return False
        return True

    def amount_for(self, price):
        """Rupee saving this discount yields on ``price`` (never exceeds it)."""
        price = Decimal(price or 0)
        if price <= 0:
            return ZERO
        if self.discount_type == constants.DiscountType.PERCENTAGE:
            amount = price * (self.value / Decimal('100'))
        else:
            amount = self.value
        amount = min(amount, price)
        return amount.quantize(Decimal('0.01'))

    @classmethod
    def best_for(cls, product, at=None):
        now = at or timezone.now()
        live = (
            cls.objects.filter(is_active=True)
            .filter(models.Q(start_at__isnull=True) | models.Q(start_at__lte=now))
            .filter(models.Q(end_at__isnull=True) | models.Q(end_at__gte=now))
        )
        cat_ids = product.category.self_and_ancestor_ids()
        applicable = live.filter(
            models.Q(products=product) | models.Q(categories__in=cat_ids)
        ).distinct()

        best, best_amount = None, ZERO
        for discount in applicable:
            amount = discount.amount_for(product.base_price)
            if amount > best_amount or (
                amount == best_amount and best and discount.priority > best.priority
            ):
                best, best_amount = discount, amount
        return best


class ShippingRate(TimeStampedModel):
    """Flat delivery fee per province. Falls back to the store default."""

    province = models.CharField(
        max_length=20, choices=constants.PROVINCE_CHOICES, unique=True,
    )
    rate = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(ZERO)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['province']

    def __str__(self):
        return f'{self.get_province_display()} — {constants.CURRENCY_SYMBOL} {self.rate:g}'

    @classmethod
    def fee_for(cls, province, subtotal=ZERO):
        settings = StoreSetting.load()
        threshold = settings.free_shipping_threshold
        if threshold and subtotal >= threshold:
            return ZERO
        rate = (
            cls.objects.filter(province=province, is_active=True)
            .values_list('rate', flat=True)
            .first()
        )
        return rate if rate is not None else settings.default_shipping_fee


class StoreSetting(TimeStampedModel):
    """Singleton holding store-wide configuration."""

    store_name = models.CharField(max_length=120, default='Al Rayan')
    currency_code = models.CharField(max_length=8, default=constants.CURRENCY_CODE)
    default_shipping_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('200.00'),
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO,
        help_text='Order subtotal at/above which shipping is free (0 = never).',
    )
    cod_enabled = models.BooleanField(default=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)

    class Meta:
        verbose_name = 'Store setting'
        verbose_name_plural = 'Store settings'

    def __str__(self):
        return self.store_name

    def save(self, *args, **kwargs):
        # Enforce a single row.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
