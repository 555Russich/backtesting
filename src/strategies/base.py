from datetime import datetime
import logging

from backtrader import (
    Strategy,
    Trade,
    Order
)

from my_tinkoff.date_utils import dt_form_sys


class MyStrategy(Strategy):
    def __init__(self):
        self.order = None
        self.limit_order = None
        self.trades: list[Trade] = []

    def get_max_size(self, price: float) -> int:
        return self.broker.get_value() // price

    def log(self, txt: str, dt: datetime | None = None):
        if dt is None:
            dt = self.datas[0].datetime.datetime(0)

        dt = dt_form_sys.datetime_strf(dt)
        logging.info(f'{{{dt}}} {{{txt}}}')

    def notify_order(self, order: Order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'Buy executed | Price={order.executed.price} | Cost={order.executed.value} | '
                         f'Comm={order.executed.comm}')
            elif order.issell():
                self.log(f'Sell executed | Price={order.executed.price} | Cost={order.executed.value} | '
                         f'Comm={order.executed.comm}')
        else:
            self.log(f'Order status: {order.Status[order.status]}')

        # no pending order
        self.order = None

    def notify_trade(self, trade: Trade):
        if trade.isclosed:
            self.trades.append(trade)
            self.log(f'{trade.pnl=} | {trade.pnlcomm=}')
