import logging
from datetime import datetime, timedelta

from tinkoff.invest import (
    TradeDirection,
    InstrumentIdType,
    CandleInterval,
    Instrument,
)
import backtrader as bt
from my_tinkoff.date_utils import DateTimeFactory, dt_form_sys
from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.csv_candles import CSVCandles
from my_tinkoff.schemas import Shares

from config import FILEPATH_LOGGER
from src.my_logging import get_logger
from src.data_feeds import MyCSVData
from src.strategies.base import MyStrategy
from src.helpers import get_timeframe_by_candle_interval
from src.schemas import StrategyResult, StrategiesResults


get_logger(FILEPATH_LOGGER)


class StrategyLongTrendBreakDown(MyStrategy):
    def __init__(self, min_count_bars: int | None = None):
        self.closes: bt.LineBuffer = self.data.close
        self.opens: bt.LineBuffer = self.data.open
        self.highs = self.data.high
        self.lows = self.data.low

        self.changes: bt.linebuffer.LinesOperation = self.closes - self.opens  # noqa
        self.min_count_bars = min_count_bars
        self.max_count_bars = 0
        super().__init__()

    def next(self):
        if len(self.closes) <= self.min_count_bars:
            return

        if self.position:
            if self.position.size < 0:
                self.buy(size=self.position.size)
            elif self.position.size > 0:
                self.sell(size=self.position.size)

            if self.limit_order:
                self.broker.cancel(self.limit_order)
                self.limit_order = None

        if dt_form_sys.datetime_strf(self.datas[0].datetime.datetime(0)) == '02.06.2009 23:59:59':
            pass

        changes = self.changes.get(ago=-1, size=len(self.closes)-1)
        count_bars_in_a_row, trend_direction = self.get_count_bars_in_a_row_with_direction(changes)

        if count_bars_in_a_row < self.min_count_bars:
            return
        elif count_bars_in_a_row > self.max_count_bars:
            self.max_count_bars = count_bars_in_a_row
            # self.log(f'Updating {self.max_count_bars=}')

        # spec_count_bars = int(self.max_count_bars * 0.5)
        spec_count_bars = self.min_count_bars

        if spec_count_bars <= count_bars_in_a_row >= self.min_count_bars:
            change = self.changes[0]
            changes_in_a_row = [abs(x) for x in changes[-count_bars_in_a_row:]]
            avg_change = sum(changes_in_a_row) / count_bars_in_a_row
            self.log(f'{count_bars_in_a_row=} | {spec_count_bars=} | {avg_change=}')
            # if abs(change) < avg_change:
            #     self.log(f'{avg_change=} | actual_change={abs(change)}')
            #     return

            order_size = self.get_max_size(self.closes[0]) // 2
            if trend_direction == TradeDirection.TRADE_DIRECTION_BUY and change < 0:
                self.order = self.sell(size=order_size)
                # order_price = self.closes[0] - self.closes[0] * 0.01
                # print(f'{order_price=}')
                # self.limit_order = self.buy(exectype=bt.Order.Limit, price=order_price)
            elif trend_direction == TradeDirection.TRADE_DIRECTION_SELL and change > 0:
                self.order = self.buy(size=order_size)
                # order_price = self.closes[0] + self.closes[0] * 0.01
                # print(f'{order_price=}')
                # self.limit_order = self.sell(exectype=bt.Order.Limit, price=order_price)

    def get_count_bars_in_a_row_with_direction(self, changes: list) -> tuple[int, TradeDirection]:
        direction = TradeDirection.TRADE_DIRECTION_UNSPECIFIED
        count_bars_in_a_row = 0

        for c in reversed(changes):
            if c == 0:
                continue

            if direction == TradeDirection.TRADE_DIRECTION_UNSPECIFIED:
                if c > 0:
                    direction = TradeDirection.TRADE_DIRECTION_BUY
                else:
                    direction = TradeDirection.TRADE_DIRECTION_SELL
            elif (c > 0 and direction == TradeDirection.TRADE_DIRECTION_SELL) or (
                    c < 0 and direction == TradeDirection.TRADE_DIRECTION_BUY):
                break
            count_bars_in_a_row += 1
        return count_bars_in_a_row, direction


async def backtest_one_instrument(
        instrument: Instrument,
        start_cash: int,
        comm: float,
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
        min_count_bars: int
) -> StrategyResult | None:
    candles = await CSVCandles.download_or_read(instrument=instrument, from_=from_, to=to, interval=interval)
    if not candles:
        return None
    candles.check_datetime_consistency()
    timeframe = get_timeframe_by_candle_interval(interval)

    cerebro = bt.Cerebro()
    cerebro.broker.set_cash(start_cash)
    cerebro.broker.setcommission(comm)

    filepath = CSVCandles.get_filepath(instrument, interval=interval)
    data = MyCSVData(dataname=filepath, fromdate=from_, todate=to, timeframe=timeframe)
    cerebro.adddata(data)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addstrategy(StrategyLongTrendBreakDown, min_count_bars=min_count_bars)

    strats = cerebro.run()
    # logging.info(cerebro.broker.get_value())
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
    interval = CandleInterval.CANDLE_INTERVAL_DAY
    to = DateTimeFactory.now()
    # to -= timedelta(days=365*7)
    from_ = to - timedelta(days=365)
    print(f'FROM={from_} | TO={to}')
    start_cash = 100_000
    comm = .0004
    min_count_bars = 8

    instrument = await get_instrument_by(id='POSI', id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER, class_code='TQBR')
    strategy_result = await backtest_one_instrument(
        instrument=instrument,
        start_cash=start_cash,
        comm=comm,
       # from_=instrument.first_1day_candle_date,
        from_=from_,
        to=to,
        interval=interval,
        min_count_bars=min_count_bars
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
            min_count_bars=min_count_bars
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
