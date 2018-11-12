import pandas as pd

from pyutil.sql.interfaces.risk.currency import Currency
from pyutil.sql.interfaces.risk.custodian import Custodian
from pyutil.sql.interfaces.risk.owner import Owner
from pyutil.sql.interfaces.risk.security import Security


class Database(object):

    def __init__(self, session):
        # session, sql database
        self.__session = session

    def close(self):
        self.__session.close()

    @property
    def session(self):
        return self.__session

    @property
    def owners(self):
        return self.__session.query(Owner)

    @property
    def securities(self):
        return self.__session.query(Security)

    @property
    def currencies(self):
        return self.__session.query(Currency)

    @property
    def custodians(self):
        return self.__session.query(Custodian)

    def owner(self, name):
        return self.owners.filter(Owner.name == name).one()

    def security(self, name):
        return self.securities.filter(Security.name == name).one()

    def currency(self, name):
        return self.currencies.filter(Currency.name == name).one()

    def custodian(self, name):
        return self.custodians.filter(Custodian.name == name).one()

    @property
    def reference_owners(self):
        frame = Owner.reference_frame(self.owners, name="Entity ID")
        frame = frame.reset_index() #.set_index("Name")
        return frame

    @property
    def reference_securities(self):
        frame = Security.reference_frame(self.securities, name="Entity ID")
        frame = frame.reset_index() #.set_index("Name")
        return frame

    @property
    def prices(self):
        return pd.DataFrame({security: security.get_ts("price") for security in self.securities})

    @property
    def returns(self):
        return pd.DataFrame({owner: owner.get_ts("return") for owner in self.owners})

    @property
    def owner_volatility(self):
        return pd.DataFrame({owner: owner.ts["volatility"] for owner in self.owners})

    def securities_volatility(self, currency):
        return pd.DataFrame({security: security.volatility(currency) for security in self.securities})

