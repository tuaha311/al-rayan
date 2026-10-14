"""Forms and widgets that keep the back office in plain language.

The shop owner edits stock per size as one labelled row of boxes, and picks
what kind of product something is from three plain choices instead of
juggling the ``sold_by_meters`` / ``sold_in_sizes`` switches.
"""

from django import forms
from django.utils.text import slugify

from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminRadioSelectWidget,
    UnfoldAdminTextareaWidget,
)

from .constants import SIZES
from .models import Order, Product


class SizeStockWidget(forms.MultiWidget):
    """Six small number boxes, each captioned with its size."""

    template_name = 'admin/store/widgets/size_stock.html'

    def __init__(self, attrs=None):
        box = {'style': 'width:3.25rem;padding-left:.5rem;padding-right:.25rem',
               'min': 0, 'placeholder': '–'}
        super().__init__(
            [UnfoldAdminIntegerFieldWidget(attrs=box) for _ in SIZES], attrs,
        )

    def decompress(self, value):
        value = value or {}
        return [value.get(size) for size in SIZES]

    def get_context(self, name, value, attrs):
        # Unfold binds every widget to Alpine with x-model; six boxes sharing
        # one model would copy each other's numbers.
        self.attrs = {k: v for k, v in self.attrs.items() if not k.startswith('x-')}
        attrs = {k: v for k, v in (attrs or {}).items() if not k.startswith('x-')}
        context = super().get_context(name, value, attrs)
        for size, sub in zip(SIZES, context['widget']['subwidgets']):
            sub['size'] = size
        return context


class SizeStockField(forms.MultiValueField):
    """Edits ``size_stock``. All blank keeps ``{}``, so every size shares the
    single stock figure; fill any box and the blanks count as 0."""

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.pop('encoder', None)
        kwargs.pop('decoder', None)
        super().__init__(
            [forms.IntegerField(min_value=0, required=False) for _ in SIZES],
            widget=SizeStockWidget, require_all_fields=False, **kwargs,
        )

    def compress(self, data_list):
        if not data_list or all(v is None for v in data_list):
            return {}
        return {size: v or 0 for size, v in zip(SIZES, data_list)}


TYPE_SIZED = 'sized'
TYPE_ONE_SIZE = 'one_size'
TYPE_CLOTH = 'cloth'
PRODUCT_TYPE_CHOICES = [
    (TYPE_SIZED, 'Stitched — sold in sizes XS to XXL'),
    (TYPE_ONE_SIZE, 'One size — shawls, dupattas, bags, shoes'),
    (TYPE_CLOTH, 'Unstitched cloth — sold by length in metres'),
]


def product_type_of(product):
    if product.sold_by_meters:
        return TYPE_CLOTH
    return TYPE_SIZED if product.sold_in_sizes else TYPE_ONE_SIZE


class ProductForm(forms.ModelForm):
    product_type = forms.ChoiceField(
        label='Kind of product', choices=PRODUCT_TYPE_CHOICES,
        widget=UnfoldAdminRadioSelectWidget,
        help_text='Decides whether shoppers pick a size, a length, or neither.',
    )
    size_stock = SizeStockField(
        label='Stock per size',
        help_text='How many of each size you have. Leave every box blank to '
                  'let all sizes share the "In stock" figure.',
    )

    class Meta:
        model = Product
        exclude = ('sold_by_meters', 'sold_in_sizes')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_type'].initial = (
            product_type_of(self.instance) if self.instance.pk else TYPE_SIZED
        )
        if 'sku' in self.fields:
            # Folded away under Advanced, so it must never block saving.
            self.fields['sku'].required = False
            self.fields['sku'].help_text += ' Left blank, one is made for you.'

    def clean_sku(self):
        sku = (self.cleaned_data.get('sku') or '').strip()
        if sku:
            return sku
        base = 'FF-' + (slugify(self.cleaned_data.get('name') or 'item')[:24].upper() or 'ITEM')
        sku, n = base, 2
        while Product.objects.filter(sku=sku).exclude(pk=self.instance.pk).exists():
            sku, n = f'{base}-{n}', n + 1
        return sku

    def save(self, commit=True):
        kind = self.cleaned_data['product_type']
        self.instance.sold_by_meters = kind == TYPE_CLOTH
        self.instance.sold_in_sizes = kind == TYPE_SIZED
        return super().save(commit)


class VariantForm(forms.ModelForm):
    size_stock = SizeStockField(label='Stock per size')


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'
        widgets = {
            'customer_note': UnfoldAdminTextareaWidget(attrs={'rows': 3}),
            'admin_note': UnfoldAdminTextareaWidget(attrs={'rows': 3}),
        }
