"""Structured logging."""
import logging
import sys
import structlog
from strategy_hello.config import get_settings


def configure_logging() -> None:
    s = get_settings()
    level = getattr(logging, s.log_level.upper(), logging.INFO)
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
