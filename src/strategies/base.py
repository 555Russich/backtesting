from multiprocessing import cpu_count
from typing import Literal
import logging

from backtrader import (
    num2date,
    Strategy,
    Trade,
    Order,
    Cerebro
)
from backtrader.analyzers import SharpeRatio
from backtrader.utils.py3 import string_types
from my_tinkoff.date_utils import dt_form_sys

from src.schemas import StrategyResult, InstrumentData
from src.data_feeds import DataFeedCandles


BuyOrSell = Literal['buy', 'sell']


class MyStrategy(Strategy):
    START_CASH: int = 100_000
    COMMISSION: float = .0004

    def __init__(self):
        self.cheating = self.cerebro.p.cheat_on_open
        if self.p.sizer is not None:
            self.sizer = self.p.sizer

        # self.balance: float = self.START_CASH
        self.order = None
        self.trades: list[Trade] = []

    @classmethod
    def backtest_instruments_together(
            cls,
            instruments_datas: list[InstrumentData],
            is_plotting: bool = False,
            **params
    ) -> StrategyResult:
        cerebro = cls._prepare_cerebro()
        cerebro.addstrategy(cls, **params)

        for instrument_data in instruments_datas:
            cerebro.adddata(data=instrument_data.data_feed, name=instrument_data.ticker)

        strats = cerebro.run()
        strategy_result = StrategyResult(
            ticker='+'.join([instr.ticker for instr in instruments_datas]),
            start_cash=cls.START_CASH,
            trades=strats[0].trades,
            sharpe_ratio=strats[0].analyzers.sharpe.get_analysis()['sharperatio']
        )
        logging.info(strategy_result)

        if is_plotting:
            cerebro.plot(style='candlestick')

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
                    logging.debug(f'{data._name} | Duplicated order will be rejected | dt={num2date(dt)}')
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
        core_numbers = cpu_count() // 4 * 3
        cerebro = Cerebro(maxcpus=core_numbers)
        cerebro.broker.set_cash(cls.START_CASH)
        cerebro.broker.setcommission(cls.COMMISSION)
        cerebro.addanalyzer(SharpeRatio, _name='sharpe')
        return cerebro
