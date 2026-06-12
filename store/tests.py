from decimal import Decimal

from django.test import TestCase
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
