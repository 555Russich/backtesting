import logging
from datetime import datetime

from backtrader import num2date, TimeFrame, Order
from tinkoff.invest import CandleInterval, InstrumentIdType
from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.date_utils import TZ_UTC
from my_tinkoff.enums import ClassCode
from moex_api import MOEX

from src.strategies.base import BaseStrategy
from src.exceptions import SkipIteration
from src.sizers import SizerPercentOfCash
from src.data_feeds import DataFeedCandles
from src.typed_dicts import ParamsClosingOnHighs
from src.helpers import (
    pack_instruments_datas,
    get_and_prepare_candles,
    get_data_feed
)
from src.multitasking import (
    async_get_instruments_by_tickers,
    multiprocessing_get_instruments_data_feeds,
)
from src.schemas import StrategyData, InstrumentData
from src.backtester import Backtester


class StrategyClosingOnHighs(BaseStrategy):
    params = ParamsClosingOnHighs(
        sizer=None,
        c_day_change=3,
        c_nearly_to_high=0.7,
        take_stop=(.003, .003),
        days_look_back=30,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True
    )

    def __init__(self):
        self.i = 0
        self.indexes_days: list[int] = [1 for _ in range(len(self.datas))]
        self.max_highs: list[int | None] = [None for _ in range(len(self.datas))]
        self.days_changes: list[list[float]] = [[] for _ in range(len(self.datas))]
        self.indexes_last: list[list[int]] = [[] for _ in range(len(self.datas))]

        for i, data in enumerate(self.datas):
            for i_c in range(1, data.buflen()):
                dt1 = num2date(data.datetime[i_c-1])
                dt2 = num2date(data.datetime[i_c])
                if dt2.date() > dt1.date():
                    self.indexes_last[i].append(i_c-1)
                    if dt2.minute == 0 and self.LOGGING:
                        logging.warning(f'{data._name} | No opening auction candle | dt1={dt1} | dt2={dt2}')

        super().__init__()

    def next(self):
        for i, data in enumerate(self.datas):
            self.i = i
            try:
                self._process_data(data)
            except SkipIteration:
                return

    def get_average_day_change(self) -> float:
        days_changes = self.days_changes[self.i]

        if len(days_changes) < self.p.days_look_back:
            raise SkipIteration

        idx = len(days_changes)-1 - self.p.days_look_back
        arr = days_changes[idx:]
        return sum([abs(x) for x in arr]) / len(arr)

    def _process_data(self, data) -> None:
        i = self.i
        indexes_last = self.indexes_last[i]
        i_day = self.indexes_days[i]

        # escaping index error while iterating on last day
        if len(indexes_last) - 1 == i_day:
            raise SkipIteration

        i_last_candle = indexes_last[i_day]
        i_prev_last_candle = indexes_last[i_day - 1]

        # escaping index error while iterating on first day
        if len(data) < i_prev_last_candle:
            raise SkipIteration

        if self.max_highs[i] is None or self.max_highs[i] < data.high[0]:
            self.max_highs[i] = data.high[0]

        # if self.getposition(data) and (
        #         len(data) == i_prev_last_candle + 1 and data.close[0] < data.close[-1] or
        #         len(data) == i_prev_last_candle + 2
        # ):
        #     self.close(data=data)

        # self.log(txt=f'{data._name} | {len(data)} | {len(self.indexes_last[i])=} | {i_day=} | {i_last_candle=} '
        #              f'| {i_prev_last_candle=} | {self.max_highs[i]=} | {data.buflen()=}', data=data)

        if len(data) in [i_last_candle, i_last_candle - 1]:
            reverse_idx_prev_last = i_prev_last_candle - len(data) - 1
            prev_last_close = data.close[reverse_idx_prev_last]
            percent_day_change = (data.close[0] - prev_last_close) / prev_last_close

            if len(data) == i_last_candle - 1:
                average_day_changes = self.get_average_day_change()
                dt = data.datetime.datetime(0)
                percent_change_to_high = (self.max_highs[i] - prev_last_close) / prev_last_close

                if percent_day_change > average_day_changes * self.p.c_day_change and (
                    percent_change_to_high >= percent_day_change > percent_change_to_high * self.p.c_nearly_to_high
                    and
                    self.p.trade_end_of_main_session and self.p.trade_end_of_evening_session or
                    (self.p.trade_end_of_main_session and dt.hour == 15 and dt.minute in list(range(39, 50)) or
                     self.p.trade_end_of_evening_session and dt.hour == 20 and dt.minute == 48)
                ):
                    self.order = self.buy(data=data)
                    price_take = data.close[0] * (1 + self.p.take_stop[0])
                    order_take = self.sell(data=data, price=price_take, exectype=Order.Limit)
                    price_stop = data.close[0] * (1 - self.p.take_stop[1])
                    self.sell(data=data, price=price_stop, exectype=Order.Stop, oco=order_take)

                    self.log(txt=f'{data._name} | close_price={data.close[0]} | {price_take=} | {price_stop=} |'
                                 f' percent_day_change={round(percent_day_change * 100, 2)} | '
                                 f'average_day_changes={round(average_day_changes * 100, 2)} | percent_change_to_high='
                                 f'{round(percent_change_to_high*100, 2)}', data=data)

            elif len(data) == i_last_candle:
                self.days_changes[i].append(percent_day_change)
                self.indexes_days[i] += 1
                self.max_highs[i] = None


