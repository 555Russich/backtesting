import logging
from datetime import datetime, timedelta
from collections import defaultdict

from backtrader import num2date, Order
from tinkoff.invest import CandleInterval, InstrumentIdType
from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.date_utils import TZ_UTC
from my_tinkoff.enums import ClassCode
from moex_api import MOEX

from src.strategies.base import BaseStrategy
from src.exceptions import SkipIteration
from src.sizers import SizerPercentOfCash
from src.helpers import (
    pack_instruments_datas,
    get_data_feed
)
from src.multitasking import (
    async_get_instruments_by_tickers,
    multiprocessing_get_instruments_data_feeds,
)
from src.schemas import StrategyData, InstrumentData
from src.backtester import Backtester
from src.params import ParamsClosingOnHighs


class StrategyClosingOnHighs(BaseStrategy):
    params = ParamsClosingOnHighs(
        sizer=SizerPercentOfCash(trade_max_size=0.05),
        c_price_change=4,
        c_volume_change=5,
        c_from_low=0.5,
        c_from_high=0.4,
        take_stop=(0.003, 0.001),
        days_look_back=60,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True,
        trade_before_weekends=True
    )

    def __init__(self):
        self.i = 0
        self.last_seen_dt: list[float | None] = [None for _ in range(len(self.datas))]
        self.indexes_days: list[int] = [1 for _ in range(len(self.datas))]
        self.max_highs: list[int | None] = [None for _ in range(len(self.datas))]
        self.price_changes: list[list[float]] = [[] for _ in range(len(self.datas))]
        self.volume_changes: list[dict[int, int]] = [defaultdict(int) for _ in range(len(self.datas))]
        self.indexes_last: list[list[int]] = [[] for _ in range(len(self.datas))]

        for i, data in enumerate(self.datas):
            for i_c in range(1, data.buflen()):
                dt1 = num2date(data.datetime[i_c-1])
                dt2 = num2date(data.datetime[i_c])
                if dt2.date() > dt1.date():
                    self.indexes_last[i].append(i_c-1)
                    # if dt2.minute == 0 and self.LOGGING:
                    #     logging.warning(f'{data._name} | No opening auction candle | dt1={dt1} | dt2={dt2}')

        super().__init__()

    def next(self):
        for i, data in enumerate(self.datas):
            self.i = i
            try:
                self._process_data(data)
            except SkipIteration:
                continue

    def _process_data(self, data) -> None:
        i = self.i  # shortcut
        indexes_last = self.indexes_last[i]
        i_day = self.indexes_days[i]
        self.volume_changes[i][i_day] += data.volume[0]

        # escaping index error while iterating on last day
        if len(indexes_last) - 1 == i_day:
            raise SkipIteration

        i_last_candle = indexes_last[i_day]
        i_prev_last_candle = indexes_last[i_day - 1]

        # escaping index error while iterating on first day
        if len(data) < i_prev_last_candle:
            raise SkipIteration

        dt = data.datetime.datetime(0)
        reverse_idx_prev_last = i_prev_last_candle - len(data) - 1
        prev_last_close = data.close[reverse_idx_prev_last]
        percent_day_change = (data.close[0] - prev_last_close) / prev_last_close
        volume_change = self.volume_changes[i].get(i_day)

        if len(data) == i_last_candle:
            self.price_changes[i].append(percent_day_change)
            self.indexes_days[i] += 1
            self.max_highs[i] = None

        if self.last_seen_dt[i] and data.datetime[0] <= self.last_seen_dt[i]:
            raise SkipIteration
        self.last_seen_dt[i] = data.datetime[0]

        if self.max_highs[i] is None or self.max_highs[i] < data.high[0]:
            self.max_highs[i] = data.high[0]

        if len(data) == i_last_candle - 1:
            avg_price_change, avg_volume_change = self._get_average_price_and_volume_change()
            percent_change_to_high = (self.max_highs[i] - prev_last_close) / prev_last_close

            if percent_day_change > avg_price_change * self.p.c_price_change and (
                    (volume_change > avg_volume_change * self.p.c_volume_change) and
                    (percent_change_to_high >= percent_day_change > percent_change_to_high * self.p.c_from_low)
                    and (percent_day_change <= percent_change_to_high * (1 - self.p.c_from_high)) and
                    ((self.p.trade_end_of_main_session and self.p.trade_end_of_evening_session) or
                     (self.p.trade_end_of_main_session and dt.hour == 15 and dt.minute in list(range(39, 50)) or
                     self.p.trade_end_of_evening_session and dt.hour == 20 and dt.minute == 48))
                    and (self.p.trade_before_weekends or (
                    not self.p.trade_before_weekends and data.datetime.datetime(2) - dt < timedelta(days=1)))
            ):
                price_take = data.close[0] * (1 + self.p.take_stop[0])
                price_stop = data.close[0] * (1 - self.p.take_stop[1])
                self.buy_bracket(data=data, exectype=Order.Market, limitprice=price_take, stopprice=price_stop)
                self.log(
                    f'close_price={data.close[0]} | '
                    f'price_take={round(price_take, 2)} | '
                    f'price_stop={round(price_stop, 2)} | '
                    f'percent_day_change={round(percent_day_change * 100, 2)} | '
                    f'average_day_changes={round(avg_price_change * 100, 2)} | '
                    f'percent_change_to_high={round(percent_change_to_high * 100, 2)} | '
                    f'volume_change={volume_change} | '
                    f'avg_volume_change={round(avg_volume_change, 2)}',
                    data=data
                )

    def _get_average_price_and_volume_change(self) -> tuple[float, float]:
        days_changes = self.price_changes[self.i]
        volume_changes = self.volume_changes[self.i]
        # assert len(days_changes) == len(volume_changes), f'{len(days_changes)} != {len(volume_changes)}'

        if len(days_changes) < self.params.days_look_back:
            raise SkipIteration

        idx = len(days_changes)-1 - self.p.days_look_back
        arr_prices = days_changes[idx:]
        arr_volumes = [volume_changes[i] for i in range(max(volume_changes.keys()))]
        avg_price = sum([abs(x) for x in arr_prices]) / len(arr_prices)
        avg_volume = sum(arr_volumes) / len(arr_volumes)
        return avg_price, avg_volume


