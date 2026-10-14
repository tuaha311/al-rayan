from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
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
        related_name='children', verbose_name='inside category',
        help_text='Leave blank for a main category.',
    )
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='categories/', blank=True, null=True,
        help_text='Banner for the menu. Leave blank to use a product photo.',
    )
    is_active = models.BooleanField('show on website', default=True)
    sort_order = models.PositiveIntegerField('position', default=0)

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

    def descendant_and_self_ids(self):
        """All category ids at/under this node (breadth-first over children)."""
        ids = [self.pk]
        frontier = [self.pk]
        seen = {self.pk}
        while frontier:
            children = Category.objects.filter(
                parent_id__in=frontier).values_list('pk', flat=True)
            frontier = [c for c in children if c not in seen]
            seen.update(frontier)
            ids.extend(frontier)
        return ids


class Fabric(TimeStampedModel):
    """Cloth material/quality — khadi, cotton, wash & wear, karandi, …"""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField('show on website', default=True)
    sort_order = models.PositiveIntegerField('position', default=0)

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
    is_active = models.BooleanField('show on website', default=True)
    sort_order = models.PositiveIntegerField('position', default=0)

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
        'swatch colour', max_length=7, blank=True,
        help_text='The dot shoppers click to pick this colour.',
    )

    class Meta:
        verbose_name = 'colour'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class OutOfStock(Exception):
    """Raised when an order asks for more units than are left."""

    def __init__(self, product, left):
        super().__init__(f'Only {left} of {product.name} left')
        self.product = product
        self.left = left


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
    slug = models.SlugField(
        'web address', max_length=220, unique=True, blank=True,
        help_text='The end of the product page link. Changing it breaks old '
                  'links that were shared.',
    )
    sku = models.CharField(
        'product code', max_length=40, unique=True,
        help_text='Your own code for this design, e.g. FF-BR-007. Must be unique.',
    )

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

    short_description = models.CharField(
        'one-line summary', max_length=300, blank=True,
        help_text='Shown under the name in the shop.',
    )
    description = models.TextField(blank=True)

    base_price = models.DecimalField(
        'price', max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)],
        help_text='Full price in rupees, before any sale. Sales are set under '
                  'Discounts.',
    )

    # --- Unstitched-cloth length handling -------------------------------------
    sold_by_meters = models.BooleanField(
        default=True,
        help_text='Unstitched cloth sold by length. Disable for unit items.',
    )
    base_meters = models.DecimalField(
        'metres included', max_digits=5, decimal_places=2, default=Decimal('3.50'),
        validators=[MinValueValidator(ZERO)],
        help_text='Length of cloth the price above buys.',
    )
    additional_meter_price = models.DecimalField(
        'price per extra metre', max_digits=10, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text='Charged for each metre a customer adds.',
    )
    max_additional_meters = models.DecimalField(
        'most extra metres', max_digits=5, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text='How many extra metres a customer may add (0 = none).',
    )

    # --- Garment size ---------------------------------------------------------
    sold_in_sizes = models.BooleanField(
        default=True,
        help_text='Stitched piece sold in standard sizes (XS–XXL): shows the '
                  'size picker and size guide. Turn off for shawls and other '
                  'one-size items. Ignored for cloth sold by meters.',
    )

    # --- Inventory ------------------------------------------------------------
    track_inventory = models.BooleanField(
        'limit sales to stock', default=True,
        help_text='Turn off for made-to-order pieces that never run out.',
    )
    stock = models.PositiveIntegerField(
        'in stock', default=0,
        help_text='Pieces you have. Used when the product has no colours.',
    )
    size_stock = models.JSONField(
        'stock per size', default=dict, blank=True,
        help_text='Pieces of each size. Used when the product has no colours. '
                  'Leave all blank to let every size share the figure above.',
    )

    is_active = models.BooleanField(
        'show on website', default=True,
        help_text='Turn off to hide it from the shop without deleting it.',
    )
    is_featured = models.BooleanField(
        'feature on home page', default=False,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} ({self.sku})'

    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        if self.uses_sizes and self.size_stock:
            self.stock = sum(self.size_stock.values())
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
    def uses_sizes(self):
        """Whether a customer must pick a size (unstitched cloth never does)."""
        return self.sold_in_sizes and not self.sold_by_meters

    # --- Stock ---------------------------------------------------------------
    def splits_stock_by_size(self, variant=None):
        """Whether this colour (or the product, without colours) counts
        stock per size. Until per-size figures are entered, every size draws
        on the overall stock."""
        return self.uses_sizes and bool((variant or self).size_stock)

    def stock_left(self, variant=None, size=''):
        """Units still for sale in this colour / size; ``None`` if untracked."""
        if not self.track_inventory:
            return None
        holder = variant or self
        if size and self.splits_stock_by_size(variant):
            return holder.size_stock.get(size, 0)
        return holder.stock

    def take_stock(self, variant, size, quantity):
        """Remove sold units, locking the stock row. Call inside a
        transaction; raises ``OutOfStock`` if too few are left."""
        if not self.track_inventory:
            return
        model = ProductVariant if variant else Product
        holder = model.objects.select_for_update().get(pk=(variant or self).pk)
        split = size and self.uses_sizes and holder.size_stock
        left = holder.size_stock.get(size, 0) if split else holder.stock
        if quantity > left:
            raise OutOfStock(self, left)
        if split:
            holder.size_stock[size] = left - quantity
        holder.stock = max(holder.stock - quantity, 0)
        holder.save(update_fields=['stock', 'size_stock'])

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
        verbose_name='colour',
    )
    sku = models.CharField('code', max_length=50, blank=True)
    price_delta = models.DecimalField(
        'extra charge', max_digits=10, decimal_places=2, default=ZERO,
        help_text='Rupees added to the price for this colour (use a minus '
                  'sign to take off). Usually 0.',
    )
    stock = models.PositiveIntegerField('in stock', default=0)
    size_stock = models.JSONField(
        'stock per size', default=dict, blank=True,
        help_text='Pieces of this colour in each size. The total is added '
                  'up for you.',
    )
    is_active = models.BooleanField('available', default=True)

    class Meta:
        verbose_name = 'colour'
        verbose_name_plural = 'colours & stock'
        ordering = ['color__name']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color'], name='uniq_variant_per_color',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.color.name}'

    def save(self, *args, **kwargs):
        if self.size_stock and self.product.uses_sizes:
            self.stock = sum(self.size_stock.values())
        super().save(*args, **kwargs)

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
        related_name='images', verbose_name='colour',
        help_text='Pick a colour to show this photo when shoppers choose it.',
    )
    image = models.ImageField('photo', upload_to=product_image_path)
    alt_text = models.CharField(
        'caption', max_length=200, blank=True,
        help_text='Read aloud to blind shoppers and used by Google. Filled in '
                  'for you if left blank.',
    )
    is_primary = models.BooleanField('main photo', default=False)
    sort_order = models.PositiveIntegerField('position', default=0)

    class Meta:
        verbose_name = 'photo'
        ordering = ['-is_primary', 'sort_order', 'id']

    def __str__(self):
        return self.alt_text or f'Image #{self.pk} for {self.product.name}'
