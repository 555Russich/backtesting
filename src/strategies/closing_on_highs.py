import logging
from datetime import datetime

from backtrader import num2date, Sizer
from tinkoff.invest import InstrumentIdType, CandleInterval, Instrument
from my_tinkoff.date_utils import DateTimeFactory, TZ_UTC
from moex_api import MOEX

from src.strategies.base import MyStrategy
from src.helpers import pack_instruments_datas
from src.sizers import MySizer
from src.multitasking import (
    async_get_instruments_by_tickers,
    multiprocessing_get_instruments_data_feeds,
)


class StrategyClosingOnHighs(MyStrategy):
    params = dict(
        sizer=None,
        coeff_change=2,
        min_days_changes=10,
        days_look_back=30,
    )

    def __init__(self):
        self.last_seen_dt: list[int] = [0 for _ in range(len(self.datas))]
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
                    if dt2.minute == 0:
                        logging.warning(f'No opening auction candle | dt1={dt1} | dt2={dt2}')
        super().__init__()

    def next(self):
        for i, data in enumerate(self.datas):
            indexes_last = self.indexes_last[i]
            i_day = self.indexes_days[i]
            days_changes = self.days_changes[i]

            # escaping index error while iterating on last day
            if len(indexes_last)-1 == i_day:
                return

            i_last_candle = indexes_last[i_day]
            i_prev_last_candle = indexes_last[i_day - 1]
            reverse_idx_prev_last = i_prev_last_candle - len(data) - 1

            # escaping index error while iterating on first day
            if len(data) < i_prev_last_candle:
                return

            if self.max_highs[i] is None or self.max_highs[i] < data.high[0]:
                self.max_highs[i] = data.high[0]

            position = self.getposition(data)

            if position:
                if len(data) == i_prev_last_candle + 1 and data.close[0] < data.close[-1]:
                    self.sell(data=data, size=position.size)
                elif len(data) == i_prev_last_candle + 2:
                    self.sell(data=data, size=position.size)

            # self.log(txt=f'{data._name} | {len(data)} | {len(self.indexes_last[i])=} | {i_day=} | {i_last_candle=} '
            #              f'| {i_prev_last_candle=} | {self.max_highs[i]=} | {data.buflen()=}', data=data)

            if len(data) in [i_last_candle, i_last_candle - 1]:
                prev_last_close = data.close[reverse_idx_prev_last]
                day_change = data.close[0] - prev_last_close
                percent_day_change = day_change / prev_last_close

                if len(data) == i_last_candle - 1:
                    if len(days_changes) < self.p.min_days_changes:
                        return
                    elif len(days_changes) >= self.p.days_look_back:
                        using_days_changes = days_changes[len(days_changes)-1-self.p.days_look_back:]
                    else:
                        using_days_changes = days_changes

                    average_day_changes = sum([abs(x) for x in using_days_changes]) / len(using_days_changes)
                    if percent_day_change > average_day_changes * self.p.coeff_change:
                        self.log(txt=f'{data._name} | percent_day_change={round(percent_day_change*100, 2)} | '
                                     f'average_day_changes={round(average_day_changes*100, 2)}', data=data)
                        self.order = self.buy(data=data)

                elif len(data) == i_last_candle:
                    days_changes.append(percent_day_change)
                    self.indexes_days[i] += 1
                    self.max_highs[i] = None


async def main():
    to = datetime(year=2024, month=2, day=23, tzinfo=TZ_UTC)
    from_ = datetime(year=2022, month=4, day=1, tzinfo=TZ_UTC)
    coeff_change = 2
    min_days_changes = 10
    days_look_back = 30
    trade_max_size = 0.1
    logging.info(f'from_={from_} | to={to} | {coeff_change=} | {min_days_changes=} | {days_look_back=} | {trade_max_size=}')

    async with MOEX() as moex:
        tickers = await moex.get_index_composition('IMOEX')
    # tickers = tickers[:3]

    instruments = await async_get_instruments_by_tickers(tickers=tickers)
    logging.info(f'Got {len(instruments)} instruments')
    data_feeds = multiprocessing_get_instruments_data_feeds(instruments=instruments, from_=from_, to=to,
                                                            interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
    logging.info(f'Packed {len(instruments_datas)} data feeds')

    StrategyClosingOnHighs.backtest_instruments_together(
        instruments_datas=instruments_datas,
        is_plotting=False,
        min_days_changes=min_days_changes,
        coeff_change=coeff_change,
        days_look_back=days_look_back,
        sizer=MySizer(trade_max_size=trade_max_size)
    )
