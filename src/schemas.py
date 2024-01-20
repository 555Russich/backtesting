from dataclasses import dataclass
from collections import UserList

from backtrader import Trade


@dataclass
class StrategyResult:
    ticker: str
    start_cash: float
    trades: list[Trade] = None
    sharpe_ratio: float | None = None

    def __repr__(self) -> str:
        return (
            f'Ticker: {self.ticker}\n'
            f'PnL: {round(self.pnlcomm, 2)} | {round(self.pnlcomm_percent*100, 2)}%\n'
            f'{self.count_successful_trades}/{len(self.trades)} successful trades | {round(self.percent_successful_trades*100, 2) if self.percent_successful_trades else None}%\n'
            f'Sharpe Ratio: {round(self.sharpe_ratio, 2) if self.sharpe_ratio else None}'
        )

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
