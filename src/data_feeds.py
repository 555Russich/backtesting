from my_tinkoff.csv_candles import DELIMITER
from my_tinkoff.schemas import Candles, Candle

from backtrader import (
    TimeFrame,
    date2num
)
from backtrader.feeds import DataBase, GenericCSVData


class DataFeedCandles(DataBase):
    def __init__(self):
        super(DataFeedCandles, self).__init__()
        self.candle_cursor = 0
        self.candles: Candles

        # Use the informative "timeframe" parameter to understand if the
        # code passed as "dataname" refers to an intraday or daily feed
        if self.p.timeframe >= TimeFrame.Days:
            self.barsize = 28
            self.dtsize = 1
            self.barfmt = 'IffffII'
        else:
            self.dtsize = 2
            self.barsize = 32
            self.barfmt = 'IIffffII'

    def _load(self):
        if self.candle_cursor >= len(self.candles)-1:
            return False

        candle = self.candles[self.candle_cursor]
        self.candle_cursor += 1
        return self._loadline(candle)

    def _loadline(self, c: Candle) -> bool | None:
        self.lines.datetime[0] = date2num(c.time)
        self.lines.open[0] = c.open
        self.lines.high[0] = c.high
        self.lines.low[0] = c.low
        self.lines.close[0] = c.close
        self.lines.volume[0] = c.volume
        return True


# df = DataFeedCandles().load_candles(1)
# print(df.lines)


class MyCSVData(GenericCSVData):
    params = (
        ('separator', DELIMITER),
        ('open', 0),
        ('high', 1),
        ('low', 2),
        ('close', 3),
        ('volume', 4),
        ('datetime', 5),
        ('dtformat', '%Y-%m-%d %H:%M:%S%z'),
        ('time', -1),
        ('openinterest', -1),
    )
