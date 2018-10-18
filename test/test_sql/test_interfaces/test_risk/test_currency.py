import unittest

from pyutil.sql.interfaces.risk.currency import Currency
from pyutil.sql.interfaces.risk.owner import Owner


class TestCurrency(unittest.TestCase):
    def test_currency(self):
        o = Owner(name="Peter")
        o.currency = Currency(name="CHF")
        self.assertEqual(o.currency, Currency(name="CHF"))
