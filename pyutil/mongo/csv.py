from .abc_archive import Archive
import pandas as pd

class CsvArchive(Archive):
    """
    Mainly used for unit-testing. This is a very minimalistic Archive providing the same interface to access historic
    data as its siblings.
    """
    def __init__(self):
        self.__data = dict()

    def __getitem__(self, item):
        return self.__data[item]

    def __setitem__(self, key, value):
        self.__data[key] = value

    def history(self, items, name="PX_LAST", before=pd.Timestamp("2002-01-01")):
        return self[name][items].truncate(before=before)