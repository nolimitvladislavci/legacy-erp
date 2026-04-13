"""Tests for Gastro Menu module."""
from decimal import Decimal
from django.test import TestCase
from companies.models import Company
from gastro_menu.models import DigitalMenu, MenuCategory, MenuItem
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


class DigitalMenuTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Gastro Co", oib="14141414141")

    def test_menu_creation(self):
        menu = DigitalMenu.objects.create(
            company=self.company,
            name="Lunch Menu",
        )
        self.assertEqual(menu.name, "Lunch Menu")

    def test_category_and_item(self):
        menu = DigitalMenu.objects.create(
            company=self.company,
            name="Dinner",
        )
        cat = MenuCategory.objects.create(
            menu=menu,
            name="Predjela",
        )
        item = MenuItem.objects.create(
            category=cat,
            name="Bruschetta",
            price=Decimal("6.50"),
        )
        self.assertEqual(item.category, cat)
        self.assertEqual(cat.items.count(), 1)
        self.assertEqual(item.price, Decimal("6.50"))
