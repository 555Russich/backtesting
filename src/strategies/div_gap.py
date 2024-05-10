import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from tinkoff.invest import (
    CandleInterval,
    Instrument,
    Dividend,
    InstrumentIdType,
    Quotation
)
from my_tinkoff.date_utils import DateTimeFactory, TZ_UTC
from my_tinkoff.api_calls.instruments import get_dividends
from my_tinkoff.helpers import quotation2decimal

from src.multitasking import async_get_instruments_by_tickers
from src.helpers import get_data_feed
from src.schemas import StrategyData, InstrumentData
from src.backtester import Backtester
from src.strategies.base import BaseStrategy
from src.params import ParamsDivGap
from src.sizers import SizerPercentOfCash


@dataclass
class DividendDeviation:
    last_buy_date: datetime
    price_close: float
    percent_yield: float
    price_next: float | None = None

    @property
    def true_price(self) -> float:
        return self.price_close * (1 - (self.percent_yield * 0.87))

    @property
    def deviation(self) -> float:
        return (self.price_next - self.true_price) / self.true_price


class StrategyDivGap(BaseStrategy):
    params = ParamsDivGap(
        sizer=SizerPercentOfCash(trade_max_size=.05),
        percent_min_div_yield=0
    )

    def __init__(self, dividends: list[Dividend]):
        first_candle_dt = self.data.datetime.date(1)
        self.dividends = [d for d in dividends if d.last_buy_date.date() >= first_candle_dt]
        self._dividends = self.dividends.copy()
        self.results: list[DividendDeviation] = []
        super().__init__()

    def next(self):
        date = self.data.datetime.date(0)
        prev_date = self.data.datetime.date(-1)

        if self.dividends:
            closest_div = self.dividends[0]
            div_date = closest_div.last_buy_date.date()
        else:
            div_date = self.results[-1].last_buy_date

        # print(f'prev_date={prev_date} | date={date} | div_date={div_date}')
        if date == div_date:
            dd = DividendDeviation(
                last_buy_date=date,
                price_close=self.data.close[0],
                percent_yield=quotation2decimal(closest_div.yield_value) / 100,
            )
            self.results.append(dd)
        elif prev_date == div_date:
            dd = self.results[-1]
            dd.price_next = self.data.open[0]
            self.dividends.pop(0)

        if len(self.data) == self.data.buflen():
            dd_dates = [d.last_buy_date.date() for d in self._dividends]
            res_dates = [r.last_buy_date for r in self.results]
            for dd_date in dd_dates:
                assert dd_date in res_dates, dd_date

            for r in self.results:
                assert r.last_buy_date in dd_dates
                assert r.price_next, r
                assert r.deviation, r

            assert len(self.results) == len(self._dividends), \
                f'{len(self.results)=} | {len(self._dividends)=}'

async def backtest(from_: datetime, to: datetime, params_strategy: ParamsDivGap):
    # async with MOEX() as moex:
    #     tickers = await moex.get_index_composition('IMOEX')
    tickers = ['LKOH']

    deviations = {}
    instruments = await async_get_instruments_by_tickers(tickers=tickers)

    for instrument in instruments:
        # if instrument.first_1day_candle_date <= from_:
        #     print(f'{instrument.ticker} | first_candle={instrument.first_1day_candle_date} < from_={from_}')

        # print(instrument)
        dividends = await get_dividends(instrument_id=instrument.uid, from_=from_, to=to)
        if not dividends:
            continue
        dividends.sort(key=lambda x: x.last_buy_date)

        for d in dividends:
            if instrument.ticker == 'MGNT':
                if d.last_buy_date.date() == datetime(2021, 1, 6).date():
                    d.last_buy_date = datetime(2021, 1, 5, 0, 0)
                elif d.last_buy_date.date() == datetime(2019, 6, 12).date():
                    d.last_buy_date = datetime(2019, 6, 11, 0, 0)
            elif instrument.ticker == 'CHMF':
                if d.last_buy_date.date() == datetime(2020, 6, 12).date():
                    d.last_buy_date = datetime(2020, 6, 11, 0, 0)
                    d.yield_value = Quotation(units=5, nano=71)
                elif d.last_buy_date.date() == datetime(2021, 5, 28).date():
                    d.yield_value = Quotation(units=4, nano=73)
            elif instrument.ticker == 'GMKN':
                if d.last_buy_date.date() == datetime(2022, 6, 13).date():
                    d.last_buy_date = d.last_buy_date.replace(day=9)
            elif instrument.ticker == 'NLMK':
                if d.last_buy_date.date() == datetime(2020, 1, 7).date():
                    d.last_buy_date = d.last_buy_date.replace(day=6)
            elif instrument.ticker == 'NVTK':
                if d.last_buy_date.date() == datetime(2022, 5, 3).date():
                    d.last_buy_date = d.last_buy_date.replace(day=29, month=4)
            elif instrument.ticker == 'SELG':
                if d.last_buy_date.date() == datetime(2020, 6, 24).date():
                    d.last_buy_date = d.last_buy_date.replace(day=23)
            elif instrument.ticker == 'FLOT':
                if d.last_buy_date.date() == datetime(2024, 4 ,1).date():
                    d.last_buy_date = d.last_buy_date.replace(day=2)
            elif instrument.ticker == 'SBER':
                if d.last_buy_date.date() == datetime(2019, 6, 11).date():
                    d.last_buy_date = d.last_buy_date.replace(day=10)
            elif instrument.ticker == 'SBERP':
                if d.last_buy_date.date() == datetime(2019, 6, 11).date():
                    d.last_buy_date = d.last_buy_date.replace(day=10)

            print(d)
        data_feed = await get_data_feed(instrument=instrument, from_=from_, to=to,
                                        interval=CandleInterval.CANDLE_INTERVAL_DAY)
        backtester = Backtester(
            instruments_data=[InstrumentData(ticker=instrument.ticker, data_feed=data_feed)],
            strategies_data=
            [StrategyData(strategy=StrategyDivGap, params=params_strategy, kwargs={'dividends': dividends})],
        )
        backtester.run()

        strategy = backtester.strategies[0]
        if strategy.results:
            average_deviation = sum([dd.deviation for dd in strategy.results]) / len(strategy.results)
            deviations[instrument.ticker] = average_deviation
            for r in strategy.results:
                print(r, r.deviation)

    for k, v in sorted(deviations.items(), key=lambda x: abs(x[1]), reverse=True):
        print(f'Ticker: {k} | Average deviation={round(v*100, 2)}%')


async def main():
    to = datetime(2024, 5, 10, tzinfo=UTC)
    from_ = to - timedelta(days=365*5)
    print(f'FROM={from_} | TO={to}')

    params_strategy = ParamsDivGap(
        sizer=SizerPercentOfCash(trade_max_size=.99),
        percent_min_div_yield=0,
    )
    await backtest(from_=from_, to=to, params_strategy=params_strategy)
