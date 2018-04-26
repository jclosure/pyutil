import pandas as _pd
import sqlalchemy as sq
from sqlalchemy.ext.declarative import has_inherited_table
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from pyutil.sql.base import Base
from pyutil.sql.immutable import ReadDict
from pyutil.sql.model.ref import _ReferenceData, Field
from pyutil.sql.model.ts import Timeseries


class MyMixin(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr.cascading
    def id(cls):
        if has_inherited_table(cls):
            return sq.Column(sq.ForeignKey('productinterface.id'), primary_key=True)
        else:
            return sq.Column(sq.Integer, primary_key=True, autoincrement=True)


class ProductInterface(MyMixin, Base):

    discriminator = sq.Column(sq.String)
    __mapper_args__ = {"polymorphic_on": discriminator}

    _refdata = relationship(_ReferenceData, collection_class=attribute_mapped_collection("field"),
                            cascade="all, delete-orphan", back_populates="product", foreign_keys=[_ReferenceData.product_id])

    _timeseries = relationship(Timeseries, collection_class=attribute_mapped_collection('key'),
                               cascade="all, delete-orphan", back_populates="product", foreign_keys=[Timeseries.product_id])

    @property
    def reference(self):
        return ReadDict(seq={field.name: x.value for field, x in self._refdata.items()}, default=None)

    @property
    def timeseries(self):
        return ReadDict(seq={ts: x.series for ts, x in self._timeseries.items()}, default=_pd.Series({}))

    def upsert_ts(self, name, data=None, secondary=None):
        """ upsert a timeseries, get Timeseries object """

        def key(name, secondary=None):
            if secondary:
                return name, secondary
            else:
                return name

        k = key(name, secondary)

        # do we need a new timeseries object?
        if k not in self._timeseries.keys():
            self._timeseries[k] = Timeseries(name=name, product=self, secondary=secondary)

        # now update the timeseries object
        return self._timeseries[k].upsert(data)

    def upsert_ref(self, field, value):
        assert isinstance(field, Field)
        # if the field is not in the keys for the reference data...
        if field not in self._refdata.keys():
            # construct a new ReferenceData row
            self._refdata[field] = _ReferenceData(field=field, product=self, content=value)
        else:
            # just update it
            self._refdata[field].content = value
        # Experts may wonder, whey we are not using the association proxy construct
        # 1. It's hard to read for the non-python experts
        # 2. If you access self._refdata[field unknown to self] you get a key error
        # 3. If you do self.reference[Name of field unknown to self] you get the default value
        # 4. Still find it very surprising that I can not define a default value in case of a key error

    def frame(self, name):
        return _pd.DataFrame({x.secondary: x.series for x in self._timeseries.values() if x.name == name and x.secondary}).sort_index()
