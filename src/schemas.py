from dataclasses import dataclass
from typing import Type, Any

from backtrader import TimeFrame

from src.data_feeds import DataFeedCandles
from src.typed_dicts import (
    AnalysisSharpe,
    AnalysisDrawDown,
    AnalysisPeriodStats
)
from src.strategies.base import BaseStrategy
from src.params import AnyParamsStrategy


@dataclass
class StrategyResult:
    strategy: Type[BaseStrategy]
    ticker: str
    start_cash: float
    sharpe: AnalysisSharpe
    drawdown: AnalysisDrawDown
    annual_return: dict[int, float]
    period_stats: AnalysisPeriodStats
    trade_analyzer: dict[str, dict]

    def __repr__(self) -> str:
        pd = self.period_stats
        ta = self.trade_analyzer
        tt = ta['total']['total']
        if tt == 0:
            return '0 Trades by this strategy'

        rows = (
            # '-' * 30,
            f'Strategy class: {self.strategy.__class__.__name__}',
            f'Ticker: {self.ticker}',
            f'PnL: {round(self.pnl_net_percent * 100, 2)}% | {round(self.pnl_net, 2)}',
            f'Winrate: {round(self.percent_successful_trades*100, 2)}% | Won {self.count_won}/{self.count_won + self.count_lost}',
            f'Sharpe Ratio: {round(self.sharpe['ratio'], 2)} (Risk free rate: {self.sharpe['risk_free_rate']}%)',
            f'Drawdown: -{round(self.drawdown['percent'], 2)}% | Length: {self.drawdown['length']}',
            f'Annual Return: [{' | '.join([f'{y}: {round(p * 100, 2)}%' for y, p in self.annual_return.items()])}]',
            f'By periods ({TimeFrame.TName(pd['timeframe'])})',
            f'  Average: {round(pd['average']*100, 2)}% | Best: {round(pd['best']*100, 2)}% | Worst: {round(pd['worst']*100, 2)}% | Stddev: {round(pd['stddev'], 5)}%',
            f'  Positive: {pd['positive']} | Negative: {pd['negative']} | No change: {pd['nochange']}',
            f'Trades Analysis:',
            f'Total: {ta['total']['total']} | Open: {ta['total']['open']} | Closed: {ta['total']['closed']}',
            f'Win streak. Current: {ta['streak']['won']['current']} | Longest={ta['streak']['won']['longest']}',
            f'Lose streak. Current: {ta['streak']['lost']['current']} | Longest={ta['streak']['lost']['longest']}',
            f'PnL Net Average: {round(ta['pnl']['net']['average'], 2)}',
            f'PnL Gross: {round(self.pnl_gross, 2)} | Average: {round(ta['pnl']['gross']['average'], 2)}',
            f'Commission: {round(self.commission, 2)} | {round(self.commission/self.pnl_net*100, 2)}%',
            f'Average won: {round(ta['won']['pnl']['average'], 2)} | Average lost {round(ta['lost']['pnl']['average'], 2)}',
            f'Max won: {round(ta['won']['pnl']['max'], 2)} | Max lost {round(ta['lost']['pnl']['max'], 2)}',
            f'Longs: {ta['long']['total']} | Won: {ta['long']['won']} | Lost: {ta['long']['lost']}',
            f'  Total: {round(ta["long"]["pnl"]['total'], 2)} | Average: {round(ta["long"]["pnl"]["average"], 2)}',
            f'Shorts: {ta['short']['total']} | Won: {ta['short']['won']} | Lost: {ta['short']['lost']}',
            f'  Total: {round(ta["short"]["pnl"]['total'], 2)} | Average: {round(ta["short"]["pnl"]["average"], 2)}',
            f'Bars in market.',
            f'Total: {ta['len']['total']} | Average: {round(ta['len']['average'], 2)} | Max: {ta['len']['max']} | Min: {ta['len']['min']}',
            # '-' * 30
        )
        return '\n'.join(rows)

    @property
    def pnl_net(self) -> float:
        return self.trade_analyzer['pnl']["net"]["total"]

    @property
    def pnl_net_percent(self) -> float:
        return self.pnl_net / self.start_cash

    @property
    def pnl_gross(self) -> float:
        return self.trade_analyzer['pnl']["gross"]["total"]

    @property
    def commission(self) -> float:
        return self.pnl_gross-self.pnl_net

    @property
    def count_won(self) -> int:
        return self.trade_analyzer['won']['total']

    @property
    def count_lost(self) -> int:
        return self.trade_analyzer['lost']['total']

    @property
    def percent_successful_trades(self) -> float:
        return self.count_won / (self.count_won + self.count_lost)


@dataclass
class InstrumentData:
    ticker: str
    data_feed: DataFeedCandles


@dataclass
class StrategyData:
    strategy: Type[BaseStrategy]
    params: AnyParamsStrategy
