import logging

from backtrader import Cerebro, OptReturn, TimeFrame
from backtrader.analyzers import SharpeRatio, AnnualReturn, TimeDrawDown, PeriodStats, TradeAnalyzer
from btplotting import BacktraderPlotting

from src.schemas import InstrumentData
from src.strategies.base import BaseStrategy
from src.schemas import StrategyData, StrategyResult
from src.params import ParamsSharpe, ParamsPeriodStats
from src.typed_dicts import (
    AnalysisSharpe,
    AnalysisDrawDown,
    AnalysisPeriodStats,
)


class Backtester:
    START_CASH: int = 1_000_000
    COMMISSION: float = .0004
    LOGGING: bool = True
    PLOTTING: bool = False
    CPU_CORES_COUNT: int = 1

    params_sharpe = ParamsSharpe(
        timeframe=TimeFrame.Days,
        compression=1,
        riskfreerate=0,
        factor=None,
        convertrate=True,
        annualize=True,
        stddev_sample=False,
    )
    params_period_stats = ParamsPeriodStats(
        timeframe=TimeFrame.Months,
        compression=1,
        fund=None,
    )

    def __init__(self, strategies_data: list[StrategyData], instruments_data: list[InstrumentData]):
        self._instruments_data = instruments_data
        self._strategies_data = strategies_data

        for sd in strategies_data:
            sd.strategy.LOGGING = self.LOGGING

    def run(self) -> list[StrategyResult]:
        cerebro = self._setup_cerebro()

        for sd in self._strategies_data:
            for k, v in sd.params:
                if isinstance(v, list):
                    if len(v) == 1:
                        setattr(sd.params, k, v[0])
                    else:
                        raise Exception(f'Parameter {k} has list value: {v}')

            cerebro.addstrategy(sd.strategy, **sd.params.__dict__)
        for instrument_data in self._instruments_data:
            cerebro.adddata(data=instrument_data.data_feed, name=instrument_data.ticker)

        strategies = cerebro.run(maxcpus=self.CPU_CORES_COUNT)
        results = []
        for strategy in strategies:
            ticker = '+'.join([instr.ticker for instr in self._instruments_data])
            res = self._get_strategy_result(strategy=strategy, ticker=ticker)
            logging.info(f'\nparams={strategy.params.__dict__}\n{res}')
            results.append(res)

            if self.PLOTTING:
                # plotter = BacktraderPlotting(style='bar')
                # cerebro.plot(plotter)
                cerebro.plot(style='candlestick')
        return results

    def optimize(self) -> list[StrategyResult]:
        cerebro = self._setup_cerebro()

        for sd in self._strategies_data:
            for instrument_data in self._instruments_data:
                cerebro.adddata(data=instrument_data.data_feed, name=instrument_data.ticker)
            cerebro.optstrategy(sd.strategy, **sd.params.__dict__)

        strategies = cerebro.run(maxcpus=self.CPU_CORES_COUNT)

        results = []
        for strategy in strategies:
            for opt_return in strategy:
                ticker = '+'.join([instr.ticker for instr in self._instruments_data])
                res = self._get_strategy_result(strategy=strategy.__class__, opt_return=opt_return, ticker=ticker)
                logging.info(f'\nparams={opt_return.params.__dict__}\n{res}')
                results.append(res)
        return results

    @classmethod
    def _setup_cerebro(cls) -> Cerebro:
        cerebro = Cerebro()
        cerebro.broker.set_cash(cls.START_CASH)
        cerebro.broker.setcommission(commission=cls.COMMISSION, leverage=1)
        cerebro.addanalyzer(SharpeRatio, _name='sharpe', **cls.params_sharpe.__dict__)
        cerebro.addanalyzer(AnnualReturn, _name='annual_return')
        cerebro.addanalyzer(TimeDrawDown, _name='drawdown')
        cerebro.addanalyzer(PeriodStats, _name='period_stats', **cls.params_period_stats.__dict__)
        cerebro.addanalyzer(TradeAnalyzer, _name='trade_analyzer')
        return cerebro

    @classmethod
    def _get_strategy_result(
            cls,
            strategy: BaseStrategy,
            ticker: str,
            opt_return: OptReturn | None = None
    ) -> StrategyResult:
        a = opt_return.analyzers if opt_return else strategy.analyzers
        dd = a.drawdown.get_analysis()
        return StrategyResult(
            strategy=strategy.__class__,
            ticker=ticker,
            start_cash=cls.START_CASH,
            sharpe=AnalysisSharpe(ratio=a.sharpe.ratio, risk_free_rate=a.sharpe.p.riskfreerate),
            drawdown=AnalysisDrawDown(percent=dd['maxdrawdown'], length=dd['maxdrawdownperiod']),
            annual_return=a.annual_return.get_analysis(),
            period_stats=AnalysisPeriodStats(
                timeframe=cls.params_period_stats.timeframe,
                **a.period_stats.get_analysis()
            ),
            trade_analyzer=a.trade_analyzer.get_analysis()
        )
