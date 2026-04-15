try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker

    _DRAMATIQ_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without dramatiq installed
    dramatiq = None
    RedisBroker = None
    _DRAMATIQ_AVAILABLE = False

from app.infrastructure.config.settings import get_settings

settings = get_settings()
_broker_configured = False


def is_dramatiq_enabled() -> bool:
    return settings.queue_driver.lower() == "dramatiq" and _DRAMATIQ_AVAILABLE


def configure_broker() -> None:
    global _broker_configured
    if _broker_configured or not is_dramatiq_enabled():
        return

    if RedisBroker is None or dramatiq is None:
        return

    broker = RedisBroker(url=settings.redis_url)
    dramatiq.set_broker(broker)
    _broker_configured = True
