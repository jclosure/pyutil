import pandas as pd
from unittest import TestCase

import pandas.util.testing as pdt

from pyutil.influx.client import Client
from pyutil.performance.summary import fromNav
from test.config import test_portfolio


class TestInfluxDB(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = Client()
        cls.client.recreate(dbname="test")

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_host(self):
        self.assertEqual(self.client.host, "test-influxdb")

    def test_database(self):
        self.assertEqual("test", self.client.database)

    def test_port(self):
        self.assertEqual(self.client.port, 8086)

    def test_repr(self):
        self.assertEqual(str(self.client), "InfluxClient at test-influxdb on port 8086")

    def test_client(self):
        databases = self.client.databases
        self.assertTrue("test" in databases)

    def test_write_series(self):
        nav = test_portfolio().nav
        nav.name = "nav"
        self.client.write(frame=nav.to_frame(name="nav"), tags={"name": "test-a"}, measurement="nav")
        pdt.assert_series_equal(nav, self.client.read(field="nav", measurement="nav", conditions={"name": "test-a"}), check_names=False)

        # alternative way to read the series
        x = self.client.read(field="nav", measurement="nav", tags=["name"])
        y = x.xs(key="test-a", level="name", drop_level=True)

        pdt.assert_series_equal(nav, y.dropna(), check_names=False)
        assert "nav" in self.client.measurements


    def test_write_series_date(self):
        x = pd.Series({pd.Timestamp("1978-11-12").date(): 5.1})
        self.client.write(frame=x.to_frame(name="temperature"), tags={"name": "birthday"}, measurement="nav")
        y = self.client.read(field="temperature", measurement="nav", conditions={"name": "birthday"})
        pdt.assert_series_equal(y, pd.Series({pd.Timestamp("1978-11-12"): 5.1}, name="temperature"), check_names=False)

    def test_write_frame(self):
        nav = test_portfolio().nav
        self.client.write(frame=nav.to_frame(name="maffay"), tags={"name": "test-a"}, measurement="nav2")
        self.client.write(frame=nav.tail(20).to_frame(name="maffay"), tags={"name": "test-b"}, measurement="nav2")

        frame = self.client.read(field="maffay", measurement="nav2", tags=["name"]).unstack()

        pdt.assert_series_equal(fromNav(frame["test-a"]), nav, check_names=False)
        pdt.assert_series_equal(fromNav(frame["test-b"]).dropna(), nav.tail(20), check_names=False)


    def test_stack(self):
        c = Client(database="wurst")
        with c as client:
            print("hello")

    def test_repeat(self):
        nav = test_portfolio().nav
        nav.name = "nav"
        print(nav)

        self.client.write(frame=nav.to_frame(name="wurst"), tags={"name": "test-wurst"}, measurement="navx")
        y = self.client.read(field="wurst", tags=["name"], measurement="navx")

        # write the entire series again!
        self.client.write(frame=nav.to_frame(name="wurst"), tags={"name": "test-wurst"}, measurement="navx")
        x = self.client.read(field="wurst", tags=["name"], measurement="navx")

        self.assertEqual(len(x), len(y))

        #assert False
