import pandas as _pd
import sqlalchemy as sq
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from pyutil.sql.base import Base
from sqlalchemy.types import Enum as _Enum

from pyutil.sql.common import FieldType, DataType


class _ReadDict(object):
    def __init__(self, data, default=None):
        self.__data = data
        self.__default = default

    def __getitem__(self, item):
        try:
            return self.__data[item]
        except KeyError:
            return self.__default

    def keys(self):
        return self.__data.keys()

    def to_pandas(self, series=True):
        if series:
            return _pd.Series(self.__data)
        else:
            return _pd.DataFrame(self.__data)

    def items(self):
        return self.__data.items()


class ProductInterface(Base):
    __tablename__ = "productinterface"
    id = sq.Column(sq.Integer, primary_key=True, autoincrement=True)
    discriminator = sq.Column(sq.String)

    __mapper_args__ = {"polymorphic_on": discriminator}

    _refdata = relationship("ReferenceData", collection_class=attribute_mapped_collection("field"),
                            cascade="all, delete-orphan", backref="product")

    #_refdata_proxy = association_proxy("_refdata", "value",
    #                                   creator=lambda key, value: ReferenceData(field=key, content=value))

    _timeseries = relationship("Timeseries", collection_class=attribute_mapped_collection('name'),
                               cascade="all, delete-orphan", backref="product")

    xxx = association_proxy("_timeseries", "series",
                                          creator=lambda key, value: Timeseries(name=key, data=value))

    @property
    def reference(self):
        return _ReadDict(data={field.name: x.value for field, x in self._refdata.items()}, default=None)

    @property
    def timeseries(self):
        return _ReadDict(data={ts: x.series for ts, x in self._timeseries.items()}, default=_pd.Series({}))

    def upsert_ts(self, name, data=None):
       """ upsert a timeseries, get Timeseries object """
       if name not in self._timeseries.keys():
           self._timeseries[name] = Timeseries(name=name, product=self)

       return self._timeseries[name].upsert(data)

    def upsert_ref(self, field, value):
        if field not in self._refdata.keys():
            self._refdata[field] = ReferenceData(field=field, product=self, content=value)
        else:
            self._refdata[field].content = value


class Field(Base):
    __tablename__ = "reference_field"
    _id = sq.Column("id", sq.Integer, primary_key=True, autoincrement=True)
    name = sq.Column(sq.String(50), unique=True)
    type = sq.Column(_Enum(FieldType))
    result = sq.Column(_Enum(DataType), nullable=False)

    _refdata_by_product = relationship("ReferenceData", backref="field",
                                       collection_class=attribute_mapped_collection("product"))

    refdata = association_proxy("_refdata_by_product", "value",
                                creator=lambda key, value: ReferenceData(product=key, content=value))

    @property
    def reference(self):
        return _pd.Series({key.name: x for key, x in self.refdata.items()})

    def __repr__(self):
        return "{name}".format(name=self.name)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.name == other.name and self.type == other.type

    def __hash__(self):
        return hash(str(self.name))

    def parse(self, argument):
        return self.result(argument)


class ReferenceData(Base):
    __tablename__ = "reference_data"
    _field_id = sq.Column("field_id", sq.Integer, sq.ForeignKey(Field._id), primary_key=True)
    content = sq.Column(sq.String(200), nullable=False)
    product_id = sq.Column(sq.Integer, sq.ForeignKey(ProductInterface.id), primary_key=True)

    def __repr__(self):
        return "{field} for {x}: {value}".format(field=self.field.name, value=self.content, x=self.product)

    def __init__(self, field=None, product=None, content=None):
        self.content = content
        self.field = field
        self.product = product

    @property
    def value(self):
        return self.field.parse(self.content)

    @value.setter
    def value(self, x):
        self.content = str(x)


# time series data for a product
class Timeseries(Base):
    __tablename__ = "ts_name"
    id = sq.Column(sq.Integer, primary_key=True, autoincrement=True)
    name = sq.Column(sq.String(100), nullable=False)
    product_id = sq.Column(sq.Integer, sq.ForeignKey(ProductInterface.id))

    sq.UniqueConstraint('product', 'name')

    _data = relationship("_TimeseriesData", collection_class=attribute_mapped_collection('date'),
                         cascade="all, delete-orphan", backref="ts")

    data = association_proxy("_data", "value", creator=lambda key, value: _TimeseriesData(date=key, value=value))

    def __init__(self, name=None, product=None, data=None):
        self.name = name
        self.product = product
        if data is not None:
            self.upsert(data)

    @property
    def series(self):
        return _pd.Series({date: x.value for date, x in self._data.items()})

    def upsert(self, ts=None):
        try:
            for date, value in ts.items():
                self.data[date] = value
        except AttributeError:
            pass

        return self

    @property
    def last_valid(self):
        return self.series.last_valid_index()


class _TimeseriesData(Base):
    __tablename__ = 'ts_data'
    date = sq.Column(sq.Date, primary_key=True)
    value = sq.Column(sq.Float)
    _ts_id = sq.Column("ts_id", sq.Integer, sq.ForeignKey(Timeseries.id), primary_key=True)

    def __init__(self, date=None, value=None, ts=None):
        self.date = date
        self.value = value
        self.ts = ts