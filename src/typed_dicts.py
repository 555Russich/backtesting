from typing import TypedDict

from backtrader import TimeFrame

from src.sizers import MySizer


class ParamsClosingOnHighs(TypedDict):
    sizer: MySizer | None
    c_day_change: float
    c_nearly_to_high: float
    min_days_changes: int
    days_look_back: int
    trade_end_of_main_session: bool
    trade_end_of_evening_session: bool


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
