import asyncio
from datetime import datetime, timedelta

from config import FILEPATH_LOGGER
from src.my_logging import get_logger, TZ
from src.api_calls import (
    get_dividends,
    get_shares
)
from src.converter import Converter

YEARS_BACK = 5


async def get_highest_dividends_shares():
    shares = await get_shares()

    ru_shares_with_dividends = [
        share for share in shares
        if share.div_yield_flag and
        share.country_of_risk == 'RU' and
        share.currency == 'rub' and
        not share.for_qual_investor_flag
    ]

    best_shares_by_divs = []
    for share in ru_shares_with_dividends:
        dividends = await get_dividends(
            figi=share.figi,
            from_=share.first_1day_candle_date,
            to=datetime.now()
        )

        dt_now = datetime.now(tz=TZ)
        dt_3_years_ago = dt_now.replace(year=dt_now.year-YEARS_BACK)
        divs_last_3_years = [d for d in dividends if d.last_buy_date > dt_3_years_ago]

        if divs_last_3_years and dt_now - divs_last_3_years[-1].last_buy_date < timedelta(days=365):
            avg_yield = sum([Converter.quotation2decimal(d.yield_value) for d in divs_last_3_years])
            last_pay = divs_last_3_years[-1].last_buy_date.strftime("%d.%m.%Y")
            share_with_div_yield = (share.ticker, round(avg_yield/3, 2), last_pay)
            best_shares_by_divs.append(share_with_div_yield)

    best_shares_by_divs.sort(key=lambda x: x[1], reverse=True)
    print(f'{len(best_shares_by_divs)=}')
    for i, d in enumerate(best_shares_by_divs):
        print(f'№:{i} {d[0]} | Avg yield={d[1]}%')


async def main():
    await get_highest_dividends_shares()
    exit()


if __name__ == '__main__':
    get_logger(FILEPATH_LOGGER)
    asyncio.run(main())
