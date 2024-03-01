import logging
from datetime import datetime

from backtrader import num2date, TimeFrame
from tinkoff.invest import CandleInterval
from my_tinkoff.date_utils import TZ_UTC
from moex_api import MOEX

from src.strategies.base import MyStrategy
from src.exceptions import SkipIteration
from src.sizers import MySizer
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


class StrategyClosingOnHighs(MyStrategy):
    params = ParamsClosingOnHighs(
        sizer=None,
        c_day_change=3,
        c_nearly_to_high=0.7,
        min_days_changes=10,
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

    def get_days_changes(self) -> list[float]:
        days_changes = self.days_changes[self.i]

        if len(days_changes) < self.p.min_days_changes:
            raise SkipIteration
        elif len(days_changes) >= self.p.days_look_back:
            return days_changes[len(days_changes) - 1 - self.p.days_look_back:]

        return days_changes

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

        if self.getposition(data) and (
                # len(data) == i_prev_last_candle + 1 and data.close[0] < data.close[-1] or
                len(data) == i_prev_last_candle + 2
        ):
            self.close(data=data)

        # self.log(txt=f'{data._name} | {len(data)} | {len(self.indexes_last[i])=} | {i_day=} | {i_last_candle=} '
        #              f'| {i_prev_last_candle=} | {self.max_highs[i]=} | {data.buflen()=}', data=data)

        if len(data) in [i_last_candle, i_last_candle - 1]:
            reverse_idx_prev_last = i_prev_last_candle - len(data) - 1
            prev_last_close = data.close[reverse_idx_prev_last]
            percent_day_change = (data.close[0] - prev_last_close) / prev_last_close

            if len(data) == i_last_candle - 1:
                days_changes = self.get_days_changes()
                average_day_changes = sum([abs(x) for x in days_changes]) / len(days_changes)
                dt = data.datetime.datetime(0)
                percent_change_to_high = (self.max_highs[i] - prev_last_close) / prev_last_close

                if percent_day_change > average_day_changes * self.p.c_day_change and (
                    percent_change_to_high >= percent_day_change > percent_change_to_high * self.p.c_nearly_to_high
                    and
                    (self.p.trade_end_of_main_session is True and dt.hour == 15 and dt.minute in list(range(39, 50)) or
                     self.p.trade_end_of_evening_session is True and dt.hour == 20 and dt.minute == 48)
                ):
                    self.log(txt=f'{data._name} | percent_day_change={round(percent_day_change * 100, 2)} | '
                                 f'average_day_changes={round(average_day_changes * 100, 2)} | percent_change_to_high='
                                 f'{round(percent_change_to_high*100, 2)}', data=data)
                    self.order = self.buy(data=data)

            elif len(data) == i_last_candle:
                self.days_changes[i].append(percent_day_change)
                self.indexes_days[i] += 1
                self.max_highs[i] = None


async def backtest_single(from_: datetime, to: datetime) -> None:
    tickers = ['SBER']
    instruments = await async_get_instruments_by_tickers(tickers=tickers)
    logging.info(f'Start collecting data for {len(instruments)} instruments')
    data_feeds = multiprocessing_get_instruments_data_feeds(instruments=instruments, from_=from_, to=to,
                                                            interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
    params_strategy = ParamsClosingOnHighs(
        sizer=MySizer(trade_max_size=0.05),
        c_day_change=0,
        c_nearly_to_high=0.5,
        min_days_changes=10,
        days_look_back=30,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True
    )
    logging.info(f'from_={from_} | to={to} | {params_strategy}')
    StrategyClosingOnHighs.backtest_instruments_together(instruments_datas, **params_strategy)


async def backtest_multiple(from_: datetime, to: datetime) -> None:
    async with MOEX() as moex:
        tickers = await moex.get_index_composition('IMOEX')

    instruments = await async_get_instruments_by_tickers(tickers=tickers)
    logging.info(f'Start collecting data for {len(instruments)} instruments')

    """ Multi """
    data_feeds = multiprocessing_get_instruments_data_feeds(instruments=instruments, from_=from_, to=to,
                                                            interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
    logging.info(f'Packed {len(instruments_datas)} data feeds')
    params_strategy = ParamsClosingOnHighs(
        sizer=MySizer(trade_max_size=0.05),
        c_day_change=3,
        c_nearly_to_high=0.7,
        min_days_changes=10,
        days_look_back=30,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True
    )
    logging.info(f'from_={from_} | to={to} | {params_strategy}')
    StrategyClosingOnHighs.backtest_instruments_together(instruments_datas, **params_strategy)
    exit()

    """ asddas """
    all_candles = [
        await get_and_prepare_candles(instr, from_, to, CandleInterval.CANDLE_INTERVAL_1_MIN)
        for instr in instruments
    ]

    for c_day_change in [0, 1, 2, 3, 4]:
        data_feeds = [DataFeedCandles.from_candles(candles, TimeFrame.Minutes) for candles in all_candles]
        pack_instruments_datas(instruments, data_feeds)
        instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
        logging.info(f'Packed {len(instruments_datas)} data feeds')

        params_strategy = ParamsClosingOnHighs(
            sizer=MySizer(trade_max_size=0.05),
            c_day_change=c_day_change,
            c_nearly_to_high=0.5,
            min_days_changes=10,
            days_look_back=30,
            trade_end_of_main_session=True,
            trade_end_of_evening_session=True
        )
        logging.info(f'from_={from_} | to={to} | {params_strategy}')
        StrategyClosingOnHighs.backtest_instruments_together(instruments_datas, **params_strategy)


async def main():
    to = datetime(year=2024, month=2, day=23, tzinfo=TZ_UTC)
    # to = datetime(year=2022, month=11, day=16, tzinfo=TZ_UTC)
    from_ = datetime(year=2022, month=4, day=1, tzinfo=TZ_UTC)
    StrategyClosingOnHighs.LOGGING = False
    # StrategyClosingOnHighs.PLOTTING = True

    await backtest_single(from_=from_, to=to)
    # await backtest_multiple(from_=from_, to=to)


