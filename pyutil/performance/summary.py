from collections import OrderedDict
from datetime import date

import pandas as pd
import numpy as np

from ._month import _monthlytable
from .periods import period_returns
from ._drawdown import _Drawdown
from ._var import _VaR


# from addict import Dict
def fromReturns(r, adjust=False):
    if r is None:
        return NavSeries(pd.Series({}))

    x = NavSeries((1 + r.dropna()).cumprod())
    if adjust:
        return x.adjust(value=1.0)

    return x


def fromNav(ts, adjust=False):
    #todo: ts is None
    if ts is None:
        return NavSeries(pd.Series({}))

    x = NavSeries(ts.dropna())
    if adjust:
        return x.adjust(value=1.0)

    return x


def performance(nav, alpha=0.95, periods=None):
    return fromNav(nav).summary(alpha=alpha, periods=periods)


class NavSeries(pd.Series):
    def __init__(self, *args, **kwargs):
        super(NavSeries, self).__init__(*args, **kwargs)
        if not self.empty:
            # change to DateTime
            if isinstance(self.index[0], date):
                self.rename(index=lambda x: pd.Timestamp(x), inplace=True)

            # check that all indices are increasing
            assert self.index.is_monotonic_increasing
            # make sure all entries non-negative
            assert not (self < 0).any(), "Problem with data:\n{x}".format(x=self.series)

    @property
    def series(self):
        return pd.Series({t: v for t, v in self.items()})

    @property
    def periods_per_year(self):
        if len(self.index) >= 2:
            x = pd.Series(data=self.index)
            return np.round(365 * 24 * 60 * 60 / x.diff().mean().total_seconds(), decimals=0)
        else:
            return 256

    def annualized_volatility(self, periods=None):
        t = periods or self.periods_per_year
        return np.sqrt(t) * self.dropna().pct_change().std()

    @staticmethod
    def __gmean(a):
        # geometric mean A
        # Prod [a_i] == A^n
        # Apply log on both sides
        # Sum [log a_i] = n log A
        # => A = exp(Sum [log a_i] // n)
        return np.exp(np.mean(np.log(a)))

    def truncate(self, before=None, after=None, adjust=False):
        return fromNav(super().truncate(before=before, after=after), adjust=adjust)

    @property
    def monthlytable(self):
        return _monthlytable(self)

    @property
    def returns(self):
        return self.pct_change().dropna()

    @property
    def returns_monthly(self):
        return self.monthly.pct_change().dropna()

    @property
    def returns_annual(self):
        x = self.annual.pct_change().dropna()
        x.index = [a.year for a in x.index]
        return x

    @property
    def __positive_events(self):
        return (self.returns >= 0).sum()

    @property
    def __negative_events(self):
        return (self.returns < 0).sum()

    @property
    def __events(self):
        return self.returns.size

    @property
    def __cum_return(self):
        return (1 + self.returns).prod() - 1.0

    def sharpe_ratio(self, periods=None, r_f=0):
        return self.__mean_r(periods, r_f=r_f) / self.annualized_volatility(periods)

    def __mean_r(self, periods=None, r_f=0):
        # annualized performance over a risk_free rate r_f (annualized)
        periods = periods or self.periods_per_year
        return periods * (self.__gmean(self.returns + 1.0) - 1.0) - r_f

    @property
    def drawdown(self):
        return _Drawdown(self).drawdown

    def sortino_ratio(self, periods=None, r_f=0):
        periods = periods or self.periods_per_year
        # cover the unrealistic case of 0 drawdown
        m = self.drawdown.max()
        if m == 0:
            return np.inf
        else:
            return self.__mean_r(periods, r_f=r_f) / m

    def calmar_ratio(self, periods=None, r_f=0):
        periods = periods or self.periods_per_year
        start = self.index[-1] - pd.DateOffset(years=3)
        # truncate the nav
        x = self.truncate(before=start)
        return fromNav(x).sortino_ratio(periods=periods, r_f=r_f)

    @property
    def mtd(self):
        """
        Compute the return in the last available month
        :return:
        """
        return self.monthly.pct_change().tail(1).values[0]

    @property
    def ytd(self):
        """
        Compute the return in the last available year
        :return:
        """
        return self.annual.pct_change().tail(1).values[0]

    @staticmethod
    def __ytd(ts: pd.Series, today=None) -> pd.Series:
        """
        Extract year to date of a series or a frame

        :param ts: series or frame
        :param today: today, relevant for testing

        :return: ts or frame starting at the first day of today's year
        """
        today = today or pd.Timestamp("today")
        first_day_of_year = (today + pd.offsets.YearBegin(-1)).date()
        last_day_of_month = (today + pd.offsets.MonthEnd(0)).date()
        return ts.truncate(before=first_day_of_year, after=last_day_of_month)

    @property
    def ytd_series(self):
        """
        Extract the series of monthly returns in the current year
        :return:
        """
        return self.__ytd(self.returns_monthly, today=self.index[-1]).sort_index(ascending=False).rename(index=lambda x: "{:02d}".format(x.month))

    def recent(self, n=15):
        return self.returns.tail(n).dropna()

    def var(self, alpha=0.95):
        return _VaR(series=self, alpha=alpha).var

    def cvar(self, alpha=0.95):
        return _VaR(series=self, alpha=alpha).cvar

    def summary(self, alpha=0.95, periods=None, r_f=0):
        periods = periods or self.periods_per_year

        d = OrderedDict()
        # d = Dict()

        d["Return"] = 100 * self.__cum_return
        d["# Events"] = self.__events
        d["# Events per year"] = periods

        d["Annua Return"] = 100 * self.__mean_r(periods=periods)
        d["Annua Volatility"] = 100 * self.annualized_volatility(periods=periods)
        d["Annua Sharpe Ratio (r_f = {0})".format(r_f)] = self.sharpe_ratio(periods=periods, r_f=r_f)

        dd = self.drawdown
        d["Max Drawdown"] = 100 * dd.max()
        d["Max % return"] = 100 * self.returns.max()
        d["Min % return"] = 100 * self.returns.min()

        d["MTD"] = 100 * self.mtd
        d["YTD"] = 100 * self.ytd

        d["Current Nav"] = self.tail(1).values[0]
        d["Max Nav"] = self.max()
        d["Current Drawdown"] = 100 * dd[dd.index[-1]]

        d["Calmar Ratio (3Y)"] = self.calmar_ratio(periods=periods, r_f=r_f)

        d["# Positive Events"] = self.__positive_events
        d["# Negative Events"] = self.__negative_events

        d["Value at Risk (alpha = {alpha})".format(alpha=int(100 * alpha))] = 100 * self.var(alpha=alpha)
        d["Conditional Value at Risk (alpha = {alpha})".format(alpha=int(100 * alpha))] = 100 * self.cvar(alpha=alpha)
        d["First at"] = self.index[0].date()
        d["Last at"] = self.index[-1].date()

        x = pd.Series(d)
        x.index.name = "Performance number"
        return x

    def ewm_volatility(self, com=50, min_periods=50, periods=None):
        periods = periods or self.periods_per_year
        return np.sqrt(periods) * self.returns.fillna(0.0).ewm(com=com, min_periods=min_periods).std(bias=False)

    @property
    def period_returns(self):
        return period_returns(self.returns, today=self.index[-1])

    def adjust(self, value=100.0):
        if self.empty:
            return NavSeries(pd.Series({}))
        else:
            first = self[self.dropna().index[0]]
            return NavSeries(self * value / first)

    @property
    def monthly(self):
        return fromNav(self.__res("M"))

    @property
    def annual(self):
        return fromNav(self.__res("A"))

    @property
    def weekly(self):
        return fromNav(self.__res("W"))

    def fee(self, daily_fee_basis_pts=0.5, adjust=False):
        ret = self.pct_change().fillna(0.0) - daily_fee_basis_pts / 10000.0
        return fromReturns(ret, adjust=adjust)
        # return fromNav((ret + 1.0).cumprod())

    @property
    def drawdown_periods(self):
        return _Drawdown(self).periods

    def __res(self, rule="M"):
        # refactor NAV at the end but keep the first element. Important for return computations!

        a = pd.concat((self.head(1), self.resample(rule).last()), axis=0)
        # overwrite the last index with the trust last index
        a.index = a.index[:-1].append(pd.DatetimeIndex([self.index[-1]]))
        return a
