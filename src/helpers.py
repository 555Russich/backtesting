from tinkoff.invest import CandleInterval
from backtrader import TimeFrame

from my_tinkoff.exceptions import UnexpectedCandleInterval


def get_timeframe_by_candle_interval(interval: CandleInterval) -> TimeFrame:
    match interval:
        case CandleInterval.CANDLE_INTERVAL_DAY:
            return TimeFrame.Days
        case CandleInterval.CANDLE_INTERVAL_1_MIN:
            return TimeFrame.Minutes
        case _:
            raise UnexpectedCandleInterval(interval)
