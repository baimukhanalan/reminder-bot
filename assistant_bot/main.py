import asyncio
import logging

from .bot import run_bot
from .config import load_settings


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_bot(load_settings()))


if __name__ == "__main__":
    run()

