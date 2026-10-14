from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from . import constants
from .models import (
    Category,
    Color,
    Discount,
    Fabric,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    Season,
    ShippingRate,
    StoreSetting,
)

D = Decimal


class PricingTests(TestCase):
    def setUp(self):
        self.men = Category.objects.create(name='Men')
        self.suits = Category.objects.create(name='Unstitched Suits', parent=self.men)
        self.fabric = Fabric.objects.create(name='Karandi')
        self.season = Season.objects.create(name='Winter')
        self.color = Color.objects.create(name='Charcoal', hex_code='#36454F')
        self.product = Product.objects.create(
            name='Karandi Suit', sku='T-KAR-1', category=self.suits,
            fabric=self.fabric, season=self.season, base_price=D('4500.00'),
            sold_by_meters=True, base_meters=D('3.50'),
            additional_meter_price=D('1300.00'), max_additional_meters=D('2.00'),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, color=self.color, stock=10,
        )

    def test_no_discount_returns_base_price(self):
        self.assertEqual(self.product.final_price, D('4500.00'))
        self.assertFalse(self.product.is_on_sale)

    def test_meter_extension_adds_to_price(self):
        # No discount: 4500 base + 1 extra meter @1300 = 5800
        self.assertEqual(self.product.price_for(D('1'), self.variant), D('5800.00'))
        self.assertEqual(self.product.price_for(D('2'), self.variant), D('7100.00'))

    def test_percentage_discount_on_category_cascades(self):
        Discount.objects.create(
            name='Suit Sale', discount_type=constants.DiscountType.PERCENTAGE,
            value=D('10'),
        ).categories.set([self.suits])
        self.assertEqual(self.product.final_price, D('4050.00'))
        self.assertEqual(self.product.savings_percentage, 10)

    def test_category_discount_applies_via_ancestor(self):
        # Discount on the parent ("Men") should reach the product in a child cat.
        Discount.objects.create(
            name='Men Sale', discount_type=constants.DiscountType.PERCENTAGE,
            value=D('20'),
        ).categories.set([self.men])
        self.assertEqual(self.product.final_price, D('3600.00'))

    def test_best_discount_wins(self):
        # 10% (=450) vs fixed 500 → fixed should win.
        Discount.objects.create(
            name='Pct', discount_type=constants.DiscountType.PERCENTAGE, value=D('10'),
        ).categories.set([self.suits])
        Discount.objects.create(
            name='Fixed', discount_type=constants.DiscountType.FIXED, value=D('500'),
        ).products.set([self.product])
        self.assertEqual(self.product.discount_amount, D('500.00'))
        self.assertEqual(self.product.final_price, D('4000.00'))

    def test_fixed_discount_never_exceeds_price(self):
        cheap = Product.objects.create(
            name='Cheap', sku='T-CHEAP', category=self.suits, base_price=D('300.00'),
            sold_by_meters=False,
        )
        Discount.objects.create(
            name='Big', discount_type=constants.DiscountType.FIXED, value=D('999'),
        ).products.set([cheap])
        self.assertEqual(cheap.final_price, D('0.00'))

    def test_expired_discount_ignored(self):
        past = timezone.now() - timedelta(days=2)
        Discount.objects.create(
            name='Old', discount_type=constants.DiscountType.PERCENTAGE, value=D('50'),
            start_at=past - timedelta(days=5), end_at=past,
        ).categories.set([self.suits])
        self.assertFalse(self.product.is_on_sale)

    def test_discount_with_meters(self):
        Discount.objects.create(
            name='Sale', discount_type=constants.DiscountType.PERCENTAGE, value=D('10'),
        ).categories.set([self.suits])
        # discounted base 4050 + 1300 extra meter = 5350
        self.assertEqual(self.product.price_for(D('1'), self.variant), D('5350.00'))


class OrderTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Unstitched Suits')
        self.product = Product.objects.create(
            name='Cotton Suit', sku='T-COT', category=self.cat, base_price=D('2600.00'),
            sold_by_meters=True, base_meters=D('3.50'), additional_meter_price=D('800.00'),
        )
        self.color = Color.objects.create(name='White')
        self.variant = ProductVariant.objects.create(
            product=self.product, color=self.color, stock=20,
        )
        ShippingRate.objects.create(province=constants.PROVINCE_PUNJAB, rate=D('200.00'))
        s = StoreSetting.load()
        s.free_shipping_threshold = D('10000.00')
        s.default_shipping_fee = D('250.00')
        s.save()

    def _order(self):
        return Order.objects.create(
            full_name='Test User', phone='03001234567',
            address_line='Street 1', city='Lahore',
            province=constants.PROVINCE_PUNJAB,
        )

    def test_order_number_generated(self):
        order = self._order()
        self.assertTrue(order.order_number.startswith('AR-'))

    def test_totals_and_snapshot(self):
        order = self._order()
        item = OrderItem(order=order)
        item.populate_from(self.product, self.variant, D('1'), quantity=2)
        item.save()
        order.recalculate_totals()
        # unit = 2600 + 800 = 3400; line = 6800; subtotal 6800; ship 200 (under 10k)
        self.assertEqual(item.unit_price, D('3400.00'))
        self.assertEqual(order.subtotal, D('6800.00'))
        self.assertEqual(order.shipping_fee, D('200.00'))
        self.assertEqual(order.total, D('7000.00'))
        self.assertEqual(item.product_name, 'Cotton Suit')
        self.assertEqual(item.color_name, 'White')

    def test_free_shipping_threshold(self):
        order = self._order()
        item = OrderItem(order=order)
        item.populate_from(self.product, self.variant, D('0'), quantity=4)  # 10400
        item.save()
        order.recalculate_totals()
        self.assertEqual(order.shipping_fee, D('0.00'))

    def test_default_shipping_for_unmapped_province(self):
        order = Order.objects.create(
            full_name='X', phone='1', address_line='a', city='Quetta',
            province=constants.PROVINCE_BALOCHISTAN,
        )
        item = OrderItem(order=order)
        item.populate_from(self.product, self.variant, D('0'), quantity=1)
        item.save()
        order.recalculate_totals()
        self.assertEqual(order.shipping_fee, D('250.00'))  # falls back to default

    def test_mark_paid(self):
        order = self._order()
        self.assertFalse(order.is_paid)
        order.mark_paid()
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertIsNotNone(order.paid_at)

    def test_discount_total_recorded(self):
        Discount.objects.create(
            name='10off', discount_type=constants.DiscountType.PERCENTAGE, value=D('10'),
        ).categories.set([self.cat])
        order = self._order()
        item = OrderItem(order=order)
        item.populate_from(self.product, self.variant, D('0'), quantity=1)
        item.save()
        order.recalculate_totals()
        # original 2600, discounted 2340 → discount_total 260
        self.assertEqual(order.discount_total, D('260.00'))
        self.assertEqual(order.subtotal, D('2340.00'))


class StoreSettingTests(TestCase):
    def test_singleton(self):
        a = StoreSetting.load()
        a.store_name = 'One'
        a.save()
        b = StoreSetting.load()
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(StoreSetting.objects.count(), 1)


class SizeTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Formals')
        self.suit = Product.objects.create(
            name='Formal Suit', sku='T-SZ-1', category=self.cat,
            base_price=D('50000.00'), sold_by_meters=False, stock=5,
        )
        self.shawl = Product.objects.create(
            name='Shawl', sku='T-SZ-2', category=self.cat,
            base_price=D('20000.00'), sold_by_meters=False, sold_in_sizes=False, stock=5,
        )
        self.fabric = Product.objects.create(
            name='Printed Lawn', sku='T-SZ-3', category=self.cat,
            base_price=D('15000.00'), sold_by_meters=True, stock=5,
        )

    def _add(self, product, **extra):
        return self.client.post(reverse('store:cart_add'), {
            'product_id': product.id, 'quantity': 1, **extra,
        })

    def _cart(self):
        return self.client.session.get('cart', {})

    def test_uses_sizes(self):
        self.assertTrue(self.suit.uses_sizes)
        self.assertFalse(self.shawl.uses_sizes)
        self.assertFalse(self.fabric.uses_sizes)   # cloth by the metre never does

    def test_sized_product_requires_a_size(self):
        r = self._add(self.suit)
        self.assertRedirects(r, reverse('store:product_detail', args=[self.suit.slug]))
        self.assertEqual(self._cart(), {})
        self._add(self.suit, size='XXXL')
        self.assertEqual(self._cart(), {})

    def test_each_size_is_its_own_cart_line(self):
        self._add(self.suit, size='M')
        self._add(self.suit, size='M')
        self._add(self.suit, size='L')
        lines = sorted((row['size'], row['quantity']) for row in self._cart().values())
        self.assertEqual(lines, [('L', 1), ('M', 2)])

    def test_unsized_products_ignore_size(self):
        self._add(self.shawl)
        self._add(self.fabric, size='M')
        self.assertEqual([row['size'] for row in self._cart().values()], ['', ''])

    def test_checkout_records_size(self):
        self._add(self.suit, size='S')
        r = self.client.post(reverse('store:checkout'), {
            'full_name': 'Test Buyer', 'phone': '+92 300 0000000',
            'address_line': '1 Test Street', 'city': 'Lahore',
            'province': constants.PROVINCE_PUNJAB,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(OrderItem.objects.get().size, 'S')

    def test_checkout_blocks_sized_line_without_size(self):
        session = self.client.session
        session['cart'] = {f'{self.suit.id}:0:0.00': {
            'product_id': self.suit.id, 'variant_id': None,
            'additional_meters': '0.00', 'quantity': 1,
        }}
        session.save()
        r = self.client.get(reverse('store:checkout'))
        self.assertRedirects(r, reverse('store:cart'))

    def test_picker_and_guide_shown_only_for_sized_products(self):
        r = self.client.get(reverse('store:product_detail', args=[self.suit.slug]))
        self.assertContains(r, 'name="size"', count=len(constants.SIZES))
        self.assertContains(r, 'id="size-guide-dialog"')
        r = self.client.get(reverse('store:product_detail', args=[self.shawl.slug]))
        self.assertNotContains(r, 'name="size"')
        self.assertNotContains(r, 'id="size-guide-dialog"')

    def test_size_guide_page(self):
        r = self.client.get(reverse('store:size_guide'))
        self.assertContains(r, 'Size Guide')
        for size, bust, hip, length in constants.SHIRT_SIZE_CHART:
            self.assertContains(r, f'<th scope="row">{size}</th><td>{bust}″</td>')


class StockLimitTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Formals')
        self.red = Color.objects.create(name='Red', hex_code='#B3202A')
        self.suit = Product.objects.create(
            name='Formal Suit', sku='T-ST-1', category=self.cat,
            base_price=D('50000.00'), sold_by_meters=False,
        )
        self.variant = ProductVariant.objects.create(
            product=self.suit, color=self.red,
            size_stock={'XS': 0, 'S': 2, 'M': 4, 'L': 0, 'XL': 0, 'XXL': 0},
        )
        self.shawl = Product.objects.create(
            name='Shawl', sku='T-ST-2', category=self.cat, base_price=D('20000.00'),
            sold_by_meters=False, sold_in_sizes=False, stock=3,
        )

    def _add(self, product, variant=None, **extra):
        data = {'product_id': product.id, 'quantity': 1, **extra}
        if variant:
            data['variant_id'] = variant.id
        return self.client.post(reverse('store:cart_add'), data)

    def _quantities(self):
        return sorted((row.get('size', ''), row['quantity'])
                      for row in self.client.session.get('cart', {}).values())

    def _checkout(self):
        return self.client.post(reverse('store:checkout'), {
            'full_name': 'Test Buyer', 'phone': '+92 300 0000000',
            'address_line': '1 Test Street', 'city': 'Lahore',
            'province': constants.PROVINCE_PUNJAB,
        })

    def test_stock_is_the_total_of_its_sizes(self):
        self.assertEqual(self.variant.stock, 6)
        self.assertEqual(self.suit.stock_left(self.variant, 'M'), 4)
        self.assertEqual(self.suit.stock_left(self.variant, 'L'), 0)

    def test_unsplit_stock_is_shared_by_every_size(self):
        self.variant.size_stock = {}
        self.variant.stock = 3
        self.variant.save()
        self.assertEqual(self.suit.stock_left(self.variant, 'XL'), 3)
        self._add(self.suit, self.variant, size='M', quantity=2)
        self._add(self.suit, self.variant, size='L', quantity=5)
        self.assertEqual(self._quantities(), [('L', 1), ('M', 2)])

    def test_untracked_stock_has_no_limit(self):
        self.shawl.track_inventory = False
        self.shawl.save()
        self.assertIsNone(self.shawl.stock_left())
        self._add(self.shawl, quantity=50)
        self.assertEqual(self._quantities(), [('', 50)])

    def test_add_caps_quantity_at_stock_left_in_that_size(self):
        self._add(self.suit, self.variant, size='S', quantity=5)
        self.assertEqual(self._quantities(), [('S', 2)])
        self._add(self.suit, self.variant, size='S')   # nothing left to add
        self.assertEqual(self._quantities(), [('S', 2)])

    def test_sold_out_size_cannot_be_added(self):
        r = self._add(self.suit, self.variant, size='L')
        self.assertRedirects(r, reverse('store:product_detail', args=[self.suit.slug]))
        self.assertEqual(self._quantities(), [])

    def test_colour_is_required_when_the_product_has_colours(self):
        self._add(self.suit, size='M')
        self.assertEqual(self._quantities(), [])

    def test_update_caps_quantity(self):
        self._add(self.shawl)
        key = next(iter(self.client.session['cart']))
        self.client.post(reverse('store:cart_update'), {'key': key, 'quantity': 9})
        self.assertEqual(self._quantities(), [('', 3)])

    def test_checkout_takes_stock(self):
        self._add(self.suit, self.variant, size='M', quantity=3)
        self._add(self.shawl, quantity=2)
        self.assertEqual(self._checkout().status_code, 302)
        self.variant.refresh_from_db()
        self.shawl.refresh_from_db()
        self.assertEqual(self.variant.size_stock['M'], 1)
        self.assertEqual(self.variant.stock, 3)
        self.assertEqual(self.shawl.stock, 1)

    def test_checkout_blocked_when_stock_ran_out(self):
        self._add(self.suit, self.variant, size='M', quantity=3)
        self.variant.size_stock['M'] = 1     # someone else bought them
        self.variant.save()
        r = self._checkout()
        self.assertRedirects(r, reverse('store:cart'))
        self.assertFalse(Order.objects.exists())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.size_stock['M'], 1)

    def test_take_stock_rolls_back_whole_order(self):
        from django.db import transaction
        from .models import OutOfStock
        with self.assertRaises(OutOfStock):
            with transaction.atomic():
                self.shawl.take_stock(None, '', 2)
                self.suit.take_stock(self.variant, 'S', 3)
        self.shawl.refresh_from_db()
        self.assertEqual(self.shawl.stock, 3)

    def test_product_page_marks_sold_out_sizes(self):
        r = self.client.get(reverse('store:product_detail', args=[self.suit.slug]))
        self.assertContains(r, 'value="L" required disabled')
        self.assertContains(r, 'value="M" required/>')
        r = self.client.get(reverse('store:product_detail', args=[self.shawl.slug]))
        self.assertContains(r, 'Only 3 left')
        self.assertContains(r, 'data-max="3"')
