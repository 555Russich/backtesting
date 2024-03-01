from multiprocessing import cpu_count
from typing import Literal
import logging

from backtrader import (
    Strategy,
    Trade,
    Order,
    Cerebro,
    TimeFrame
)
from backtrader.analyzers import (
    SharpeRatio,
    AnnualReturn,
    TimeDrawDown,
    PeriodStats,
    TradeAnalyzer,
)
from backtrader.utils.py3 import string_types
from my_tinkoff.date_utils import dt_form_sys

from src.schemas import StrategyResult, InstrumentData
from src.data_feeds import DataFeedCandles
from src.typed_dicts import (
    ParamsSharpe,
    ParamsPeriodStats,
    AnalysisSharpe,
    AnalysisDrawDown,
    AnalysisPeriodStats,
)


BuyOrSell = Literal['buy', 'sell']


class MyStrategy(Strategy):
    START_CASH: int = 1_000_000
    COMMISSION: float = .0004
    LOGGING: bool = True
    PLOTTING: bool = False
    USING_CORES: int = cpu_count() // 4 * 3

    params_sharpe = ParamsSharpe(
        timeframe=TimeFrame.Days,
        compression=1,
        riskfreerate=0,
        factor=None,
        convertrate=True,
        annualize=True,
        stddev_sample=False,
    )
    params_period_stats = ParamsPeriodStats(
        timeframe=TimeFrame.Months,
        compression=1,
        fund=None,
    )

    def __init__(self):
        self.cheating = self.cerebro.p.cheat_on_open
        if self.p.sizer is not None:
            self.sizer = self.p.sizer

        self.order = None
        self.trades: list[Trade] = []

    @classmethod
    def backtest_instruments_together(cls, instruments_datas: list[InstrumentData], **params) -> StrategyResult:
        cerebro = cls._prepare_cerebro()
        cerebro.addstrategy(cls, **params)

        for instrument_data in instruments_datas:
            cerebro.adddata(data=instrument_data.data_feed, name=instrument_data.ticker)

        strats = cerebro.run()
        analyzers = strats[0].analyzers
        sharpe = analyzers.sharpe
        sharpe_analysis = AnalysisSharpe(ratio=sharpe.ratio, risk_free_rate=sharpe.p.riskfreerate)
        annual_return_analysis = analyzers.annual_return.get_analysis()
        drawdown = analyzers.drawdown.get_analysis()
        drawdown_analysis = AnalysisDrawDown(percent=drawdown['maxdrawdown'], length=drawdown['maxdrawdownperiod'])
        period_stats_analysis = analyzers.period_stats.get_analysis()
        period_stats = AnalysisPeriodStats(timeframe=cls.params_period_stats['timeframe'], **period_stats_analysis)
        trade_analyzer = analyzers.trade_analyzer.get_analysis()

        strategy_result = StrategyResult(
            ticker='+'.join([instr.ticker for instr in instruments_datas]),
            start_cash=cls.START_CASH,
            trades=strats[0].trades,
            sharpe=sharpe_analysis,
            drawdown=drawdown_analysis,
            annual_return=annual_return_analysis,
            period_stats=period_stats,
            trade_analyzer=trade_analyzer
        )
        logging.info(f'\n{strategy_result}')

        cerebro.plot(style='candlestick') if cls.PLOTTING else None
        return strategy_result

    @classmethod
    def backtest_instruments_separately(cls):
        pass

    def buy(self, data=None, size=None, price=None, plimit=None, exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None, parent=None, transmit=True, **kwargs
            ) -> Order | None:
        return self._buy_or_sell(
            buy_or_sell='buy', data=data, size=size, price=price, plimit=plimit, exectype=exectype, valid=valid,
            tradeid=tradeid, oco=oco, trailamount=trailamount, trailpercent=trailpercent, parent=parent,
            transmit=transmit, **kwargs
        )

    def sell(self, data=None, size=None, price=None, plimit=None, exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None, parent=None, transmit=True, **kwargs
            ) -> Order | None:
        return self._buy_or_sell(
            buy_or_sell='sell', data=data, size=size, price=price, plimit=plimit, exectype=exectype, valid=valid,
            tradeid=tradeid, oco=oco, trailamount=trailamount, trailpercent=trailpercent, parent=parent,
            transmit=transmit, **kwargs
        )

    def get_max_size(self, price: float) -> int:
        return self.broker.get_value() // price

    def log(self, txt: str, data: DataFeedCandles | None = None):
        if not self.LOGGING:
            return

        if data is None:
            data = self.data

        dt = data.datetime.datetime(0)
        dt = dt_form_sys.datetime_strf(dt)
        logging.info(f'{{{dt}}} {{{txt}}}')

    def notify_order(self, order: Order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        name = order.data._name
        if order.status == order.Completed:
            buy_or_sell = 'Buy' if order.isbuy() else 'Sell'
            # self.log(f'{buy_or_sell} executed | cash={round(cash, 2)} | Price={order.executed.price} | Cost='
            self.log(f'{name} | {buy_or_sell} executed | Price={order.executed.price} | Cost='
                     f'{round(order.executed.value, 2)} | Comm={round(order.executed.comm, 2)}')
        else:
            self.log(f'{name} | Order status: {order.getstatusname()} | {self.broker.get_value()=} | {self.broker.get_cash()=}')

        # no pending order
        self.order = None

    def notify_trade(self, trade: Trade):
        if trade.isclosed:
            self.trades.append(trade)
            self.log(f'{trade.data._name} | PnL={round(trade.pnl, 2)} | PnLComm={round(trade.pnlcomm, 2)}')

    def _buy_or_sell(self, buy_or_sell: BuyOrSell, data=None, size=None, price=None, plimit=None, exectype=None,
                     valid=None, tradeid=0, oco=None, trailamount=None, trailpercent=None, parent=None, transmit=True,
                     **kwargs) -> Order | None:
        func = self.broker.buy if buy_or_sell == 'buy' else self.broker.sell

        if isinstance(data, string_types):
            data = self.getdatabyname(data)

        data = data if data is not None else self.datas[0]
        size = size if size is not None else self.getsizing(data, isbuy=True)

        if size:
            dt = data.datetime[0]
            for order in self.broker.orders:
                if data._name == order.data._name and order.alive() and order.created.dt == dt:
                    self.log(f'{data._name} | Duplicated order will be rejected', data=data)
                    return

            return func(
                self, data,
                size=abs(size), price=price, plimit=plimit,
                exectype=exectype, valid=valid, tradeid=tradeid, oco=oco,
                trailamount=trailamount, trailpercent=trailpercent,
                parent=parent, transmit=transmit,
                **kwargs)

        return None

    @classmethod
    def _prepare_cerebro(cls) -> Cerebro:
        cerebro = Cerebro(maxcpus=cls.USING_CORES)
        cerebro.broker.set_cash(cls.START_CASH)
        cerebro.broker.setcommission(cls.COMMISSION)

        cerebro.addanalyzer(SharpeRatio, _name='sharpe', **cls.params_sharpe)
        cerebro.addanalyzer(AnnualReturn, _name='annual_return')
        cerebro.addanalyzer(TimeDrawDown, _name='drawdown')
        cerebro.addanalyzer(PeriodStats, _name='period_stats', **cls.params_period_stats)
        cerebro.addanalyzer(TradeAnalyzer, _name='trade_analyzer')

        return cerebro
