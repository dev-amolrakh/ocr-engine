import asyncio
import functools
from typing import TypeVar, Callable
import structlog

log = structlog.get_logger()

F = TypeVar("F", bound=Callable)


def async_retry(max_retries: int = 3, base_delay: float = 1.0,
                max_delay: float = 30.0, exceptions: tuple = (Exception,)):
    """
    Async exponential backoff retry decorator.
    Retries the decorated async function on specified exceptions.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        log.warning("retry_attempt",
                                    func=func.__name__,
                                    attempt=attempt + 1,
                                    max_retries=max_retries,
                                    delay=delay,
                                    error=str(e))
                        await asyncio.sleep(delay)
                    else:
                        log.error("retry_exhausted",
                                  func=func.__name__,
                                  max_retries=max_retries,
                                  error=str(e))
            raise last_exception
        return wrapper
    return decorator
