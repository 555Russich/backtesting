import logging
from datetime import datetime, timedelta

from tinkoff.invest import (
    CandleInterval,
    Instrument,
    Dividend,
    InstrumentIdType
)
from moex_api import MOEX
from backtrader import (
    Trade,
    Cerebro,
)
from backtrader.analyzers import SharpeRatio

from my_tinkoff.date_utils import DateTimeFactory
from my_tinkoff.api_calls.instruments import get_dividends, get_instrument_by
from my_tinkoff.helpers import quotation2decimal
from my_tinkoff.csv_candles import CSVCandles
from my_tinkoff.schemas import Shares

from src.data_feeds import MyCSVData
from src.helpers import get_timeframe_by_candle_interval
from src.schemas import StrategyResult, StrategiesResults
from src.strategies.base import MyStrategy


class StrategyDivGap(MyStrategy):
    def __init__(self, dividends: list[Dividend], count_days: int, percent_min_div_yield: float):
        self.order = None
        self.limit_order = None
        self.trades: list[Trade] = []

        self.changes: bt.linebuffer.LinesOperation = self.data.close - self.data.open  # noqa
        self.count_days = count_days
        self.dividends_dates = []
        for d in dividends:
            percent_yield = quotation2decimal(d.yield_value)
            if percent_yield > percent_min_div_yield:
                self.dividends_dates.append(d.last_buy_date.date())

        super().__init__()

    def next(self):
        if self.position:
            if self.position.size < 0:
                self.buy(size=self.position.size)
            elif self.position.size > 0:
                self.sell(size=self.position.size)

        date = self.data.datetime.datetime(0).date()
        if date in self.dividends_dates:
            size = self.get_max_size(price=self.data.close) // 2
            self.order = self.sell(size=size)


async def backtest_one_instrument(
        instrument: Instrument,
        start_cash: int,
        comm: float,
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
        count_days: int,
        percent_min_div_yield: float
) -> StrategyResult | None:
    candles = await CSVCandles.download_or_read(instrument=instrument, from_=from_, to=to, interval=interval)
    dividends = await get_dividends(instrument=instrument, from_=from_, to=to)
    if not candles or not dividends:
        return None
    candles.check_datetime_consistency()

    cerebro = Cerebro()
    cerebro.broker.set_cash(start_cash)
    cerebro.broker.setcommission(comm)

    filepath = CSVCandles.get_filepath(instrument, interval=interval)
    timeframe = get_timeframe_by_candle_interval(interval)
    data = MyCSVData(dataname=filepath, fromdate=from_, todate=to, timeframe=timeframe)
    cerebro.adddata(data)

    cerebro.addanalyzer(SharpeRatio, _name='sharpe')
    cerebro.addstrategy(
        strategy=StrategyDivGap,
        count_days=count_days,
        dividends=dividends,
        percent_min_div_yield=percent_min_div_yield
    )

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
    start_cash = 100_000
    comm = .0004

    interval = CandleInterval.CANDLE_INTERVAL_DAY
    to = DateTimeFactory.now()
    # to -= timedelta(days=365*2)
    from_ = to - timedelta(days=365*5)
    print(f'FROM={from_} | TO={to}')
    count_days = 1
    percent_min_div_yield = 3

    instrument = await get_instrument_by(id='GAZP', id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER, class_code='TQBR')
    strategy_result = await backtest_one_instrument(
        instrument=instrument,
        start_cash=start_cash,
        comm=comm,
        # from_=instrument.first_1day_candle_date,
        from_=from_,
        to=to,
        interval=interval,
        count_days=count_days,
        percent_min_div_yield=percent_min_div_yield
    )
    exit()

    instruments = await Shares.from_IMOEX()
    strategies_results = []
    for instrument in instruments:
        strategy_result = await backtest_one_instrument(
            instrument=instrument,
            start_cash=start_cash,
            comm=comm,
            from_=from_,
            # from_=instrument.first_1day_candle_date,
            to=to,
            interval=interval,
            count_days=count_days,
            percent_min_div_yield=percent_min_div_yield
        )
        if strategy_result:
            strategies_results.append(strategy_result)

    results_with_trades = [r for r in strategies_results if r.trades]
    results_sorted_by_successful_trades = sorted(results_with_trades, key=lambda x: x.pnlcomm)
    for s in results_sorted_by_successful_trades:
        print(s)
        print()

    results = StrategiesResults(results_with_trades)
    print(results)
