import pandas as pd


def merge(new, old=None):
    # very smart merging here, new and old merge
    if new is not None:
        if old is not None:
            x = pd.concat((new, old), sort=True)
            return x.groupby(x.index).first().sort_index()
        else:
            return new

    else:
        return old


def last_index(ts, default=None):
    try:
        # if the object is empty
        return ts.last_valid_index() or default
    except AttributeError:
        return default


def first_index(ts, default=None):
    try:
        return ts.first_valid_index() or default
    except AttributeError:
        return default


def to_datetime(ts=None):
    try:
        ts.index = pd.to_datetime(ts.index)
        return ts
    except AttributeError:
        return None

def to_date(ts=None):
    try:
        ts.index = [a.date() for a in to_datetime(ts).index]
        return ts
    except AttributeError:
        return None