from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    """Customer + delivery details for a Cash-on-Delivery order."""

    class Meta:
        model = Order
        fields = [
            'full_name', 'phone', 'email',
            'address_line', 'city', 'province', 'postal_code',
            'customer_note',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g. Ahmed Raza'}),
            'phone': forms.TextInput(attrs={'placeholder': '+92 3XX XXXXXXX'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com (optional)'}),
            'address_line': forms.TextInput(
                attrs={'placeholder': 'House / street / area'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. Lahore'}),
            'postal_code': forms.TextInput(attrs={'placeholder': 'Optional'}),
            'customer_note': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Any delivery instructions (optional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tag every field with a shared class so store.css can style them.
        for name, field in self.fields.items():
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (css + ' field-input').strip()
        self.fields['email'].required = False
        self.fields['postal_code'].required = False
        self.fields['customer_note'].required = False
