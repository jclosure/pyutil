import unittest

from pyutil.sql.interfaces.risk.currency import Currency
from pyutil.sql.interfaces.risk.owner import Owner


class TestCurrency(unittest.TestCase):
    def test_currency(self):
        o = Owner(name="Peter")
        currency = Currency(name="CHF")
        o.currency = currency
        self.assertEqual(o.currency, currency)
