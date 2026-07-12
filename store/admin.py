from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils.html import format_html

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import (
    ChoicesDropdownFilter,
    RangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import display

from . import constants
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

admin.site.site_header = 'Al Rayan — Store Admin'
admin.site.site_title = 'Al Rayan Admin'
admin.site.index_title = 'Store management'

CURRENCY = constants.CURRENCY_SYMBOL


def money(value):
    if value is None:
        return '—'
    return f'{CURRENCY} {value:,.0f}'


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('full_path', 'parent', 'product_count', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('parent',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_pc=Count('products'))

    @admin.display(description='Products', ordering='_pc')
    def product_count(self, obj):
        return obj._pc


@admin.register(Fabric)
class FabricAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Season)
class SeasonAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Color)
class ColorAdmin(ModelAdmin):
    list_display = ('swatch', 'name', 'hex_code')
    search_fields = ('name', 'hex_code')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='')
    def swatch(self, obj):
        if not obj.hex_code:
            return '—'
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;border:1px '
            'solid #ccc;border-radius:3px;background:{}"></span>', obj.hex_code,
        )


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ('preview', 'image', 'variant', 'alt_text', 'is_primary', 'sort_order')
    readonly_fields = ('preview',)

    @admin.display(description='Preview')
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px"/>', obj.image.url,
            )
        return '—'


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    autocomplete_fields = ('color',)
    fields = ('color', 'sku', 'price_delta', 'stock', 'is_active')


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    """Registered mainly so order/cart admins can autocomplete variants."""

    list_display = ('product', 'color', 'sku', 'price_delta', 'stock', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('product__name', 'product__sku', 'color__name', 'sku')
    autocomplete_fields = ('product', 'color')


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = (
        'name', 'sku', 'category', 'fabric', 'season',
        'price_column', 'stock_column', 'is_active', 'is_featured',
    )
    list_filter = (
        'is_active', 'is_featured', 'sold_by_meters',
        ('category', RelatedDropdownFilter),
        ('fabric', RelatedDropdownFilter),
        ('season', RelatedDropdownFilter),
    )
    list_filter_submit = True
    list_editable = ('is_active', 'is_featured')
    search_fields = ('name', 'sku', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('category', 'fabric', 'season')
    inlines = (ProductVariantInline, ProductImageInline)
    actions = ('activate', 'deactivate', 'feature', 'unfeature')
    list_select_related = ('category', 'fabric', 'season')
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'sku', ('category', 'fabric', 'season')),
        }),
        ('Description', {
            'fields': ('short_description', 'description'),
        }),
        ('Pricing', {
            'fields': ('base_price',),
        }),
        ('Unstitched cloth — length', {
            'fields': (
                'sold_by_meters', 'base_meters',
                'additional_meter_price', 'max_additional_meters',
            ),
            'description': 'For non-cloth items (bags, footwear) turn off '
                           '“sold by meters” and price per unit.',
        }),
        ('Inventory & visibility', {
            'fields': ('track_inventory', 'stock', 'is_active', 'is_featured'),
        }),
    )

    @admin.display(description='Price')
    def price_column(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration:line-through;color:#999">{}</span>'
                '&nbsp;<b style="color:#138000">{}</b>&nbsp;'
                '<small style="color:#c0392b">(-{}%)</small>',
                money(obj.base_price), money(obj.final_price), obj.savings_percentage,
            )
        return money(obj.base_price)

    @admin.display(description='Stock')
    def stock_column(self, obj):
        if not obj.track_inventory:
            return '∞'
        total = obj.total_stock
        color = '#c0392b' if total == 0 else ('#e67e22' if total < 5 else '#138000')
        return format_html('<b style="color:{}">{}</b>', color, total)

    @admin.action(description='Activate selected products')
    def activate(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} product(s) activated.')

    @admin.action(description='Deactivate selected products')
    def deactivate(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f'{n} product(s) deactivated.')

    @admin.action(description='Mark as featured')
    def feature(self, request, queryset):
        n = queryset.update(is_featured=True)
        self.message_user(request, f'{n} product(s) featured.')

    @admin.action(description='Remove from featured')
    def unfeature(self, request, queryset):
        n = queryset.update(is_featured=False)
        self.message_user(request, f'{n} product(s) unfeatured.')


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
@admin.register(Discount)
class DiscountAdmin(ModelAdmin):
    list_display = ('name', 'value_display', 'live_badge', 'priority', 'start_at', 'end_at')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('name', 'code')
    filter_horizontal = ('products', 'categories')
    fieldsets = (
        (None, {'fields': ('name', 'code', ('discount_type', 'value'), 'priority')}),
        ('Applies to', {
            'fields': ('categories', 'products'),
            'description': 'Target whole categories and/or specific products. '
                           'A category target cascades to its sub-categories.',
        }),
        ('Schedule', {'fields': ('is_active', ('start_at', 'end_at'))}),
    )

    @admin.display(description='Discount')
    def value_display(self, obj):
        if obj.discount_type == constants.DiscountType.PERCENTAGE:
            return f'{obj.value:g}%'
        return money(obj.value)

    @display(description='Status', label={'Live': 'success', 'Inactive': 'warning'})
    def live_badge(self, obj):
        return 'Live' if obj.is_live() else 'Inactive'


