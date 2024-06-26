from typing import Literal
import logging
from collections import defaultdict

from backtrader import (
    Strategy,
    Trade,
    Order,
)
from my_tinkoff.date_utils import dt_form_sys

from src.data_feeds import DataFeedCandles


BuyOrSell = Literal['buy', 'sell']


class BaseStrategy(Strategy):
    LOGGING: bool

    def __init__(self):
        self.cheating = self.cerebro.p.cheat_on_open
        self.p = self.params

        if self.p.sizer is not None:
            self.sizer = self.p.sizer

        self._trade_values = defaultdict(lambda: 0)

        super().__init__()
        logging.info(f'{self.__class__.__name__}\n{self.params.__dict__}')

    def notify_order(self, order: Order):
        # logging.info(order)
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status == order.Completed:
            buy_or_sell = 'Buy' if order.isbuy() else 'Sell'
            self.log(f'{buy_or_sell} executed | Price={order.executed.price} | Cost='
                     f'{round(order.executed.value, 2)} | Comm={round(order.executed.comm, 2)}', data=order.data)
        elif order.status == order.Canceled:
            return
        else:
            self.log(f'Order status: {order.getstatusname()} | value={round(self.broker.get_value(), 2)} | '
                     f'cash={round(self.broker.get_cash(), 2)}', data=order.data)

    def notify_trade(self, trade: Trade):
        if trade.justopened:
            self._trade_values[trade.data] += trade.value

        if trade.isclosed:
            pnl_perc = trade.pnl / self._trade_values[trade.data]
            pnlcomm_perc = trade.pnlcomm / self._trade_values[trade.data]
            self._trade_values[trade.data] = 0

            self.log(f'PnL={round(trade.pnl, 2)} ({round(pnl_perc*100, 2)}%) | PnLComm={round(trade.pnlcomm, 2)} '
                     f'({round(pnlcomm_perc*100, 2)}%)', data=trade.data)

    def log(self, txt: str, data: DataFeedCandles | None = None):
        if not self.LOGGING:
            return

        if data is None:
            data = self.data

        dt = data.datetime.datetime(0)
        dt = dt_form_sys.datetime_strf(dt)
        logging.info(f'{{{dt}}} | {data._name} | {txt}')
