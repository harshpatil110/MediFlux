"""Application logging configuration with correlation ID context tracing."""

import logging
import sys
from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    """Retrieve current correlation ID from context."""
    return correlation_id_ctx.get()


def set_correlation_id(corr_id: str) -> None:
    """Set correlation ID in context."""
    correlation_id_ctx.set(corr_id)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured console logging with correlation ID tracing."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | "
        "%(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(logging.Formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]


logger = logging.getLogger("mediflux")
