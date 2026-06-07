"""Indgangspunkt."""
import asyncio
import signal
from strategy_nvidia.strategy import NvidiaStrategy
from strategy_nvidia.config import get_settings


async def _main() -> None:
    settings = get_settings()
    strategy = NvidiaStrategy(settings)
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGTERM, lambda: setattr(strategy, "_running", False))
    loop.add_signal_handler(
        signal.SIGINT, lambda: setattr(strategy, "_running", False))
    await strategy.run()


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
