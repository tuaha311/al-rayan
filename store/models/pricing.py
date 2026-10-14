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
        'internal code', max_length=30, blank=True,
        help_text='Optional, for your own records. Shoppers never type it.',
    )
    discount_type = models.CharField(
        'take off', max_length=12, choices=constants.DiscountType.CHOICES,
        default=constants.DiscountType.PERCENTAGE,
    )
    value = models.DecimalField(
        'amount', max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)],
        help_text='e.g. 15 for 15% off, or 2000 for Rs 2,000 off.',
    )

    products = models.ManyToManyField(
        Product, blank=True, related_name='direct_discounts',
        help_text='Type to search by name or code.',
    )
    categories = models.ManyToManyField(
        Category, blank=True, related_name='discounts',
        help_text='Every product in these categories (and the ones inside '
                  'them) goes on sale.',
    )

    start_at = models.DateTimeField(
        'starts', null=True, blank=True,
        help_text='Leave blank to start straight away.',
    )
    end_at = models.DateTimeField(
        'ends', null=True, blank=True,
        help_text='Leave blank to run until you switch it off.',
    )
    is_active = models.BooleanField('switched on', default=True)
    priority = models.IntegerField(
        default=0, help_text='Only matters when two sales give the same '
                             'saving on a product: the higher number is shown.',
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
        'delivery charge', max_digits=8, decimal_places=2,
        validators=[MinValueValidator(ZERO)],
    )
    is_active = models.BooleanField(
        'in use', default=True,
        help_text='When off, the default delivery charge from Store settings '
                  'applies.',
    )

    class Meta:
        verbose_name = 'delivery charge'
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

    store_name = models.CharField(max_length=120, default='Floral Finesse')
    currency_code = models.CharField(max_length=8, default=constants.CURRENCY_CODE)
    default_shipping_fee = models.DecimalField(
        'default delivery charge', max_digits=8, decimal_places=2,
        default=Decimal('200.00'),
        help_text='Used for any province without its own delivery charge.',
    )
    free_shipping_threshold = models.DecimalField(
        'free delivery from', max_digits=10, decimal_places=2, default=ZERO,
        help_text='Orders worth this much or more get free delivery (0 = never).',
    )
    cod_enabled = models.BooleanField('cash on delivery', default=True)
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
