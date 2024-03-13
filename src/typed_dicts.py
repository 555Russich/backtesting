from typing import TypedDict, Iterable, NamedTuple

from backtrader import TimeFrame

from src.sizers import SizerPercentOfCash


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
