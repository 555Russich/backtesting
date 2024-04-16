import logging
from math import floor

from backtrader import Sizer, CommissionInfo

from src.params import ParamsSizerPercentOfCash


class SizerPercentOfCash(Sizer):
    params = ParamsSizerPercentOfCash(trade_max_size=0.1)

    def _getsizing(self, comminfo: CommissionInfo, cash, data, isbuy):
        value = self.broker.get_value()
        price = data.close[0]

        if cash < value * self.params.trade_max_size:
            size = cash // price * 0.9
        elif cash <= value:
            size = cash // price * self.params.trade_max_size
        else:
            # it probably means short position
            # return 0
            raise Exception(f"{data._name} | cash={round(cash, 2)} | value={round(value, 2)} | {price=} | size=None")

        size = size // 1
        # logging.debug(f"{data._name} | cash={round(cash, 2)} | value={round(value, 2)} | {price=} | size="
        #               f"{round(size, 2)}")
        return size
