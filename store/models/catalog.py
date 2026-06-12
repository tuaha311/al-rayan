from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from .base import TimeStampedModel

ZERO = Decimal('0.00')


class Category(TimeStampedModel):
    """A self-nesting catalogue category.

    The tree lets the same structure cover today's men's cloth ("Men >
    Unstitched Suits") and tomorrow's expansion ("Women", "Bags", "Footwear")
    without schema changes.
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='children',
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'name'], name='uniq_category_name_per_parent',
            ),
        ]

    def __str__(self):
        return self.full_path

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_path(self):
        names = [self.name]
        node = self.parent
        # Guard against accidental cycles while walking to the root.
        seen = {self.pk}
        while node and node.pk not in seen:
            names.append(node.name)
            seen.add(node.pk)
            node = node.parent
        return ' › '.join(reversed(names))

    def get_ancestors(self, include_self=False):
        """Return ancestors from root down to (optionally) this node."""
        chain = [self] if include_self else []
        node = self.parent
        seen = {self.pk}
        while node and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        return list(reversed(chain))

    def self_and_ancestor_ids(self):
        return [c.pk for c in self.get_ancestors(include_self=True)]


class Fabric(TimeStampedModel):
    """Cloth material/quality — khadi, cotton, wash & wear, karandi, …"""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Season(TimeStampedModel):
    """Seasonal collection a product belongs to — summer, winter, all-season."""

    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Color(TimeStampedModel):
    """Reusable colour swatch shared across products."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    hex_code = models.CharField(
        max_length=7, blank=True,
        help_text='Optional hex like #1A2B3C, used to render a swatch.',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.active().filter(is_featured=True)


class Product(TimeStampedModel):
    """A saleable item.

    For unstitched cloth the price is quoted for a base length (``base_meters``)
    and a customer may buy extra running length at ``additional_meter_price``.
    Non-cloth future items (bags, footwear) simply set ``sold_by_meters=False``
    and are priced per unit.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField(max_length=40, unique=True)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products',
    )
    fabric = models.ForeignKey(
        Fabric, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products',
        help_text='Cloth material. Leave blank for non-cloth items.',
    )
    season = models.ForeignKey(
        Season, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products',
    )

    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)

    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)],
        help_text='Price for the base length / one unit, before any discount.',
    )

    # --- Unstitched-cloth length handling -------------------------------------
    sold_by_meters = models.BooleanField(
        default=True,
        help_text='Unstitched cloth sold by length. Disable for unit items.',
    )
    base_meters = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('3.50'),
        validators=[MinValueValidator(ZERO)],
        help_text='Length (in meters) included in the base price.',
    )
    additional_meter_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text='Price charged per extra meter beyond the base length.',
    )
    max_additional_meters = models.DecimalField(
        max_digits=5, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text='How many extra meters a customer may add (0 = none).',
    )

    # --- Inventory ------------------------------------------------------------
    track_inventory = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(
        default=0,
        help_text='Stock used when the product has no colour variants.',
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} ({self.sku})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        super().save(*args, **kwargs)

    # --- Pricing -------------------------------------------------------------
    def effective_discount(self, at=None):
        """Best live discount applicable to this product, or ``None``."""
        from .pricing import Discount
        return Discount.best_for(self, at=at)

    @property
    def discount_amount(self):
        discount = self.effective_discount()
        return discount.amount_for(self.base_price) if discount else ZERO

    @property
    def final_price(self):
        """Discounted base price (for ``base_meters`` / one unit)."""
        return (self.base_price - self.discount_amount).quantize(Decimal('0.01'))

    @property
    def is_on_sale(self):
        return self.discount_amount > ZERO

    @property
    def savings_percentage(self):
        if not self.is_on_sale or not self.base_price:
            return 0
        return int(round((self.discount_amount / self.base_price) * 100))

    def price_for(self, additional_meters=ZERO, variant=None):
        """Final unit price including a colour variant and extra length."""
        price = self.final_price
        if variant is not None:
            price += variant.price_delta
        extra = Decimal(additional_meters or 0)
        if self.sold_by_meters and extra > 0:
            price += extra * self.additional_meter_price
        return price.quantize(Decimal('0.01'))

    @property
    def total_stock(self):
        if self.pk and self.variants.exists():
            return sum(v.stock for v in self.variants.all())
        return self.stock

    @property
    def in_stock(self):
        if not self.track_inventory:
            return True
        return self.total_stock > 0

    @property
    def primary_image(self):
        img = self.images.filter(is_primary=True).first() or self.images.first()
        return img.image if img else None


class ProductVariant(TimeStampedModel):
    """A colour option of a product, with its own stock and price tweak."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants',
    )
    color = models.ForeignKey(
        Color, on_delete=models.PROTECT, related_name='variants',
    )
    sku = models.CharField(max_length=50, blank=True)
    price_delta = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO,
        help_text='Added to (or subtracted from) the base price for this colour.',
    )
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['color__name']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color'], name='uniq_variant_per_color',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.color.name}'

    @property
    def price(self):
        return self.product.price_for(variant=self)


def product_image_path(instance, filename):
    return f'products/{instance.product.slug or instance.product_id}/{filename}'


class ProductImage(TimeStampedModel):
    """An image for a product, optionally tied to a specific colour variant."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images',
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True,
        related_name='images',
        help_text='Tie this image to a colour, or leave blank for general shots.',
    )
    image = models.ImageField(upload_to=product_image_path)
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-is_primary', 'sort_order', 'id']

    def __str__(self):
        return self.alt_text or f'Image #{self.pk} for {self.product.name}'
