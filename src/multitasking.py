import asyncio
from datetime import datetime
from multiprocessing import Pool, cpu_count

from tinkoff.invest import Instrument, InstrumentIdType, CandleInterval

from my_tinkoff.api_calls.instruments import get_instrument_by
from my_tinkoff.schemas import ClassCode

from src.data_feeds import DataFeedCandles
from src.helpers import get_data_feed


async def async_get_instruments_by_tickers(tickers: list[str]) -> list[Instrument]:
    tasks = []
    for ticker in tickers:
        coro = get_instrument_by(id=ticker, id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                                 class_code=ClassCode.TQBR)
        task = asyncio.create_task(coro)
        tasks.append(task)
    return list(await asyncio.gather(*tasks))


async def async_get_instruments_data_feeds(
        instruments: list[Instrument],
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
) -> list[DataFeedCandles]:
    tasks = []
    for instrument in instruments:
        coro = get_data_feed(instrument=instrument, from_=from_, to=to, interval=interval)
        task = asyncio.create_task(coro)
        tasks.append(task)
    return list(await asyncio.gather(*tasks))


def sync_get_data_feed(instrument: Instrument, from_: datetime,
                       to: datetime, interval: CandleInterval) -> DataFeedCandles:
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(get_data_feed(instrument=instrument, from_=from_, to=to, interval=interval))
    return res


def multiprocessing_get_instruments_data_feeds(
        instruments: list[Instrument],
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
) -> list[DataFeedCandles]:
    args_for_pool = [(i, from_, to, interval) for i in instruments]
    with Pool(processes=cpu_count()) as pool:
        return pool.starmap(sync_get_data_feed, args_for_pool)
