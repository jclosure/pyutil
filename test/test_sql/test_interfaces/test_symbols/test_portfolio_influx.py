import pandas as pd
from unittest import TestCase

import pandas.util.testing as pdt

from pyutil.influx.client import Client
from pyutil.performance.summary import fromNav
from pyutil.sql.interfaces.symbols.portfolio import Portfolio
from test.config import test_portfolio


class TestPortfolio(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Portfolio(name="Maffay")
        cls.client = Client(host='test-influxdb', database="test-portfolio")
        #cls.assertIsNone(cls, cls.p.last(client=cls.client))

        cls.p.upsert_influx(client=cls.client, portfolio=test_portfolio())

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database(dbname="test-portfolio")

    def test_read_influx(self):
        p1 = self.p.portfolio_influx(client=self.client)
        pdt.assert_frame_equal(p1.weights, test_portfolio().weights, check_names=False)
        pdt.assert_frame_equal(p1.prices, test_portfolio().prices, check_names=False)

    def test_symbols(self):
        symbols = self.p.symbols_influx(client=self.client)
        self.assertSetEqual(set(symbols), set(test_portfolio().assets))

    def test_nav(self):
        pdt.assert_series_equal(self.p.nav(self.client), test_portfolio().nav, check_names=False)

    def test_leverage(self):
        pdt.assert_series_equal(self.p.leverage(self.client), test_portfolio().leverage, check_names=False)

    def test_upsert(self):
        p = 5*test_portfolio().tail(10)
        self.p.upsert_influx(self.client, p)

        x = self.p.portfolio_influx(client=self.client).weights.tail(12).sum(axis=1)
        self.assertAlmostEqual(x["2015-04-08"], 0.305048, places=5)
        self.assertAlmostEqual(x["2015-04-09"], 1.524054, places=5)

    def test_last(self):
        self.assertEqual(self.p.last(self.client), pd.Timestamp("2015-04-22"))

    def test_series_portfolio(self):
        yyy = self.p.portfolio_influx(self.client)
        pdt.assert_frame_equal(yyy.prices, test_portfolio().prices, check_names=False)
        pdt.assert_frame_equal(yyy.weights, test_portfolio().weights, check_names=False)

class TestPortfolios(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p1 = Portfolio(name="Maffay")
        cls.p2 = Portfolio(name="Falco")

        cls.client = Client(host='test-influxdb', database="test-portfolio3")
        cls.p1.upsert_influx(client=cls.client, portfolio=test_portfolio())
        cls.p2.upsert_influx(client=cls.client, portfolio=test_portfolio())

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database(dbname="test-portfolio3")

    def test_nav_all(self):
        x = Portfolio.nav_all(self.client)
        pdt.assert_series_equal(fromNav(x["Falco"]), test_portfolio().nav, check_names=False)

    def test_leverage_all(self):
        x = Portfolio.leverage_all(self.client)
        pdt.assert_series_equal(x["Falco"], test_portfolio().leverage, check_names=False)