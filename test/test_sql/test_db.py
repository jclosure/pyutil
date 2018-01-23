from unittest import TestCase

import pandas as pd
from pony import orm

from pyutil.sql.db import define_database, upsert_frame

from test.config import read_frame, TestEnv

import pandas.util.testing as pdt


class TestHistory(TestCase):
    def test_series(self):
        with TestEnv() as p:
            
        #db = define_database(provider='sqlite', filename=":memory:")

        #with orm.db_session:
            prices = read_frame("price.csv")
            for symbol in ["A", "B", "C", "D"]:
                ts = p.database.Timeseries(symbol=p.database.Symbol(bloomberg_symbol=symbol, group=p.database.SymbolGroup(name=symbol)), name="PX_LAST")
                for date, value in prices[symbol].dropna().items():
                    p.database.TimeseriesData(ts=ts, date=date, value=value)

            t = p.database.Symbol.get(bloomberg_symbol="A").series["PX_LAST"]
            pdt.assert_series_equal(t, read_frame("price.csv")["A"].dropna(), check_names=False)

            tt = p.database.Timeseries.get(symbol=p.database.Symbol.get(bloomberg_symbol="A"), name="PX_LAST")
            self.assertFalse(tt.empty)
            self.assertEqual(tt.last_valid, pd.Timestamp("2015-04-22").date())


    def test_ref(self):
        with TestEnv() as p:
            t1 = p.database.Type(name="BB-static", comment="Static data Bloomberg")
            t2 = p.database.Type(name="BB-dynamic", comment="Dynamic data Bloomberg")
            t3 = p.database.Type(name="user-defined", comment="User-defined reference data")
            p.database.Field(name="CHG_PCT_1D", type=t2)
            p.database.Field(name="NAME", type=t1)
            p.database.Field(name="REGION", type=t3)

            p.database.Symbol(bloomberg_symbol="XX", group=p.database.SymbolGroup(name="A"))
            p.database.Symbol(bloomberg_symbol="YY", group=p.database.SymbolGroup(name="B"))

            p.database.SymbolReference(field=p.database.Field.get(name="CHG_PCT_1D"), symbol=p.database.Symbol.get(bloomberg_symbol="XX"), content="0.40")
            p.database.SymbolReference(field=p.database.Field.get(name="NAME"), symbol=p.database.Symbol.get(bloomberg_symbol="XX"), content="Hans")
            p.database.SymbolReference(field=p.database.Field.get(name="REGION"), symbol=p.database.Symbol.get(bloomberg_symbol="XX"), content="Europe")

            p.database.SymbolReference(field=p.database.Field.get(name="CHG_PCT_1D"), symbol=p.database.Symbol.get(bloomberg_symbol="YY"), content="0.40")
            p.database.SymbolReference(field=p.database.Field.get(name="NAME"), symbol=p.database.Symbol.get(bloomberg_symbol="YY"), content="Urs")
            p.database.SymbolReference(field=p.database.Field.get(name="REGION"), symbol=p.database.Symbol.get(bloomberg_symbol="YY"), content="Europe")


            s = p.database.Symbol.get(bloomberg_symbol="XX")
            self.assertEqual(s.reference["REGION"], "Europe")

    def test_frame(self):
        with TestEnv() as p:
            x = pd.DataFrame(data=[[1.2, 1.0], [1.0, 2.1]], index=["A","B"], columns=["X1", "X2"])
            x.index.names = ["index"]

            upsert_frame(p.database, name="test", frame=x)

            f = p.database.Frame.get(name="test").frame

            pdt.assert_frame_equal(f, x)


    # def test_portfolio(self):
    #     with db_in_memory(db):
    #         p = test_portfolio()
    #         SymbolGroup(name="A")
    #         SymbolGroup(name="B")
    #
    #         for symbol in ["A", "B", "C", "D"]:
    #             Symbol(bloomberg_symbol=symbol, group=SymbolGroup.get(name="A"))
    #
    #         for symbol in ["E", "F", "G"]:
    #             Symbol(bloomberg_symbol=symbol, group=SymbolGroup.get(name="B"))
    #
    #         upsert_portfolio(name="test", portfolio=p)
    #
    #         x = PortfolioSQL.get(name="test")
    #
    #         pdt.assert_frame_equal(x.portfolio.weights, p.weights)
    #         pdt.assert_frame_equal(x.portfolio.prices, p.prices)
    #         pdt.assert_series_equal(x.nav, p.nav)
    #         self.assertAlmostEquals(x.sector["A"]["2013-01-25"],0.1069106628 )



    # def test_strategy(self):
    #     with db_in_memory(db):
    #         s = Strategy(name="test", source="No", active=True)
    #         self.assertIsNone(s.last_valid)
    #         self.assertIsNone(s.portfolio)
    #         #self.assertIsNone(s.assets)
    #
    #         s.upsert_portfolio(portfolio=test_portfolio())
    #         self.assertIsNotNone(s.portfolio)
    #
    #         pdt.assert_frame_equal(s.portfolio.weight, test_portfolio().weights)
    #         pdt.assert_frame_equal(s.portfolio.price, test_portfolio().prices)
    #
    #         self.assertEquals(s.last_valid, pd.Timestamp("2015-04-22"))
    #
    #         # upsert for a second time....
    #         s.upsert_portfolio(portfolio=test_portfolio())
    #         self.assertIsNotNone(s.portfolio)
    #         pdt.assert_frame_equal(s.portfolio.weight, test_portfolio().weights)
    #         pdt.assert_frame_equal(s.portfolio.price, test_portfolio().prices)
    #         self.assertEquals(s.last_valid, pd.Timestamp("2015-04-22"))


    def test_timeseries(self):
        with TestEnv() as p:
            ts = p.database.Timeseries(name="PX_LAST", symbol=p.database.Symbol(bloomberg_symbol="A"))
            self.assertIsNone(ts.last_valid)
            self.assertTrue(ts.empty)
            ts.upsert(ts=read_frame("price.csv")["A"])
            pdt.assert_series_equal(ts.series, read_frame("price.csv")["A"], check_names=False)
            self.assertEqual(ts.last_valid, pd.Timestamp("2015-04-22").date())
