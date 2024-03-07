from typing import TypedDict, Iterable

from backtrader import TimeFrame

from src.sizers import SizerPercentOfCash


class ParamsClosingOnHighs(TypedDict):
    sizer: SizerPercentOfCash | None
    c_day_change: float | Iterable[float]
    c_nearly_to_high: float | Iterable[float]
    days_look_back: int | Iterable[int]
    take_stop: tuple[float, float] | Iterable[tuple[float, float]]
    trade_end_of_main_session: bool | Iterable[bool]
    trade_end_of_evening_session: bool | Iterable[bool]


class ParamsSharpe(TypedDict):
    timeframe: TimeFrame
    compression: int
    riskfreerate: float
    factor: None | int
    convertrate: bool
    annualize: bool
    stddev_sample: bool


class ParamsPeriodStats(TypedDict):
    timeframe: TimeFrame
    compression: int
    fund: bool | None


class AnalysisSharpe(TypedDict):
    ratio: float
    risk_free_rate: float


class AnalysisDrawDown(TypedDict):
    percent: float
    length: int


class AnalysisPeriodStats(TypedDict):
    timeframe: TimeFrame
    average: float
    stddev: float
    positive: int
    negative: int
    nochange: int
    best: float
    worst: float
