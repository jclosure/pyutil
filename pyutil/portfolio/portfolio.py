import os

import pandas as pd

from ..performance.summary import fromReturns
from ..performance.periods import period_returns, periods


def merge(portfolios, axis=0):
    prices = pd.concat([p.prices for p in portfolios], axis=axis, verify_integrity=True)
    weights = pd.concat([p.weights for p in portfolios], axis=axis, verify_integrity=True)
    return Portfolio(prices, weights.fillna(0.0))


def similar(a, b, eps=1e-6):
    if not (isinstance(a, Portfolio) and isinstance(b, Portfolio)):
        return False

    if not (list(a.index) == list(b.index) and list(a.assets) == list(b.assets)):
        return False

    delta_w = (a.weights - b.weights).abs().max().max()
    delta_p = (a.prices - b.prices).abs().max().max()

    if not (delta_w < eps and delta_p < eps):
        return False

    return True


class Portfolio(object):
    def copy(self):
        return Portfolio(prices=self.prices.copy(), weights=self.weights.copy())

    def iron_threshold(self, threshold=0.02):
        """
        Iron a portfolio, do not touch the last index

        :param threshold:
        :return:
        """
        portfolio = self.copy()
        for yesterday, today in zip(self.index[:-2], self.index[1:-1]):
            if (portfolio.weights.loc[today] - portfolio.weights.loc[yesterday]).abs().max() <= threshold:
                portfolio.forward(today, yesterday=yesterday)

        return portfolio

    def iron_time(self, rule):
        # make sure the order is correct...
        portfolio = self.copy()

        moments = [self.index[0]]

        # we need timestamps from the underlying series not the end of the intervals!
        resample = self.weights.resample(rule=rule).last()
        for t in resample.index:
            moments.append([a for a in self.index if a <= t][-1])

        # run through all dates expect the last one...
        for date in self.weights.index[:-1]:
            # if that's not a special date, forward the portfolio
            if date not in moments:
                portfolio.forward(date)

        return portfolio

    def forward(self, t, yesterday=None):
        # We move weights to t
        yesterday = yesterday or self.__before[t]

        # weights of "yesterday"
        w1 = self.__weights.loc[yesterday].dropna()

        # fraction of the cash in the portfolio yesterday
        cash = 1 - w1.sum()

        # new value of each position
        value = w1 * (self.asset_returns.loc[t].fillna(0.0) + 1)

        # compute the new weights...
        self.weights.loc[t] = value / (value.sum() + cash)

        return self

    def __init__(self, prices, weights=None):
        # if you don't specify any weights, we initialize them with nan
        if weights is None:
            weights = pd.DataFrame(index=prices.index, columns=prices.keys(), data=0.0)

        # If weights is a Series, each weight per asset!
        if isinstance(weights, pd.Series):
            w = pd.DataFrame(index=prices.index, columns=weights.keys())
            for t in w.index:
                w.loc[t] = weights

            weights = w

        # make sure the keys are matching
        assert set(weights.keys()) <= set(prices.keys()), "Key for weights not subset of keys for prices"
        # enforce some indixes
        assert prices.index.equals(weights.index), "Index for prices and weights have to match"

        # avoid duplicates
        assert not prices.index.has_duplicates, "Price Index has duplicates"
        assert not weights.index.has_duplicates, "Weights Index has duplicates"

        assert prices.index.is_monotonic_increasing, "Price Index is not increasing"
        assert weights.index.is_monotonic_increasing, "Weight Index is not increasing"

        self.__prices = prices.ffill()

        for key, w in weights.items():
            # check the weight series...
            series = w.copy()
            series.index = range(0, len(series))
            # remove all nans
            series = series.dropna()

            # compute the length of the maximal gap
            max_gap = pd.Series(data=series.index).diff().dropna().max()
            assert not max_gap > 1, "There are gaps in the series {0} and gap {1}".format(w, max_gap)

        self.__weights = weights

        self.__before = {today : yesterday for today, yesterday in zip(prices.index[1:], prices.index[:-1])}
        self.__r = self.__prices.pct_change()

    def __repr__(self):
        return "Portfolio with assets: {0}".format(list(self.__weights.keys()))

    @property
    def cash(self):
        """
        cash series
        :return:
        """
        return 1.0 - self.leverage

    @property
    def assets(self):
        """
        list of assets
        :return:
        """
        return list(self.__prices.sort_index(axis=1).columns)

    @property
    def prices(self):
        """
        frame of prices
        :return:
        """
        return self.__prices

    @property
    def weights(self):
        """
        frame of weights
        :return:
        """
        return self.__weights

    @property
    def asset_returns(self):
        """
        frame of returns
        :return:
        """
        return self.__r

    @property
    def nav(self):
        """
        nav series
        :return:
        """
        return fromReturns(self.weighted_returns.sum(axis=1))

    @property
    def weighted_returns(self):
        """
        frame of returns after weights
        :return:
        """
        r = self.asset_returns.fillna(0.0)
        return pd.DataFrame({a: r[a]*self.weights[a].dropna().shift(1).fillna(0.0) for a in self.assets})

    @property
    def index(self):
        """
        index of the portfolio (e.g. timestamps)
        :return:
        """
        return self.prices.index

    @property
    def leverage(self):
        """
        leverage (sum of weights)
        :return:
        """
        return self.weights.sum(axis=1).dropna().apply(float)

    def truncate(self, before=None, after=None):
        """
        truncate the portfolio
        :param before:
        :param after:
        :return:
        """
        return Portfolio(prices=self.prices.truncate(before=before, after=after),
                    weights=self.weights.truncate(before=before, after=after))

    @property
    def empty(self):
        """
        true only if the portfolio is empty
        :return:
        """
        return len(self.index) == 0

    @property
    def weight_current(self):
        """
        current weight, e.g. the last weight
        :return:
        """
        w = self.weights.ffill()
        a = w.loc[w.index[-1]]
        a.index.name = "weight"
        return a

    def sector_weights(self, symbolmap, total=False):
        """
        weights per sector, symbolmap is a dictionary
        :param symbolmap:
        :param total:
        :return:
        """
        frame = self.weights.ffill().groupby(by=symbolmap, axis=1).sum()
        if total:
            frame["Total"] = frame.sum(axis=1)
        return frame

    def sector_weights_final(self, symbolmap, total=False):
        return self.sector_weights(symbolmap=symbolmap, total=total).iloc[-1]

    def snapshot(self, n=5):
        """
        Give a snapshot of the portfolio, e.g. MTD, YTD and the weights at the last n trading days for each asset
        :param n:
        :return:
        """
        today = self.index[-1]
        offsets = periods(today)

        a = self.weighted_returns.apply(period_returns, offset=offsets).transpose()[
            ["Month-to-Date", "Year-to-Date"]]
        t = self.trading_days[-n:]

        b = self.weights.ffill().loc[t].rename(index=lambda x: x.strftime("%d-%b-%y")).transpose()
        return pd.concat((a, b), axis=1)

    def top_flop_ytd(self, n=5, day_final=pd.Timestamp("today")):
        return self.__f(n=n, day_final=day_final, term="Year-to-Date")

    def __f(self, n=5, term="Month-to-Date", day_final=pd.Timestamp("today")):
        s = self.weighted_returns.apply(period_returns, offset=periods(today=day_final)).transpose()[term]
        return {"top": s.sort_values(ascending=False).head(n), "flop": s.sort_values(ascending=True).head(n)}

    def top_flop_mtd(self, n=5, day_final=pd.Timestamp("today")):
        return self.__f(n=n, day_final=day_final, term="Month-to-Date")

    def tail(self, n=10):
        w = self.weights.tail(n)
        return Portfolio(prices=self.prices.loc[w.index], weights=w)

    @property
    def position(self):
        return pd.DataFrame({k: self.weights[k] * self.nav / self.prices[k] for k in self.assets})

    def subportfolio(self, assets):
        return Portfolio(prices=self.prices[assets], weights=self.weights[assets])

    def __mul__(self, other):
        return Portfolio(prices=self.prices, weights=other * self.weights)

    def __rmul__(self, other):
        return self.__mul__(other)

    def apply(self, function, axis=0):
        return Portfolio(prices=self.prices, weights=self.weights.apply(function, axis=axis))

    @property
    def trading_days(self):
        __fundsize = 1e6
        days = (__fundsize * self.position).diff().abs().sum(axis=1)
        return sorted(list(days[days > 1].index))

    @property
    def state(self):
        # get the last 5 trading days
        trade_events = self.trading_days[-5:-1]
        today = self.index[-1]
        if today not in trade_events:
            trade_events.append(today)

        # extract the weights at all those trade events
        weights = self.weights.ffill().loc[trade_events].transpose()

        # that's the portfolio where today has been forwarded to (from yesterday),
        p = Portfolio(prices=self.prices, weights=self.weights.copy()).forward(today)

        weights = weights.rename(columns=lambda x: x.strftime("%d-%b-%y"))

        weights["Extrapolated"] = p.weights.loc[today]
        weights["Gap"] = self.weights.loc[today] - p.weights.loc[today]
        weights.index.name = "Symbol"
        return weights
    #
    # def to_csv(self, folder=None):
    #     if folder:
    #         self.prices.to_csv(os.path.join(folder, "prices.csv"))
    #         self.weights.to_csv(os.path.join(folder, "weights.csv"))
    #     else:
    #         return self.prices.to_csv(), self.weights.to_csv()
    #
    # @staticmethod
    # def read_csv(folder):
    #     return Portfolio(prices=pd.read_csv(os.path.join(folder, "prices.csv"), index_col=0, parse_dates=True),
    #               weights=pd.read_csv(os.path.join(folder, "weights.csv"), index_col=0, parse_dates=True))

if __name__ == "__main__":
    idx = pd.DatetimeIndex(start=pd.Timestamp("2018-10-28"), periods=100, freq="D")
    print(idx)

    x = pd.Series(data=idx, index=idx)
    print(x)

    # monthly
    print(sorted(x.groupby([idx.year, idx.month]).last().values))

    # weekly
    print(sorted(x.groupby(idx.map(lambda x: x.isocalendar()[0:2])).last().values))
