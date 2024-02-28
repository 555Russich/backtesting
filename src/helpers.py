from datetime import datetime

from tinkoff.invest import CandleInterval, Instrument
from backtrader import TimeFrame

from my_tinkoff.exceptions import UnexpectedCandleInterval
from my_tinkoff.schemas import Candles
from my_tinkoff.csv_candles import CSVCandles

from src.data_feeds import DataFeedCandles
from src.schemas import InstrumentData


def get_timeframe_by_candle_interval(interval: CandleInterval) -> TimeFrame:
    match interval:
        case CandleInterval.CANDLE_INTERVAL_DAY:
            return TimeFrame.Days
        case CandleInterval.CANDLE_INTERVAL_1_MIN:
            return TimeFrame.Minutes
        case _:
            raise UnexpectedCandleInterval(interval)


async def get_data_feed(
        instrument: Instrument,
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
) -> DataFeedCandles:
    candles = await get_and_prepare_candles(instrument=instrument, from_=from_, to=to, interval=interval)
    timeframe = get_timeframe_by_candle_interval(interval=interval)
    return DataFeedCandles.from_candles(candles=candles, timeframe=timeframe)


async def get_and_prepare_candles(
        instrument: Instrument,
        from_: datetime,
        to: datetime,
        interval: CandleInterval
) -> Candles:
    candles = await CSVCandles.download_or_read(instrument=instrument, from_=from_, to=to, interval=interval)
    candles.check_datetime_consistency()
    return candles.remove_weekend_and_holidays_candles()


def pack_instruments_datas(instruments: list[Instrument], data_feeds: list[DataFeedCandles]) -> list[InstrumentData]:
    return [InstrumentData(ticker=instr.ticker, data_feed=data_feed)
            for instr, data_feed in zip(instruments, data_feeds)]