@admin.register(ShippingRate)
class ShippingRateAdmin(ModelAdmin):
    list_display = ('get_province_display', 'rate', 'is_active')
    list_editable = ('rate', 'is_active')
    list_display_links = ('get_province_display',)


@admin.register(StoreSetting)
class StoreSettingAdmin(ModelAdmin):
    list_display = ('store_name', 'currency_code', 'default_shipping_fee',
                    'free_shipping_threshold', 'cod_enabled', 'contact_phone', 'contact_email')

    def has_add_permission(self, request):
        # Singleton — only ever one row.
        return not StoreSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product', 'variant')
    readonly_fields = ('unit_original_price', 'unit_price', 'line_total')
    fields = (
        'product', 'variant', 'color_name', 'additional_meters',
        'quantity', 'unit_original_price', 'unit_price', 'line_total',
    )


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        'order_number', 'full_name', 'phone', 'city', 'total_display',
        'status_badge', 'payment_badge', 'created_at',
    )
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('payment_status', ChoicesDropdownFilter),
        ('payment_method', ChoicesDropdownFilter),
        ('province', ChoicesDropdownFilter),
        ('created_at', RangeDateFilter),
    )
    list_filter_submit = True
    search_fields = ('order_number', 'full_name', 'phone', 'email')
    date_hierarchy = 'created_at'
    inlines = (OrderItemInline,)
    actions = ('mark_paid', 'mark_unpaid', 'mark_confirmed', 'mark_shipped', 'mark_delivered')
    readonly_fields = ('order_number', 'subtotal', 'discount_total', 'total',
                       'paid_at', 'created_at', 'updated_at')
    fieldsets = (
        ('Order', {
            'fields': ('order_number', ('status', 'created_at'), 'user'),
        }),
        ('Customer & delivery', {
            'fields': ('full_name', ('phone', 'email'), 'address_line',
                       ('city', 'province', 'postal_code')),
        }),
        ('Payment', {
            'fields': (('payment_method', 'payment_status'), 'paid_at'),
        }),
        ('Totals', {
            'fields': ('subtotal', 'discount_total', 'shipping_fee', 'total'),
            'description': 'Subtotal/discount/total recalculate from the line '
                           'items on save. Shipping fee is editable.',
        }),
        ('Notes', {'fields': ('customer_note', 'admin_note')}),
    )

    @display(description='Total', ordering='total')
    def total_display(self, obj):
        return money(obj.total)

    @display(description='Status', ordering='status', label={
        'Pending': 'warning',
        'Confirmed': 'info',
        'Processing': 'info',
        'Shipped': 'info',
        'Delivered': 'success',
        'Cancelled': 'danger',
        'Returned': 'danger',
    })
    def status_badge(self, obj):
        return obj.get_status_display()

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
                )
                item.save()
        order.recalculate_totals()

    @admin.action(description='Mark selected orders PAID')
    def mark_paid(self, request, queryset):
        count = 0
        for order in queryset:
            order.mark_paid()
            count += 1
        self.message_user(request, f'{count} order(s) marked paid.', messages.SUCCESS)

    @admin.action(description='Mark selected orders UNPAID')
    def mark_unpaid(self, request, queryset):
        n = queryset.update(payment_status=constants.PaymentStatus.UNPAID, paid_at=None)
        self.message_user(request, f'{n} order(s) marked unpaid.')

    @admin.action(description='Mark as Confirmed')
    def mark_confirmed(self, request, queryset):
        n = queryset.update(status=constants.OrderStatus.CONFIRMED)
        self.message_user(request, f'{n} order(s) confirmed.')

    @admin.action(description='Mark as Shipped')
    def mark_shipped(self, request, queryset):
        n = queryset.update(status=constants.OrderStatus.SHIPPED)
        self.message_user(request, f'{n} order(s) marked shipped.')

    @admin.action(description='Mark as Delivered')
    def mark_delivered(self, request, queryset):
        n = queryset.update(status=constants.OrderStatus.DELIVERED)
        self.message_user(request, f'{n} order(s) marked delivered.')


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ('product', 'variant')


@admin.register(Cart)
class CartAdmin(ModelAdmin):
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
