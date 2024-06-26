from dataclasses import dataclass, asdict
from typing import TypeVar, Union

from backtrader import Sizer, TimeFrame

S = TypeVar('S', bound=Sizer)


@dataclass
class _Iterable:
    def __iter__(self):
        return iter(asdict(self).items())


@dataclass
class ParamsSizerPercentOfCash(_Iterable):
    trade_max_size: float


@dataclass
class ParamsClosingOnHighs(_Iterable):
    c_price_change: list[int] | int
    c_volume_change: list[int] | int
    c_from_low: float | list[float]
    c_from_high: float | list[float]
    take_stop: tuple[float, float] | list[tuple[float, float]]
    days_look_back: int | list[int]
    trade_end_of_main_session: bool | list[bool]
    trade_end_of_evening_session: bool | list[bool]
    trade_before_weekends: bool | list[bool]
    sizer: S | None


@dataclass
class ParamsSharpe(_Iterable):
    timeframe: TimeFrame
    compression: int
    riskfreerate: float
    factor: None | int
    convertrate: bool
    annualize: bool
    stddev_sample: bool


@dataclass
class ParamsPeriodStats(_Iterable):
    timeframe: TimeFrame
    compression: int
    fund: bool | None


@dataclass
class ParamsDivGap(_Iterable):
    percent_min_div_yield: float
    sizer: S = None


AnyParamsStrategy = Union[
    ParamsClosingOnHighs,
    ParamsDivGap
]
