from dataclasses import dataclass
from collections import UserList

from backtrader import Trade, TimeFrame

from src.data_feeds import DataFeedCandles
from src.typed_dicts import (
    AnalysisSharpe,
    AnalysisDrawDown,
    AnalysisPeriodStats
)


@dataclass
class StrategyResult:
    ticker: str
    start_cash: float
    sharpe: AnalysisSharpe
    drawdown: AnalysisDrawDown
    annual_return: dict[int, float]
    period_stats: AnalysisPeriodStats
    trade_analyzer: dict[str, dict]
    trades: list[Trade] = None

    def __repr__(self) -> str:
        pd = self.period_stats
        txt = (
            f'Ticker: {self.ticker}\n'
            f'PnL: {round(self.pnlcomm, 2)} | {round(self.pnlcomm_percent*100, 2)}%\n'
            f'{self.count_successful_trades}/{len(self.trades)} successful trades | {round(self.percent_successful_trades*100, 2) if self.percent_successful_trades else None}%\n'
            f'Sharpe Ratio: {round(self.sharpe['ratio'], 2)} (Risk free rate: {self.sharpe['risk_free_rate']})\n'
            f'Drawdown: {round(self.drawdown['percent'], 2)}% | Length: {self.drawdown['length']}\n'
            f'Annual Return: [{' | '.join([f'{y}: {round(p * 100, 2)}%' for y, p in self.annual_return.items()])}]\n'
            f'By {TimeFrame.TName(pd['timeframe'])}. '
            f'Average: {round(pd['average']*100, 2)} | Best: {round(pd['best']*100, 2)} | Worst: {round(pd['worst']*100, 2)} | Stddev: {round(pd['stddev'], 5)}\n'
            f'Positive: {pd['positive']} | Negative: {pd['negative']} | No change: {pd['nochange']}\n'

        )
        ta = self.trade_analyzer
        if ta['total']['total']:
            trades_analysis = (
                f'Trades Analysis:\n'
                f'Total: {ta['total']['total']} | Open: {ta['total']['open']} | Closed: {ta['total']['closed']}\n'
                f'Win streak. Current: {ta['streak']['won']['current']} | Longest={ta['streak']['won']['longest']}\n'
                f'Lose streak. Current: {ta['streak']['lost']['current']} | Longest={ta['streak']['lost']['longest']}\n'
                f'PnL Net. Total: {round(ta['pnl']["net"]["total"], 2)} | Average: {round(ta['pnl']['net']['average'], 2)}\n'
                f'PnL Gross. Total: {round(ta['pnl']["gross"]["total"], 2)} | Average: {round(ta['pnl']['gross']['average'], 2)}\n'
                f'Count Won/Lost: {ta['won']['total']}/{ta['lost']['total']}\n'
                f'Average won: {round(ta['won']['pnl']['average'], 2)} | Average lost {round(ta['lost']['pnl']['average'], 2)}\n'
                f'Max won: {round(ta['won']['pnl']['max'], 2)} | Max lost {round(ta['lost']['pnl']['max'], 2)}\n'
                f'Longs: {ta['long']['total']} | Won: {ta['long']['won']} | Lost: {ta['long']['lost']}\n'
                f'  Total: {round(ta["long"]["pnl"]['total'], 2)} | Average: {round(ta["long"]["pnl"]["average"], 2)}\n'
                f'Shorts: {ta['short']['total']} | Won: {ta['short']['won']} | Lost: {ta['short']['lost']}\n'
                f'  Total: {round(ta["short"]["pnl"]['total'], 2)} | Average: {round(ta["short"]["pnl"]["average"], 2)}\n'
                f'Bars in market.\n'
                f'Total: {ta['len']['total']} | Average: {ta['len']['average']} | Max: {ta['len']['max']} | Min: {ta['len']['min']}'
            )
        else:
            trades_analysis = ''
        return '\n'.join(['-'*30, txt, trades_analysis, '-'*30])

    @property
    def pnlcomm(self) -> float:
        return sum(t.pnlcomm for t in self.trades)

    @property
    def pnlcomm_percent(self) -> float:
        return self.pnlcomm / self.start_cash

    @property
    def count_successful_trades(self) -> int:
        return len([1 for t in self.trades if t.pnlcomm > 0])

    @property
    def percent_successful_trades(self) -> float | None:
        if len(self.trades):
            return self.count_successful_trades / len(self.trades)


class StrategiesResults(UserList[StrategyResult]):

    def __repr__(self) -> str:
        return (
            f'Cumulative of {len(self)} strategies results\n'
            f'PnL: {round(self.pnlcomm, 2)} | {round(self.pnlcomm_percent*100, 2)}%\n'
            f'{self.count_successful_trades}/{len(self.trades)} successful trades | {round(self.percent_successful_trades*100, 2) if self.percent_successful_trades else None}%\n'
            f'Average Sharpe Ratio: {round(self.sharpe_ratio, 2) if self.sharpe_ratio else None}'
        )

    @property
    def pnlcomm(self) -> float:
        return sum([r.pnlcomm for r in self])

    @property
    def pnlcomm_percent(self) -> float:
        return sum([r.pnlcomm_percent for r in self])

    @property
    def trades(self) -> list[Trade]:
        return [t for r in self for t in r.trades]

    @property
    def count_successful_trades(self) -> int:
        return len([1 for t in self.trades if t.pnlcomm > 0])

    @property
    def percent_successful_trades(self) -> float | None:
        if self.trades:
            return self.count_successful_trades / len(self.trades)

    @property
    def sharpe_ratio(self) -> float | None:
        sharpe_ratios = [r.sharpe_ratio for r in self if r.sharpe_ratio]
        if sharpe_ratios:
            return sum(sharpe_ratios) / len(sharpe_ratios)

    def sort_by_pnl(self) -> None:
        self.sort(key=lambda x: x.pnlcomm)


@dataclass
class InstrumentData:
    ticker: str
    data_feed: DataFeedCandles
