from unittest import TestCase

import pandas as pd
import pandas.util.testing as pdt

from pyutil.mongo.assets import frame2assets
from pyutil.mongo.mongoArchive import MongoArchive
from test.config import read_frame, test_portfolio


prices = read_frame("price.csv", parse_dates=True)
symbols = read_frame("symbols.csv")

class TestMongoArchive(TestCase):
    @classmethod
    def setUp(self):
        self.archive = MongoArchive()

        assets = frame2assets(prices, symbols)
        for name, asset in assets.items():
            self.archive.update_asset(asset)
        p = test_portfolio(group="test", comment="test", time=pd.Timestamp("1980-01-01"))
        self.archive.portfolios.update("test", p)

    def test_history(self):
        pdt.assert_frame_equal(self.archive.assets().frame(), prices)
        pdt.assert_frame_equal(self.archive.assets(names=["A", "B"]).frame(), prices[["A","B"]])

    def test_symbols(self):
        pdt.assert_frame_equal(self.archive.assets().reference.sort_index(axis=1), symbols.sort_index(axis=1), check_dtype=False)

    def test_asset(self):
        a = self.archive.assets(names=["A"])
        self.assertEquals(a["A"].reference["internal"], "Gold")

    def test_get(self):
        p = self.archive.portfolios["test"]
        self.assertDictEqual(p.meta, {'comment': 'test', 'time': pd.Timestamp("01-01-1980"), 'group': 'test'})

    def test_porfolio_none(self):
        p = self.archive.portfolios["abc"]
        assert not p

    def test_update(self):
        portfolio = test_portfolio()
        self.archive.portfolios.update(key="test", portfolio=portfolio.tail(10))

        g = self.archive.portfolios["test"]
        pdt.assert_frame_equal(portfolio.prices, g.prices)
        pdt.assert_frame_equal(portfolio.weights, g.weights)