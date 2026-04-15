import logging
from logging.config import dictConfig

from app.infrastructure.config.settings import get_settings
from app.infrastructure.http.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    settings = get_settings()

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id_filter": {
                "()": RequestIdFilter,
            }
        },
        "formatters": {
            "json": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": (
                    "%(asctime)s %(levelname)s %(name)s %(message)s "
                    "%(request_id)s %(pathname)s %(lineno)d"
                ),
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "json",
                "filters": ["request_id_filter"],
            }
        },
        "root": {"level": settings.log_level, "handlers": ["default"]},
    }

    dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

