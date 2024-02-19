import logging
from datetime import datetime, timedelta

from backtrader import Cerebro, num2date
from backtrader.analyzers import SharpeRatio
from tinkoff.invest import (
    InstrumentIdType,
    CandleInterval,
    Instrument,
)
from my_tinkoff.date_utils import DateTimeFactory
from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.csv_candles import CSVCandles
from my_tinkoff.schemas import Shares
from my_tinkoff.enums import Board

from src.strategies.base import MyStrategy
from src.schemas import StrategyResult
from src.helpers import get_timeframe_by_candle_interval
from src.csv_data import MyCSVData


class StrategyClosingOnHighs(MyStrategy):
    def __init__(self):
        self.idx_day = 0
        self.high = list(self.data.high)

        self.idx_first_candles: list[int] = []
        for i in range(1, self.data.buflen()):
            c1 = num2date(self.data.datetime[i-1])
            c2 = num2date(self.data.datetime[i])
            if c2.date() > c1.date():
                self.idx_first_candles.append(i)

        self.day_changes_percent = []
        self.max_day_changes_percent = []
        for k in range(1, len(self.idx_first_candles)):
            idx_first_candle_in_day = self.idx_first_candles[k-1]
            idx_last_candle_in_day = self.idx_first_candles[k]-1
            # dt_first_candle_in_day = num2date(self.data.datetime[idx_first_candle_in_day])
            # dt_last_candle_in_day = num2date(self.data.datetime[idx_last_candle_in_day])

            day_open = self.data.open[idx_first_candle_in_day]
            day_close = self.data.close[idx_last_candle_in_day]
            day_high = max(self.high[idx_first_candle_in_day:idx_last_candle_in_day+1])

            day_change_percent = (day_close - day_open) / day_open * 100
            day_max_change_percent = (day_high - day_open) / day_open * 100
            self.day_changes_percent.append(day_change_percent)
            self.max_day_changes_percent.append(day_max_change_percent)

            # print(f'{dt_first_candle_in_day} | {dt_last_candle_in_day} | {day_change_percent=} | {day_max_change_percent=}')

        self.idx_first_candles.pop(0)
        super().__init__()

    def next(self):
        dt = num2date(self.data.datetime[0])
        if dt.weekday() in [5, 6]:
            return

        if self.position:
            if self.position.size < 0:
                self.buy(size=self.position.size)
            elif self.position.size > 0:
                self.sell(size=self.position.size)

        idx = len(self.data) - 1
        idx_last_candle_in_day = self.idx_first_candles[self.idx_day] - 1
        # print(f'{idx=} | {idx_last_candle_in_day=} | {self.cursor=}')

        if idx == idx_last_candle_in_day-2:
            day_change_percent = self.day_changes_percent[self.idx_day]
            max_day_change_percent = self.max_day_changes_percent[self.idx_day]
            self.idx_day += 1
            if max_day_change_percent > 2 and day_change_percent > 1.7:
                self.log(f'{max_day_change_percent=} | {day_change_percent=}')
                self.buy(size=self.get_max_size(self.data.close[0]) // 2)

        elif self.idx_day >= len(self.idx_first_candles)-1:
            return
        elif idx > idx_last_candle_in_day:
            self.idx_day += 1
        # print(f'{dt} | {self.data.open[0]=} | {self.data.close[0]=}')


async def backtest_one_instrument(
        instrument: Instrument,
        start_cash: int,
        comm: float,
        from_: datetime,
        to: datetime,
        interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_1_MIN
) -> StrategyResult | None:
    candles = await CSVCandles.download_or_read(instrument=instrument, from_=from_, to=to, interval=interval)
    if not candles:
        return None
    candles.check_datetime_consistency()
    timeframe = get_timeframe_by_candle_interval(interval)

    cerebro = Cerebro()
    cerebro.broker.set_cash(start_cash)
    cerebro.broker.setcommission(comm)

    filepath = CSVCandles.get_filepath(instrument, interval=interval)
    data = MyCSVData(dataname=filepath, fromdate=from_, todate=to, timeframe=timeframe)
    cerebro.adddata(data)

    cerebro.addanalyzer(SharpeRatio, _name='sharpe')
    cerebro.addstrategy(StrategyClosingOnHighs)

    strats = cerebro.run()
    strategy_result = StrategyResult(
        ticker=instrument.ticker,
        start_cash=start_cash,
        trades=strats[0].trades,
        sharpe_ratio=strats[0].analyzers.sharpe.get_analysis()['sharperatio']
    )
    logging.info(strategy_result)
    cerebro.plot(style='candlestick')
    return strategy_result


async def main():
    to = DateTimeFactory.now()
    # to -= timedelta(days=365*7)
    from_ = DateTimeFactory.replace_time(to - timedelta(days=365))
    print(f'FROM={from_} | TO={to}')
    start_cash = 100_000
    comm = .0004

    instrument = await get_instrument_by(
        id='SBER',
        id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
        class_code=Board.TQBR
    )
    await backtest_one_instrument(
        instrument=instrument,
        start_cash=start_cash,
        comm=comm,
        from_=instrument.first_1min_candle_date,
        # from_=from_,
        to=to,
    )

    # instruments = Shares.from_board(Board.TQBR)
    # for instrument