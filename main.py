import asyncio
import logging

from config import FILEPATH_LOGGER
from src.my_logging import get_logger


async def main():
    from src.strategies.closing_on_highs import main as submain
    # from src.strategies.pair_spread import main as submain
    await submain()


if __name__ == "__main__":
    get_logger(FILEPATH_LOGGER)

    try:
        asyncio.run(main())
    except Exception as ex:
        logging.error(ex, exc_info=True)
        exit(1)
