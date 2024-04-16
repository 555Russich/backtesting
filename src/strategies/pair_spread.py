from datetime import datetime

from tinkoff.invest import InstrumentIdType
from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.csv_candles import CSVCandles
from my_tinkoff.date_utils import TZ_UTC

from src.strategies.base import BaseStrategy
from src.backtester import Backtester


class StrategyPairSpread(BaseStrategy):
    params = {}

    def __init__(self):
        ...


async def main():
    to = datetime(year=2024, month=2, day=23, tzinfo=TZ_UTC)
    from_ = datetime(year=2018, month=3, day=8, tzinfo=TZ_UTC)

    Backtester.LOGGING = False
    Backtester.PLOTTING = False

    instrument = await get_instrument_by(id='SRM4', id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER)
    print(instrument)
    # await CSVCandles.download_or_read()

    # await backtest(from_=from_, to=to, params_strategy=params_strategy)
    # await optimize(from_=from_, to=to, params_strategy=params_strategy)
