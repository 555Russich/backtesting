from my_tinkoff.csv_candles import DELIMITER

import backtrader as bt


class MyCSVData(bt.feeds.GenericCSVData):
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
