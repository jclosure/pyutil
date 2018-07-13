import pandas as pd
from unittest import TestCase

import pandas.util.testing as pdt

from pyutil.influx.client import Client
from pyutil.performance.summary import fromNav
from pyutil.sql.base import Base
from pyutil.sql.interfaces.symbols.portfolio import Portfolio
from pyutil.sql.interfaces.symbols.symbol import Symbol, SymbolType
from pyutil.sql.session import postgresql_db_test
from test.config import test_portfolio

from pyutil.portfolio.portfolio import Portfolio as _Portfolio

t1 = pd.Timestamp("2010-04-24")
t2 = pd.Timestamp("2010-04-25")

class TestPortfolio(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Portfolio(name="Maffay")
        cls.client = Client(host='test-influxdb', database="test-portfolio")
        Portfolio.client = cls.client
        cls.p.upsert_influx(portfolio=test_portfolio())

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database(dbname="test-portfolio")

    def test_read_influx(self):
        p1 = self.p.portfolio_influx
        pdt.assert_frame_equal(p1.weights, test_portfolio().weights, check_names=False)
        pdt.assert_frame_equal(p1.prices, test_portfolio().prices, check_names=False)

    def test_symbols(self):
        symbols = self.p.symbols_influx
        self.assertSetEqual(set(symbols), set(test_portfolio().assets))

    def test_nav(self):
        pdt.assert_series_equal(self.p.nav, test_portfolio().nav, check_names=False)

    def test_leverage(self):
        pdt.assert_series_equal(self.p.leverage, test_portfolio().leverage, check_names=False)

    def test_upsert(self):
        p = 5*test_portfolio().tail(10)
        self.p.upsert_influx(p)

        x = self.p.portfolio_influx.weights.tail(12).sum(axis=1)
        self.assertAlmostEqual(x["2015-04-08"], 0.305048, places=5)
        self.assertAlmostEqual(x["2015-04-09"], 1.524054, places=5)

    def test_last(self):
        self.assertEqual(self.p.last(), pd.Timestamp("2015-04-22"))

    def test_series_portfolio(self):
        yyy = self.p.portfolio_influx
        pdt.assert_frame_equal(yyy.prices, test_portfolio().prices, check_names=False)
        pdt.assert_frame_equal(yyy.weights, test_portfolio().weights, check_names=False)


class TestPortfolios(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p1 = Portfolio(name="Maffay")
        cls.p2 = Portfolio(name="Falco")

        cls.client = Client(host='test-influxdb', database="test-portfolio3")
        Portfolio.client = cls.client

        cls.p1.upsert_influx(portfolio=test_portfolio())
        cls.p2.upsert_influx(portfolio=test_portfolio())

    @classmethod
    def tearDownClass(cls):
        cls.client.drop_database(dbname="test-portfolio3")

    def test_nav_all(self):
        x = Portfolio.nav_all()
        pdt.assert_series_equal(fromNav(x["Falco"]), test_portfolio().nav, check_names=False)

    def test_leverage_all(self):
        x = Portfolio.leverage_all()
        pdt.assert_series_equal(x["Falco"], test_portfolio().leverage, check_names=False)


class TestPortfolioSymbols(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = postgresql_db_test(base=Base, echo=True)
        cls.s1 = Symbol(name="A1", group=SymbolType.equities, internal="A1i")
        cls.s2 = Symbol(name="A2", group=SymbolType.equities, internal="A2i")

        cls.session.add_all([cls.s1, cls.s2])
        cls.session.commit()
        cls.client = Client(host='test-influxdb', database="test-portfolio-symbol")
        Portfolio.client = cls.client

    def test_portfolio(self):
        p = Portfolio(name="Maffay")

        prices = pd.DataFrame(index=[t1, t2], columns=["A1", "A2"], data=[[1.1,1.2],[1.4,1.3]])
        weights = pd.DataFrame(index=[t1, t2], columns=["A1", "A2"], data=[[0.3, 0.7], [0.2, 0.8]])
        x = _Portfolio(prices=prices, weights=weights)

        p.upsert_influx(portfolio=x)
        xxx = p.symbols(session=self.session)
        print(xxx)

