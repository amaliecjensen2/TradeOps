"""Struktureret logging via structlog.

Output format styres af LOG_FORMAT env varen: "json" til produktion (parserbar
af log aggregator) eller "console" til lokal udvikling (pænere i terminalen).
"""
import logging
import sys
import structlog
from trader_api.config import get_settings


def configure_logging() -> None:
    s = get_settings()
    # Fald tilbage til INFO hvis LOG_LEVEL er ukendt.
    level = getattr(logging, s.log_level.upper(), logging.INFO)
    # Fælles processors der altid køres: contextvars, log level og timestamp.
    shared = [structlog.contextvars.merge_contextvars,
              structlog.processors.add_log_level,
              structlog.processors.TimeStamper(fmt="iso")]
    renderer = structlog.processors.JSONRenderer(
    ) if s.log_format == "json" else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=shared +
        [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    # Wire structlog ind i standard logging så biblioteker (uvicorn, fastapi)
    # også går gennem samme formatter.
    fmt = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=shared,
    )
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(fmt)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(level)


def get_logger(name: str = "") -> structlog.BoundLogger:
    return structlog.get_logger(name)
