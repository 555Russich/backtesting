import logging
import sys
from pathlib import Path
from datetime import datetime

from my_tinkoff_investments.date_utils import TZ_MOSCOW


def get_logger(filepath: Path) -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        encoding='utf-8',
        format="[{asctime},{msecs:03.0f}]:[{levelname}]:{message}",
        datefmt='%d.%m.%Y %H:%M:%S',
        style='{',
        handlers=[
            logging.FileHandler(filepath, mode='a'),
            logging.StreamHandler(sys.stdout),
        ]
    )

    logging.Formatter.converter = lambda *args: datetime.now(tz=TZ_MOSCOW).timetuple()
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('tinkoff').setLevel(logging.WARNING)
    logging.getLogger('grpc').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('market_data').setLevel(logging.WARNING)
