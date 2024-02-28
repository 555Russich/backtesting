import logging

from backtrader import Sizer


class MySizer(Sizer):
    params = (('trade_max_size', 0.1),)

    def _getsizing(self, comminfo, cash, data, isbuy):
        value = self.broker.get_value()
        price = data.close[0]

        if cash < value * self.p.trade_max_size:
            size = cash // price * 0.9
            logging.debug(f"{data._name} | cash={round(cash, 2)} | value={round(value, 2)} | {price=} | size={round(size, 2)}")
        elif cash <= value:
            size = cash // price * self.p.trade_max_size
        else:
            raise Exception(f"{data._name} | cash={round(cash, 2)} | value={round(value, 2)} | {price=} | size=None")
        return size