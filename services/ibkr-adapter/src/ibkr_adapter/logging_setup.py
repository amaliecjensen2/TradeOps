"""Struktureret logging opsætning via structlog.

Kald configure_logging() én gang ved procesopstart.
Alle andre moduler importerer `get_logger` og kalder det på modulniveau.
"""

# Importerer Pythons indbyggede logging-system.
import logging
import sys  # der hvor loggen bliver skrevet ud til

# Importerer structlog som laver strukturede logs
import structlog

# Henter runtime-konfiguration, fx logniveau og logformat.
from ibkr_adapter.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    # Oversætter tekst som "INFO" til logging.INFO; falder tilbage til INFO hvis værdien er ukendt.
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list = [   # Processors er små trin, som alle logevents går igennem før de bliver skrevet ud.
        # Fletter eventuel kontekst fra contextvars ind i logeventet.
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Hvis konfigurationen siger json, bruges JSON-rendering af logs.
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        # Renderer logeventet som menneskelæselig tekst i terminalen.
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(  # Konfigurerer structlog globalt for hele processen.
        processors=shared_processors + [  # Definerer kæden af processors som structlog-events skal igennem.
            # Pakker eventet, så stdlib formatteren kan færdigbehandle det senere.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Opretter loggere som automatisk filtrerer efter valgt logniveau.
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        # Sørger for at ikke-structlog logs også får samme basale felter som timestamp og level.
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)

    for noisy in ("ib_insync", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str = "") -> structlog.BoundLogger:
    return structlog.get_logger(name)
