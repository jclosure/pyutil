import pandas as pd
import sqlalchemy as _sq
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship as _relationship


from pyutil.sql.interfaces.products import ProductInterface, association_table
from pyutil.sql.interfaces.risk.currency import Currency
from pyutil.sql.interfaces.risk.custodian import Custodian
from pyutil.sql.interfaces.risk.security import Security
from pyutil.sql.model.ref import Field, DataType, FieldType
from pyutil.sql.util import parse

_association_table = association_table(left="security", right="owner", name="security_owner")


FIELDS = {
    "name": Field(name="Name", result=DataType.string, type=FieldType.other),
    "15. Custodian Name": Field(name="Custodian", result=DataType.string, type=FieldType.other),
    "17. Reference Currency": Field(name="Currency", result=DataType.string, type=FieldType.other),
    "18. LWM Risk Profile": Field(name="Risk Profile", result=DataType.string, type=FieldType.other),
    "23. LWM - AUM Type": Field(name="AUM Type", result=DataType.string, type=FieldType.other),
    "Inception Date": Field(name="Inception Date", result=DataType.string, type=FieldType.other)  # don't use date here...
}




class Owner(ProductInterface):
    __mapper_args__ = {"polymorphic_identity": "Owner"}
    __securities = _relationship(Security, secondary=_association_table, backref="owner", lazy="joined")
    __currency_id = _sq.Column("currency_id", _sq.Integer, _sq.ForeignKey(Currency.id), nullable=True)
    __currency = _relationship(Currency, foreign_keys=[__currency_id], lazy="joined")
    __custodian_id = _sq.Column("custodian_id", _sq.Integer, _sq.ForeignKey(Custodian.id), nullable=True)
    __custodian = _relationship(Custodian, foreign_keys=[__custodian_id], lazy="joined")

    def __init__(self, name, currency=None, custodian=None):
        super().__init__(name=name)
        self.currency = currency
        self.custodian = custodian

    def __repr__(self):
        return "Owner({id}: {name})".format(id=self.name, name=self.get_reference("Name"))

    @hybrid_property
    def currency(self):
        return self.__currency

    @currency.setter
    def currency(self, value):
        self.__currency = value

    @hybrid_property
    def custodian(self):
        return self.__custodian

    @custodian.setter
    def custodian(self, value):
        self.__custodian = value

    @property
    def securities(self):
        return self.__securities



    def position(self, client, sum=False, tail=None):
        f = client.read_series(measurement="WeightsOwner", field="weight", tags=["security"], conditions={"owner": self.name}).unstack()
        print(f)
        #assert False

        #f = client.query("""SELECT weight::field, security::tag FROM owner WHERE "owner"='{name}'""".format(name=self.name))
        #f = f["owner"].set_index(keys=["security"], append=True).groupby(level=[0, 1]).sum()
        # print(f).sum()
        # assert False
        #f = f.unstack(level=-1).tz_localize(None)["weight"]  #.tail(1).transpose()
        #print(f)


        #f = client.query("""SELECT weight::field, security::tag FROM owner WHERE "owner"='{name}'""".format(name=self.name))
        #if measurement in f:
        #f = f["weight"].tz_localize(None)
        #f.set_index(keys=["security"], append=True)
        #f.groupby()
        #print(f).sum()


        #f = client.frame(field="weight", tags=["security"], measurement="owner", conditions=[("owner", self.name)])

        if tail:
            f = f.tail(tail)

        f = f.transpose()

        if sum:
            f.loc["Sum"] = f.sum(axis=0)

        return f

    def position_by(self, client, index_col, sum=False, tail=None):
        pos = self.position(client=client, sum=False, tail=tail)
        return self.__weighted_by(x=pos, index_col=index_col, sum=sum)

    def __weighted_by(self, x, index_col, sum=False):
        try:
            ref = self.reference_securities[index_col]
            a = pd.concat((x, ref), axis=1, sort=True).groupby(by=index_col).sum()
            if sum:
                a.loc["Sum"] = a.sum(axis=0)
            # this is a very weird construction but it seems it can not be avoided
            return pd.DataFrame(index=a.index, data=a.values, columns=pd.DatetimeIndex([b for b in a.keys()]))
        except KeyError:
            return pd.DataFrame({})

    def vola_securities(self, client):
        x = pd.DataFrame({security.name: security.volatility(client=client, currency=self.currency) for security in self.securities})
        return x.transpose()

    def vola_weighted(self, client, sum=False, tail=None):
        w = self.position(client, sum=False, tail=tail)
        v = self.vola_securities(client=client)
        print("WWWWWWWWeights")
        print(w)
        print("VVVVVVolatitiliy")
        print(v)

        x = w.multiply(v).dropna(axis=0, how="all").dropna(axis=1, how="all")

        if sum:
            x.loc["Sum"] = x.sum(axis=0)

        return x

    def vola_weighted_by(self, client, index_col, sum=False, tail=None):
        vola = self.vola_weighted(client=client, sum=False, tail=tail)
        return self.__weighted_by(x=vola, index_col=index_col, sum=sum)

    @property
    def reference_securities(self):
        return pd.DataFrame({security.name: security.reference_series.sort_index() for security in self.securities}).sort_index().transpose()

    @property
    def kiid(self):
        return pd.Series({security.name: security.kiid for security in self.securities})

    def kiid_weighted(self, client, sum=False, tail=None):
        x = self.position(client=client, sum=False, tail=tail).apply(lambda weights: weights * self.kiid, axis=0).dropna(axis=0, how="all")
        if sum:
            x.loc["Sum"] = x.sum(axis=0)
        return x

    def kiid_weighted_by(self, client, index_col, sum=False, tail=None):
        kiid = self.kiid_weighted(client=client, sum=False, tail=tail)
        return self.__weighted_by(x=kiid, index_col=index_col, sum=sum)

    def upsert_return(self, client, ts):
        client.write_series(ts=ts, field="return", tags={"owner": self.name}, measurement='ReturnOwner')

    def upsert_position(self, client, security, custodian, ts):
        assert isinstance(security, Security)
        assert isinstance(custodian, Custodian)

        client.write_series(ts=ts, field="weight", tags={"owner": self.name, "security": security.name, "custodian": custodian.name}, measurement="WeightsOwner")

    def upsert_volatility(self, client, ts):
        client.write_series(ts=ts, field="volatility", tags={"owner": self.name}, measurement='VolatilityOwner')

    def returns(self, client):
        # this is fast!
        return client.read_series(field="return", measurement="ReturnOwner", conditions={"owner": self.name})

    def volatility(self, client):
        return client.read_series(field="volatility", measurement="VolatilityOwner", conditions={"owner": self.name})

    @staticmethod
    def returns_all(client):
        return client.read_series(measurement="ReturnOwner", field="return", tags=["owner"], unstack=True)

    @staticmethod
    def volatility_all(client):
        return client.read_series(measurement="VolatilityOwner", field="volatility", tags=["owner"], unstack=True)

    @staticmethod
    def position_all(client):
        return client.read_series(measurement="WeightsOwner", field="weight", tags=["owner", "security", "custodian"])

    @staticmethod
    def reference_frame(owners):
        def __row(owner):
            rows = [{"owner": owner.name, "field": field.name, "content": value, "result": field.result} for field, value in owner.reference.items()]
            return parse(rows, index=["owner", "field"])

        return pd.concat([__row(owner) for owner in owners], axis=0).unstack(level=-1)

    @staticmethod
    def reference_frame_securities(owners):
        def __row(owner):
            a = Security.reference_frame(owner.securities)
            a["owner"] = owner.name
            return a.set_index("owner", append=True).swaplevel(i=0, j=1)#.swaplevel(i=1, j=2)

        try:
            return pd.concat([__row(owner) for owner in owners], axis=0)
        except AttributeError:
            return pd.DataFrame({})