async def backtest(from_: datetime, to: datetime, params_strategy: ParamsClosingOnHighs) -> None:
    ticker = 'GAZP'
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
    assert Backtester.PLOTTING is False

    async with MOEX() as moex:
        tickers = await moex.get_index_composition('IMOEX')
    # tickers = ['SBER']

    instruments = [i for i in await async_get_instruments_by_tickers(tickers=tickers)
                   if i.first_1min_candle_date <= from_]
    logging.info(f'Start collecting data for {len(instruments)} instruments')
    data_feeds = multiprocessing_get_instruments_data_feeds(instruments=instruments, from_=from_, to=to,
                                                            interval=CandleInterval.CANDLE_INTERVAL_1_MIN)
    instruments_datas = pack_instruments_datas(instruments=instruments, data_feeds=data_feeds)
    logging.info(f'from_={from_} | to={to}\n{params_strategy} | Packed {len(instruments_datas)} data feeds')

    backtester = Backtester(
        instruments_data=instruments_datas,
        strategies_data=[StrategyData(strategy=StrategyClosingOnHighs, params=params_strategy)],
    )
    backtester.optimize()


async def main():
    to = datetime(year=2024, month=2, day=23, tzinfo=TZ_UTC)
    # from_ = datetime(year=2023, month=1, day=1, tzinfo=TZ_UTC)

    # to = datetime(year=2018, month=10, day=5, tzinfo=TZ_UTC)
    from_ = datetime(year=2018, month=3, day=8, tzinfo=TZ_UTC)

    Backtester.LOGGING = True
    Backtester.PLOTTING = True
    params_strategy = ParamsClosingOnHighs(
        sizer=SizerPercentOfCash(trade_max_size=0.05),
        c_price_change=4,
        c_volume_change=3,
        c_from_low=0,
        c_from_high=0,
        take_stop=[(.003, .001)],
        days_look_back=60,
        trade_end_of_main_session=True,
        trade_end_of_evening_session=True,
        trade_before_weekends=True
    )

    await backtest(from_=from_, to=to, params_strategy=params_strategy)
    # await optimize(from_=from_, to=to, params_strategy=params_strategy)

