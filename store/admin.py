"""The shop's back office.

Written for a shop owner rather than a developer: plain labels, one-click
buttons for each step of an order, stock shown in words, and the rarely
needed settings folded away instead of removed.
"""

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.core.files.storage import default_storage
from django.db.models import Case, Count, F, OuterRef, Subquery, Sum, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import (
    ChoicesDropdownFilter,
    RangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import action, display
from unfold.enums import ActionVariant
from unfold.widgets import UnfoldAdminColorInputWidget

from . import constants
from .admin_forms import OrderForm, ProductForm, VariantForm
from .constants import LOW_STOCK_THRESHOLD, OrderStatus, PaymentStatus
from .models import (
    Cart,
    CartItem,
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

admin.site.site_header = 'Floral Finesse — Store Admin'
admin.site.site_title = 'Floral Finesse Admin'
admin.site.index_title = 'Today'

CURRENCY = constants.CURRENCY_SYMBOL


def money(value):
    if value is None:
        return '—'
    return f'{CURRENCY} {value:,.0f}'


def badge(text, kind=''):
    """One of Unfold's coloured labels: success, warning, danger, info."""
    return mark_safe(render_to_string(
        'unfold/helpers/label.html', {'text': text, 'type': kind},
    ))


def photo_url(path):
    return default_storage.url(path) if path else ''


class FriendlyAdmin(ModelAdmin):
    """Warns before leaving a page with unsaved changes, and drops "Save and
    add another" where people only ever add one thing at a time."""

    warn_unsaved_form = True
    show_add_another = False

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = {
            'show_save_and_add_another': self.show_add_another,
            **(extra_context or {}),
        }
        return super().changeform_view(request, object_id, form_url, extra_context)


# -- Bulk actions shared by everything with a "show on website" switch -------
@admin.action(description='Show on website')
def show_on_site(modeladmin, request, queryset):
    n = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{n} now shown on the website.', messages.SUCCESS)


@admin.action(description='Hide from website')
def hide_from_site(modeladmin, request, queryset):
    n = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{n} hidden from the website.', messages.SUCCESS)


@display(description='On website', ordering='is_active',
         label={'Shown': 'success', 'Hidden': 'danger'})
def visible_badge(obj):
    return 'Shown' if obj.is_active else 'Hidden'


ADVANCED = {'classes': ('collapse',)}


# ---------------------------------------------------------------------------
# Catalogue lists: categories, fabrics, seasons, colours
# ---------------------------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(FriendlyAdmin):
    list_display = ('category_column', 'product_count', visible_badge)
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering_field = 'sort_order'
    hide_ordering_field = True
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('parent',)
    actions = (show_on_site, hide_from_site)
    fieldsets = (
        (None, {'fields': ('name', 'parent', 'description', 'image', 'is_active')}),
        ('Advanced', {**ADVANCED, 'fields': ('slug',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_pc=Count('products'))

    @display(description='Category', header=True, ordering='name')
    def category_column(self, obj):
        return [obj.name, f'inside {obj.parent.full_path}' if obj.parent else 'Main category']

    @display(description='Products', ordering='_pc')
    def product_count(self, obj):
        url = reverse('admin:store_product_changelist') + f'?category__id__exact={obj.pk}'
        return format_html('<a href="{}" class="text-primary-600">{} products</a>', url, obj._pc)


class SimpleListAdmin(FriendlyAdmin):
    """Fabrics and seasons: a name and a switch."""

    list_display = ('name', visible_badge)
    search_fields = ('name',)
    ordering_field = 'sort_order'
    hide_ordering_field = True
    show_add_another = True
    actions = (show_on_site, hide_from_site)
    fields = ('name', 'is_active')


@admin.register(Fabric)
class FabricAdmin(SimpleListAdmin):
    fields = ('name', 'description', 'is_active')


@admin.register(Season)
class SeasonAdmin(SimpleListAdmin):
    pass


@admin.register(Color)
class ColorAdmin(FriendlyAdmin):
    list_display = ('swatch', 'name', 'product_count')
    search_fields = ('name', 'hex_code')
    show_add_another = True
    fields = ('name', 'hex_code')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_pc=Count('variants'))

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'hex_code':
            kwargs['widget'] = UnfoldAdminColorInputWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description='')
    def swatch(self, obj):
        if not obj.hex_code:
            return '—'
        return format_html(
            '<span style="display:inline-block;width:22px;height:22px;border:1px '
            'solid #ccc;border-radius:50%;background:{}"></span>', obj.hex_code,
        )

    @admin.display(description='Used by', ordering='_pc')
    def product_count(self, obj):
        return f'{obj._pc} product(s)'


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ('preview', 'image', 'variant', 'is_primary', 'alt_text', 'sort_order')
    readonly_fields = ('preview',)
    ordering_field = 'sort_order'
    hide_ordering_field = True
    verbose_name_plural = 'Photos — drag to change the order'

    @admin.display(description='')
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:72px;width:56px;object-fit:cover;'
                'border-radius:6px"/>', obj.image.url,
            )
        return ''

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'variant':
            # Only this product's colours, named by colour alone.
            product_id = request.resolver_match.kwargs.get('object_id')
            field.queryset = (
                ProductVariant.objects.filter(product_id=product_id).select_related('color')
                if product_id else ProductVariant.objects.none()
            )
            field.label_from_instance = lambda v: v.color.name
            field.empty_label = 'Any colour'
            field.help_text = ''
        return field


class ProductVariantInline(TabularInline):
    model = ProductVariant
    form = VariantForm
    extra = 1
    autocomplete_fields = ('color',)
    fields = ('color', 'size_stock', 'stock', 'price_delta', 'is_active', 'sku')
    verbose_name_plural = 'Colours & stock'


def _photo_subquery():
    first = ProductImage.objects.filter(product=OuterRef('pk')).order_by(
        '-is_primary', 'sort_order', 'id',
    )
    return Subquery(first.values('image')[:1])


class StockFilter(admin.SimpleListFilter):
    title = 'stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return (
            ('out', 'Sold out'),
            ('low', f'Running low ({LOW_STOCK_THRESHOLD} or fewer)'),
            ('in', 'In stock'),
        )

    def queryset(self, request, queryset):
        tracked = queryset.filter(track_inventory=True)
        if self.value() == 'out':
            return tracked.filter(_total=0)
        if self.value() == 'low':
            return tracked.filter(_total__gt=0, _total__lte=LOW_STOCK_THRESHOLD)
        if self.value() == 'in':
            return queryset.exclude(track_inventory=True, _total=0)
        return queryset


class SaleFilter(admin.SimpleListFilter):
    title = 'sale'
    parameter_name = 'sale'

    def lookups(self, request, model_admin):
        return (('yes', 'On sale now'), ('no', 'Full price'))

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        on_sale = [p.pk for p in Product.objects.select_related('category') if p.is_on_sale]
        if self.value() == 'yes':
            return queryset.filter(pk__in=on_sale)
        return queryset.exclude(pk__in=on_sale)


def stock_words(total, tracked=True):
    if not tracked:
        return badge('Made to order')
    if total == 0:
        return badge('Sold out', 'danger')
    if total <= LOW_STOCK_THRESHOLD:
        return badge(f'Only {total} left', 'warning')
    return badge(f'{total} in stock', 'success')


@admin.register(Product)
class ProductAdmin(FriendlyAdmin):
    form = ProductForm
    list_display = ('product_column', 'category_column', 'price_column',
                    'stock_column', 'status_column')
    list_filter = (
        StockFilter, SaleFilter, 'is_active', 'is_featured',
        ('category', RelatedDropdownFilter),
        ('fabric', RelatedDropdownFilter),
        ('season', RelatedDropdownFilter),
    )
    list_filter_submit = True
    search_fields = ('name', 'sku', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('category', 'fabric', 'season')
    inlines = (ProductImageInline, ProductVariantInline)
    actions = (show_on_site, hide_from_site, 'feature', 'unfeature')
    list_select_related = ('category', 'category__parent')
    readonly_fields = ('stock_by_colour',)

    class Media:
        js = ('js/admin-product.js',)

    def get_fieldsets(self, request, obj=None):
        has_colours = obj is not None and obj.variants.exists()
        stock_fields = (
            ('track_inventory', 'stock_by_colour') if has_colours
            else ('track_inventory', 'stock', 'size_stock')
        )
        return (
            (None, {
                'fields': ('name', 'category', 'short_description', 'description'),
            }),
            ('Price & kind', {
                'fields': ('base_price', 'product_type', 'base_meters',
                           'additional_meter_price', 'max_additional_meters'),
            }),
            ('Stock', {
                'fields': stock_fields,
                'description': (
                    'Stock is kept per colour in "Colours & stock" further down.'
                    if has_colours else
                    'If you add colours further down, enter the stock on each '
                    'colour there instead.'
                ),
            }),
            ('On the website', {
                'fields': ('is_active', 'is_featured', 'fabric', 'season'),
                'description': 'Fabric and season are the shop\'s filters.',
            }),
            ('Advanced', {**ADVANCED, 'fields': ('sku', 'slug')}),
        )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .annotate(_vcount=Count('variants'),
                      _vstock=Coalesce(Sum('variants__stock'), 0))
            .annotate(_total=Case(When(_vcount__gt=0, then=F('_vstock')),
                                  default=F('stock')),
                      _photo=_photo_subquery())
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        product = form.instance
        images = list(product.images.select_related('variant__color'))
        # Exactly one main photo: the first ticked one, else the first photo.
        main = next((i for i in images if i.is_primary), images[0] if images else None)
        for image in images:
            fields = []
            if image.is_primary != (image is main):
                image.is_primary = image is main
                fields.append('is_primary')
            if not image.alt_text:
                colour = f' in {image.variant.color.name}' if image.variant else ''
                image.alt_text = f'{product.name}{colour}'[:200]
                fields.append('alt_text')
            if fields:
                image.save(update_fields=fields)

    @display(description='Product', header=True, ordering='name')
    def product_column(self, obj):
        photo = getattr(obj, '_photo', None)
        return [
            obj.name, obj.sku, obj.name[:1],
            {'path': photo_url(photo), 'squared': True, 'width': 40, 'height': 52}
            if photo else None,
        ]

    @admin.display(description='Category', ordering='category__name')
    def category_column(self, obj):
        return obj.category.name

    @admin.display(description='Price', ordering='base_price')
    def price_column(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration:line-through;color:#999">{}</span>'
                '&nbsp;<b style="color:#138000">{}</b>&nbsp;'
                '<small style="color:#c0392b">(-{}%)</small>',
                money(obj.base_price), money(obj.final_price), obj.savings_percentage,
            )
        return money(obj.base_price)

    @admin.display(description='Stock', ordering='_total')
    def stock_column(self, obj):
        return stock_words(obj._total, obj.track_inventory)

    @admin.display(description='Status')
    def status_column(self, obj):
        parts = [badge('Shown', 'success') if obj.is_active else badge('Hidden', 'danger')]
        if obj.is_featured:
            parts.append(badge('Featured', 'info'))
        return mark_safe(' '.join(parts))

    @admin.display(description='Stock')
    def stock_by_colour(self, obj):
        rows = [
            format_html('<li><b>{}</b>: {}</li>', v.color.name, stock_words(v.stock))
            for v in obj.variants.select_related('color')
        ]
        return format_html('<ul style="display:grid;gap:4px">{}</ul>', mark_safe(''.join(rows)))

    @admin.action(description='Feature on home page')
    def feature(self, request, queryset):
        n = queryset.update(is_featured=True)
        self.message_user(request, f'{n} product(s) now featured.', messages.SUCCESS)

    @admin.action(description='Remove from home page')
    def unfeature(self, request, queryset):
        n = queryset.update(is_featured=False)
        self.message_user(request, f'{n} product(s) no longer featured.', messages.SUCCESS)


@admin.register(ProductVariant)
class ProductVariantAdmin(FriendlyAdmin):
    """Every colour of every product in one list — handy for stock checks.
    Also lets order and cart screens search colours."""

    form = VariantForm
    list_display = ('product', 'color', 'stock_column', 'is_active')
    list_filter = ('is_active', ('color', RelatedDropdownFilter))
    search_fields = ('product__name', 'product__sku', 'color__name', 'sku')
    autocomplete_fields = ('product', 'color')
    list_select_related = ('product', 'color')
    fields = ('product', 'color', 'size_stock', 'stock', 'price_delta', 'is_active', 'sku')

    @admin.display(description='Stock', ordering='stock')
    def stock_column(self, obj):
        return stock_words(obj.stock, obj.product.track_inventory)


# ---------------------------------------------------------------------------
# Sales & delivery
# ---------------------------------------------------------------------------
@admin.register(Discount)
class DiscountAdmin(FriendlyAdmin):
    list_display = ('name', 'value_display', 'applies_to', 'live_badge', 'start_at', 'end_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    autocomplete_fields = ('categories', 'products')
    actions = ('switch_on', 'switch_off')
    fieldsets = (
        (None, {'fields': ('name', ('discount_type', 'value'))}),
        ('What goes on sale', {
            'fields': ('categories', 'products'),
            'description': 'Pick whole categories, single products, or both.',
        }),
        ('When', {'fields': ('is_active', 'start_at', 'end_at')}),
        ('Advanced', {**ADVANCED, 'fields': ('code', 'priority')}),
    )

    @admin.display(description='Discount')
    def value_display(self, obj):
        if obj.discount_type == constants.DiscountType.PERCENTAGE:
            return f'{obj.value:g}% off'
        return f'{money(obj.value)} off'

    @admin.display(description='On')
    def applies_to(self, obj):
        names = [c.name for c in obj.categories.all()] + [p.name for p in obj.products.all()]
        if not names:
            return 'Nothing chosen yet'
        more = f' + {len(names) - 3} more' if len(names) > 3 else ''
        return ', '.join(names[:3]) + more

    @display(description='Status', label={
        'Running': 'success', 'Scheduled': 'info', 'Ended': 'warning', 'Off': 'danger',
    })
    def live_badge(self, obj):
        if not obj.is_active:
            return 'Off'
        if obj.is_live():
            return 'Running'
        return 'Scheduled' if obj.start_at and obj.start_at > timezone.now() else 'Ended'

    @admin.action(description='Switch on')
    def switch_on(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} discount(s) switched on.', messages.SUCCESS)

    @admin.action(description='Switch off')
    def switch_off(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f'{n} discount(s) switched off.', messages.SUCCESS)


@admin.register(ShippingRate)
class ShippingRateAdmin(FriendlyAdmin):
    list_display = ('get_province_display', 'rate', 'is_active')
    list_editable = ('rate', 'is_active')
    list_display_links = ('get_province_display',)
    show_add_another = True


@admin.register(StoreSetting)
class StoreSettingAdmin(FriendlyAdmin):
    fieldsets = (
        ('Shop', {'fields': ('store_name', 'contact_phone', 'contact_email')}),
        ('Delivery & payment', {
            'fields': ('default_shipping_fee', 'free_shipping_threshold', 'cod_enabled'),
        }),
        ('Advanced', {**ADVANCED, 'fields': ('currency_code',)}),
    )

    def changelist_view(self, request, extra_context=None):
        # There is only ever one settings record: go straight to it.
        return redirect('admin:store_storesetting_change', StoreSetting.load().pk)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product', 'variant')
    readonly_fields = ('color_name', 'unit_price', 'line_total')
    fields = ('product', 'variant', 'color_name', 'size', 'additional_meters',
              'quantity', 'unit_price', 'line_total')
    verbose_name = 'item'
    verbose_name_plural = 'Items'


def whatsapp_number(phone):
    """03xx-xxxxxxx → 923xxxxxxxxx, the form wa.me links need."""
    digits = ''.join(ch for ch in phone or '' if ch.isdigit())
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = '92' + digits[1:]
    return digits


# Which one-click buttons an order shows, by its status.
NEXT_STEPS = {
    OrderStatus.PENDING: ('confirm', 'cancel'),
    OrderStatus.CONFIRMED: ('ship', 'cancel'),
    OrderStatus.PROCESSING: ('ship', 'cancel'),
    OrderStatus.SHIPPED: ('deliver', 'return'),
    OrderStatus.DELIVERED: ('return',),
}
CLOSED = (OrderStatus.CANCELLED, OrderStatus.RETURNED)

STATUS_LABELS = {
    'New': 'warning',
    'Confirmed': 'info',
    'Processing': 'info',
    'Shipped': 'info',
    'Delivered': 'success',
    'Cancelled': 'danger',
    'Returned': 'danger',
}


def status_text(order):
    return 'New' if order.status == OrderStatus.PENDING else order.get_status_display()


@admin.register(Order)
class OrderAdmin(FriendlyAdmin):
    form = OrderForm
    list_display = (
        'order_column', 'customer_column', 'items_column', 'total_display',
        'status_badge', 'payment_badge',
    )
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('payment_status', ChoicesDropdownFilter),
        ('province', ChoicesDropdownFilter),
        ('created_at', RangeDateFilter),
        ('payment_method', ChoicesDropdownFilter),
    )
    list_filter_submit = True
    search_fields = ('order_number', 'full_name', 'phone', 'email', 'city')
    inlines = (OrderItemInline,)
    actions = ('mark_paid', 'mark_unpaid', 'mark_confirmed', 'mark_shipped',
               'mark_delivered', 'mark_cancelled')
    actions_detail = ('confirm_order', 'ship_order', 'deliver_order', 'paid_order',
                      'cancel_order', 'return_order')
    readonly_fields = ('contact_links', 'order_number', 'subtotal',
                       'discount_total', 'total', 'paid_at', 'created_at')
    change_form_before_template = 'admin/store/order_summary_slot.html'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_items=Sum('items__quantity'))

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            # Taking an order by phone: customer first, items below.
            return (
                ('Customer & delivery', {'fields': (
                    'full_name', 'phone', 'email', 'address_line',
                    ('city', 'province', 'postal_code'), 'customer_note',
                )}),
                ('Status', {'fields': ('status', 'payment_status', 'payment_method')}),
                ('Private note', {'fields': ('admin_note',)}),
            )
        return (
            ('Status', {
                'fields': (('status', 'payment_status'),),
                'description': 'The buttons at the top move the order to its '
                               'next step. Change these by hand only to fix a '
                               'mistake.',
            }),
            ('Customer & delivery', {'fields': (
                'full_name', ('phone', 'contact_links'), 'email', 'address_line',
                ('city', 'province', 'postal_code'),
            )}),
            ('Private note', {'fields': ('admin_note',)}),
            ('More details', {**ADVANCED, 'fields': (
                'shipping_fee', 'payment_method', 'paid_at', 'customer_note',
                'created_at', 'user',
            ), 'description': 'Changing the delivery charge updates the total '
                              'when you save.'}),
        )

    def get_inline_instances(self, request, obj=None):
        inlines = super().get_inline_instances(request, obj)
        for inline in inlines:
            # Existing orders show their items in the summary at the top;
            # the editable list stays folded away for corrections.
            inline.classes = ('collapse',) if obj else ()
            inline.verbose_name_plural = 'Change items' if obj else 'Items'
        return inlines

    def change_view(self, request, object_id, form_url='', extra_context=None):
        order = Order.objects.filter(pk=object_id).first()
        if order:
            extra_context = {'order_summary': self.summary(order), **(extra_context or {})}
        return super().change_view(request, object_id, form_url, extra_context)

    # -- Read-only panels ----------------------------------------------------
    def summary(self, obj):
        items = list(obj.items.select_related('product'))
        for item in items:
            image = item.product.primary_image if item.product else None
            item.photo = image.url if image else ''
        return render_to_string('admin/store/order_summary.html', {
            'order': obj, 'items': items, 'status': status_text(obj),
            'status_kind': STATUS_LABELS.get(status_text(obj), ''),
        })

    @admin.display(description='Contact')
    def contact_links(self, obj):
        if not obj.phone:
            return '—'
        return format_html(
            '<a href="tel:{}" class="text-primary-600 font-semibold">Call</a>'
            ' &nbsp;·&nbsp; <a href="https://wa.me/{}" target="_blank" '
            'rel="noopener" class="text-primary-600 font-semibold">WhatsApp</a>',
            obj.phone, whatsapp_number(obj.phone),
        )

    # -- List columns --------------------------------------------------------
    @display(description='Order', header=True, ordering='created_at')
    def order_column(self, obj):
        return [obj.order_number, obj.created_at.strftime('%d %b %Y, %I:%M %p')]

    @display(description='Customer', header=True, ordering='full_name')
    def customer_column(self, obj):
        return [obj.full_name, f'{obj.phone} · {obj.city}']

    @admin.display(description='Items', ordering='_items')
    def items_column(self, obj):
        n = obj._items or 0
        return f'{n} piece{"s" if n != 1 else ""}'

    @display(description='Total', ordering='total')
    def total_display(self, obj):
        return money(obj.total)

    @display(description='Status', ordering='status', label=STATUS_LABELS)
    def status_badge(self, obj):
        return status_text(obj)

    @display(description='Payment', ordering='payment_status', label={
        'Paid': 'success',
        'Unpaid': 'danger',
        'Refunded': 'warning',
    })
    def payment_badge(self, obj):
        return obj.get_payment_status_display()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Re-snapshot any freshly-added line items from their live product,
        # then recompute order money. Keeps admin-entered orders consistent.
        order = form.instance
        for item in order.items.all():
            if item.product and not item.unit_price:
                item.populate_from(
                    item.product, item.variant, item.additional_meters, item.quantity,
                    size=item.size,
                )
                item.save()
        # A delivery charge typed in by hand stands; otherwise it follows the
        # province's rate when the order is new or its province changes.
        changed = form.changed_data
        order.recalculate_totals(recompute_shipping='shipping_fee' not in changed and (
            not change or 'province' in changed))

    # -- One-click buttons on an order --------------------------------------
    def get_actions_detail(self, request, object_id):
        buttons = super().get_actions_detail(request, object_id)
        order = Order.objects.filter(pk=object_id).first()
        if order is None:
            return buttons
        wanted = set(NEXT_STEPS.get(order.status, ()))
        if order.payment_status == PaymentStatus.UNPAID and order.status not in CLOSED:
            wanted.add('paid')
        return [b for b in buttons if b.path in wanted]

    def _step(self, request, object_id, message, **changes):
        order = get_object_or_404(Order, pk=object_id)
        if changes.pop('paid', False):
            order.mark_paid()
        if changes:
            for field, value in changes.items():
                setattr(order, field, value)
            order.save(update_fields=[*changes, 'updated_at'])
        self.message_user(request, f'{order.order_number}: {message}', messages.SUCCESS)
        return redirect('admin:store_order_change', order.pk)

    @action(description='Confirm order', url_path='confirm', icon='check_circle',
            variant=ActionVariant.PRIMARY)
    def confirm_order(self, request, object_id):
        return self._step(request, object_id, 'confirmed.', status=OrderStatus.CONFIRMED)

    @action(description='Mark as shipped', url_path='ship', icon='local_shipping',
            variant=ActionVariant.PRIMARY)
    def ship_order(self, request, object_id):
        return self._step(request, object_id, 'marked as shipped.', status=OrderStatus.SHIPPED)

    @action(description='Mark as delivered', url_path='deliver', icon='inventory',
            variant=ActionVariant.PRIMARY)
    def deliver_order(self, request, object_id):
        return self._step(request, object_id, 'marked as delivered.',
                          status=OrderStatus.DELIVERED)

    @action(description='Payment received', url_path='paid', icon='payments',
            variant=ActionVariant.SUCCESS)
    def paid_order(self, request, object_id):
        return self._step(request, object_id, 'payment received.', paid=True)

    @action(description='Cancel order', url_path='cancel', icon='cancel',
            variant=ActionVariant.DANGER)
    def cancel_order(self, request, object_id):
        return self._step(request, object_id, 'cancelled.', status=OrderStatus.CANCELLED)

    @action(description='Returned', url_path='return', icon='undo',
            variant=ActionVariant.WARNING)
    def return_order(self, request, object_id):
        return self._step(request, object_id, 'marked as returned.',
                          status=OrderStatus.RETURNED)

    # -- Bulk actions on the list -------------------------------------------
    @admin.action(description='Payment received')
    def mark_paid(self, request, queryset):
        count = 0
        for order in queryset:
            order.mark_paid()
            count += 1
        self.message_user(request, f'{count} order(s) marked paid.', messages.SUCCESS)

    @admin.action(description='Not paid yet')
    def mark_unpaid(self, request, queryset):
        n = queryset.update(payment_status=PaymentStatus.UNPAID, paid_at=None)
        self.message_user(request, f'{n} order(s) marked unpaid.')

    @admin.action(description='Confirm')
    def mark_confirmed(self, request, queryset):
        n = queryset.update(status=OrderStatus.CONFIRMED)
        self.message_user(request, f'{n} order(s) confirmed.')

    @admin.action(description='Mark as shipped')
    def mark_shipped(self, request, queryset):
        n = queryset.update(status=OrderStatus.SHIPPED)
        self.message_user(request, f'{n} order(s) marked shipped.')

    @admin.action(description='Mark as delivered')
    def mark_delivered(self, request, queryset):
        n = queryset.update(status=OrderStatus.DELIVERED)
        self.message_user(request, f'{n} order(s) marked delivered.')

    @admin.action(description='Cancel')
    def mark_cancelled(self, request, queryset):
        n = queryset.update(status=OrderStatus.CANCELLED)
        self.message_user(request, f'{n} order(s) cancelled.')


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ('product', 'variant')


@admin.register(Cart)
class CartAdmin(FriendlyAdmin):
    list_display = ('__str__', 'user', 'item_count', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('session_key', 'user__username')
    inlines = (CartItemInline,)


# ---------------------------------------------------------------------------
# Re-skin the built-in auth admin so Users/Groups match the Unfold theme.
# ---------------------------------------------------------------------------
User = get_user_model()
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    pass


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, ModelAdmin):
    pass
