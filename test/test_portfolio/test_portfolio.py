import pandas as pd
import numpy as np
import pandas.util.testing as pdt
from nose.tools import raises
from pyutil.portfolio.portfolio import merge, Portfolio
from test.config import test_portfolio, read_frame
from unittest import TestCase

portfolio = test_portfolio()


class TestPortfolio(TestCase):
    def test_leverage(self):
        self.assertAlmostEqual(portfolio.leverage[pd.Timestamp("2013-07-19")], 0.25505730106555635, places=5)

    def test_nav(self):
        self.assertAlmostEqual(portfolio.nav.series[pd.Timestamp("2013-07-19")], 0.9849066065468487, places=5)

    def test_assets(self):
        self.assertSetEqual(set(portfolio.assets),
                            {'A', 'B', 'C', 'D', 'E', 'F', 'G'})

    def test_summary(self):
        # todo: include mtd, ytd
        self.assertAlmostEqual(portfolio.summary()[100]["Max Drawdown"], 1.7524809688827636, places=5)

    def test_index(self):
        pdt.assert_index_equal(portfolio.index, portfolio.prices.index)

    def test_asset_return(self):
        pdt.assert_frame_equal(portfolio.prices.pct_change(), portfolio.asset_returns)

    def test_truncate(self):
        self.assertEqual(portfolio.truncate(before=pd.Timestamp("2013-01-08")).index[0], pd.Timestamp("2013-01-08"))

    def test_top_flop(self):
        x = portfolio.top_flop(day_final=pd.Timestamp("2015-01-01"))
        self.assertAlmostEqual(x["Value"].values[16], 0.00025637273414469419, places=5)

    def test_tail(self):
        x = portfolio.tail(5)
        self.assertEqual(len(x.index), 5)
        self.assertEqual(x.index[0], pd.Timestamp("2015-04-16"))

    def test_snapshot(self):
        x = portfolio.snapshot()
        self.assertAlmostEqual(x["Apr 22"]["A"], 0.071761843963205701, places=10)

    def test_sector_weights(self):
        x = portfolio.sector_weights(pd.Series({"A": "A", "B": "A", "C": "B", "D": "B",
                                                "E": "C", "F": "C", "G": "C"}))

        pdt.assert_frame_equal(x.head(10), read_frame("sector_weights.csv", parse_dates=True))

    #def test_sector_weights_2(self):
    #    x = portfolio.sector_weights(pd.Series({"A": "A", "B": "A", "C": "B", "D": "B",
    #                                            "E": "C", "F": "C", "G": "C"}))
    #
    #    pdt.assert_frame_equal(x.head(10), read_frame("sector_weights.csv", parse_dates=True))


    def test_position(self):
        x = 1e6 * portfolio.position
        self.assertAlmostEqual(x["A"][pd.Timestamp("2015-04-22")], 60.191699988670969, places=5)

    def test_cash(self):
        self.assertAlmostEqual(portfolio.cash[pd.Timestamp("2015-04-22")], 0.69102612448658074, places=5)

    def test_build(self):
        prices = read_frame("price.csv")
        weights = pd.DataFrame(index=[prices.index[5]], data=0.1, columns=prices.keys())
        portfolio = Portfolio(prices, weights)

        self.assertEqual(portfolio.index[0], pd.Timestamp('2013-01-01'))
        self.assertAlmostEqual(portfolio.weights["B"][pd.Timestamp('2013-01-08')], 0.1, places=5)

    def test_build_portfolio(self):
        prices = pd.DataFrame(columns=["A", "B"], index=[1, 2, 3],
                              data=[[1000.0, 1000.0], [1500.0, 1500.0], [2000.0, 2000.0]])
        weights = pd.DataFrame(columns=["A", "B"], index=[1], data=[[0.25, 0.25]])

        portfolio = Portfolio(prices=prices, weights=weights)

        pdt.assert_frame_equal(prices, portfolio.prices)

        position = pd.DataFrame(columns=["A", "B"], index=[1, 2, 3], data=0.00025)
        pdt.assert_frame_equal(portfolio.position, position)

    def test_mul(self):
        pdt.assert_frame_equal(2 * portfolio.weights, (2 * portfolio).weights)

    def test_merge(self):
        # we merge two portfolios, in time-direction
        portfolios = [portfolio.truncate(after=pd.Timestamp("2015-01-01") - pd.DateOffset(days=1)),
                      portfolio.truncate(before=pd.Timestamp("2015-01-01")).apply(lambda x: 2 * x, axis=1)]
        p = merge(portfolios, axis=0)
        self.assertAlmostEqual(2 * portfolio.weight_current["D"], p.weight_current["D"], places=5)

    def test_plot(self):
        x = portfolio.plot()
        self.assertEqual(len(x), 4)

    def test_iron(self):
        x = test_portfolio()
        p1 = x.iron_threshold(threshold=0.05)
        p2 = x.iron_time(rule="3M")
        self.assertEqual(len(p1.trading_days), 40)
        self.assertEqual(len(p2.trading_days), 10)

    def test_transaction_report(self):
        x = test_portfolio()
        p1 = x.iron_threshold(threshold=0.05)
        y = p1.transaction_report()
        yy = read_frame("report.csv", index_col=[0, 1])
        yy.index.names = [None, None]
        pdt.assert_frame_equal(y, yy)

    def test_to_json(self):
        x = test_portfolio()
        a = x.to_json()
        self.assertAlmostEqual(a["price"]["A"]["20140909"], 1255.5, places=5)

    def test_init_1(self):
        prices = pd.DataFrame(columns=["A", "B"], index=[1, 2, 3], data=[[10.0, 10.0], [15.0, 15.0], [20.0, np.nan]])
        weights = pd.DataFrame(columns=["A", "B"], index=[2], data=[[0.3, 0.7]])

        portfolio = Portfolio(prices=prices, weights=weights)
        self.assertAlmostEqual(0.4 / 1.1, portfolio.weights["A"][3], places=5)

    @raises(AssertionError)
    def test_init_2(self):
        prices = pd.DataFrame(columns=["A", "B"], index=[1, 2, 3], data=[[10.0, 10.0], [15.0, 15.0], [20.0, np.nan]])
        weights = pd.DataFrame(columns=["A", "B"], index=[1.5], data=[[0.3, 0.7]])
        Portfolio(prices=prices, weights=weights)

    @raises(AssertionError)
    def test_init_3(self):
        prices = pd.DataFrame(columns=["A", "B"], index=[1, 2, 3], data=[[10.0, 10.0], [15.0, 15.0], [20.0, np.nan]])
        weights = pd.DataFrame(columns=["C"], index=[1.5], data=[[0.3]])
        Portfolio(prices=prices, weights=weights)

    def test_mtd(self):
        portfolio = test_portfolio()
        p = portfolio.mtd(today=portfolio.index[-1])
        self.assertEqual(p.index[0], pd.Timestamp("2015-04-01"))

    def test_ytd(self):
        portfolio = test_portfolio()
        p = portfolio.ytd(today=portfolio.index[-1])
        self.assertEqual(p.index[0], pd.Timestamp("2015-01-01"))
