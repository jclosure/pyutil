import pandas as pd
import sqlalchemy as sq
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from pyutil.performance.summary import fromNav
from pyutil.sql.interfaces.products import ProductInterface
from pyutil.sql.interfaces.risk.custodian import Currency
from pyutil.sql.interfaces.series import Series

from pyutil.timeseries.merge import merge


def _create_volatility(currency, data):
    assert isinstance(currency, Currency)
    assert isinstance(data, pd.Series)

    return Series(name="volatility", product2=currency, data=data)


class Security(ProductInterface):
    __tablename__ = "security"
    __mapper_args__ = {"polymorphic_identity": "Security"}

    fullname = sq.Column("fullname", sq.String, nullable=True)

    id = sq.Column(sq.ForeignKey(ProductInterface.id, onupdate="CASCADE", ondelete="CASCADE"), primary_key=True)

    # define the price...
    _price_rel = relationship(Series, uselist=False, primaryjoin=ProductInterface.join_series("price"), lazy="joined")

    _price = association_proxy("_price_rel", "data", creator=lambda data: Series(name="price", data=data))

    # define the volatility (dictionary where currency is the key!)
    _vola_rel = relationship(Series, collection_class=attribute_mapped_collection("product_2"),
                         primaryjoin=ProductInterface.join_series("volatility"), lazy="joined")

    _vola = association_proxy(target_collection="_vola_rel", attr="data",
                              creator=lambda currency, data: _create_volatility(currency=currency, data=data))

    def __init__(self, name, fullname=None):
        super().__init__(name)
        self.fullname = fullname

    def __repr__(self):
        return "Security({id}: {name})".format(id=self.name, name=self.get_reference("Name"))

    @hybrid_property
    def kiid(self):
        return self.get_reference("KIID")

    @hybrid_property
    def bloomberg_ticker(self):
        return self.get_reference("Bloomberg Ticker", default=None)

    @hybrid_property
    def bloomberg_scaling(self):
        return self.get_reference("Bloomberg Multiplier", default=1.0)

    def to_json(self):
        nav = fromNav(self._price)
        return {"Price": nav, "Volatility": nav.ewm_volatility(), "Drawdown": nav.drawdown, "name": self.name}

    @property
    def vola_frame(self):
        return pd.DataFrame({key: item for (key, item) in self._vola.items()})

    def upsert_volatility(self, currency, ts):
        assert isinstance(currency, Currency)
        self._vola[currency] = merge(new=ts, old=self._vola.get(currency, default=None))
        return self._vola[currency]

    def upsert_price(self, ts):
        # self.price will be None if not defined
        self._price = merge(new=ts, old=self._price)
        return self.price

    @property
    def price(self):
        return self._price

    def volatility(self, currency):
        return self._vola.get(currency, pd.Series({}))

    @staticmethod
    def frame(securities):
        frame = pd.DataFrame({security: {**security.reference_series, **{"Name": security.fullname, "Entity ID": int(security.name)}} for security in securities}).transpose()
        frame.index.name = "Security"
        return frame.sort_index()
