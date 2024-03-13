from typing import Literal
import logging

from backtrader import (
    Strategy,
    Trade,
    Order,
)
from backtrader.utils.py3 import string_types
from my_tinkoff.date_utils import dt_form_sys

from src.data_feeds import DataFeedCandles


BuyOrSell = Literal['buy', 'sell']


class BaseStrategy(Strategy):
    LOGGING: bool

    def __init__(self):
        super().__init__()
        self.cheating = self.cerebro.p.cheat_on_open
        if self.p.sizer is not None:
            self.sizer = self.p.sizer

    def notify_order(self, order: Order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status == order.Completed:
            buy_or_sell = 'Buy' if order.isbuy() else 'Sell'
            self.log(f'{buy_or_sell} executed | Price={order.executed.price} | Cost='
                     f'{round(order.executed.value, 2)} | Comm={round(order.executed.comm, 2)}', data=order.data)
        else:
            self.log(f'Order status: {order.getstatusname()} | value={round(self.broker.get_value(), 2)} | '
                     f'cash={round(self.broker.get_cash(), 2)}', data=order.data)

    def notify_trade(self, trade: Trade):
        if trade.isclosed:
            self.log(f'PnL={round(trade.pnl, 2)} | PnLComm={round(trade.pnlcomm, 2)}', data=trade.data)

    def log(self, txt: str, data: DataFeedCandles | None = None):
        if not self.LOGGING:
            return

        if data is None:
            data = self.data

        dt = data.datetime.datetime(0)
        dt = dt_form_sys.datetime_strf(dt)
        logging.info(f'{{{dt}}} | {data._name} | {{{txt}}}')

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

    def _buy_or_sell(self, buy_or_sell: BuyOrSell, data=None, size=None, price=None, plimit=None, exectype=None,
                     valid=None, tradeid=0, oco=None, trailamount=None, trailpercent=None, parent=None, transmit=True,
                     **kwargs) -> Order | None:
        func = self.broker.buy if buy_or_sell == 'buy' else self.broker.sell

        if isinstance(data, string_types):
            data = self.getdatabyname(data)

        data = data if data is not None else self.datas[0]
        size = size if size is not None else self.getsizing(data, isbuy=buy_or_sell == 'buy')

        if size:
            dt = data.datetime[0]
            for order in self.broker.orders:
                if data._name == order.data._name and order.alive() and order.created.dt == dt and order.price == price:
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