async def backtest(from_: datetime, to: datetime, params_strategy: ParamsClosingOnHighs) -> None:
    ticker = 'SBER'
    instrument = await get_instrument_by(id=ticker, id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                                         class_code=ClassCode.TQBR)
    data_feed = await get_data_feed(instrument=instrument, from_=from_,
                                    to=to, interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    logging.info(f'from_={from_} | to={to}\n{params_strategy}')
    backtester = Backtester(
        instruments_data=[InstrumentData(data_feed=data_feed, ticker=ticker)],
        strategies_data=[StrategyData(strategy=StrategyClosingOnHighs, params=params_strategy)],
    )
    backtester.run()


async def optimize(from_: datetime, to: datetime, params_strategy: ParamsClosingOnHighs) -> None:
    async with MOEX() as moex:
        tickers = await moex.get_index_composition('IMOEX')

    instruments = [i for i in await async_get_instruments_by_tickers(tickers=tickers)
                   if i.first_1min_candle_date < from_]
    logging.info(f'Start collecting data for {len(instruments)} instruments')
    data_feeds = multiprocessing_get_instruments_data_feeds(instruments=instruments, from_=from_, to=to,
                                                            interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
    logging.info(f'Packed {len(instruments_datas)} data feeds')
    logging.info(f'from_={from_} | to={to}\n{params_strategy}')

    backtester = Backtester(
        instruments_data=instruments_datas,
        strategies_data=[StrategyData(strategy=StrategyClosingOnHighs, params=params_strategy)],
    )
    backtester.optimize()


async def main():
    to = datetime(year=2024, month=2, day=23, tzinfo=TZ_UTC)
    # from_ = datetime(year=2023, month=1, day=1, tzinfo=TZ_UTC)
    from_ = datetime(year=2018, month=3, day=8, tzinfo=TZ_UTC)
    Backtester.LOGGING = False
    # Backtester.PLOTTING = True

    params_strategy = ParamsClosingOnHighs(
        sizer=SizerPercentOfCash(trade_max_size=0.05),
        c_day_change=(0, 1, 2, 3),
        c_nearly_to_high=0.5,
        take_stop=((.003, .001),),
        days_look_back=60,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True
    )

    # await backtest(from_=from_, to=to, params_strategy=params_strategy)
    await optimize(from_=from_, to=to, params_strategy=params_strategy)

