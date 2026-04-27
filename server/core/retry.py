from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")

class RetryConfig:
    def __init__(
        self,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
        multiplier: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.multiplier = multiplier

DEFAULT_RETRY_CONFIG = RetryConfig()

def with_retry(
    config: RetryConfig = DEFAULT_RETRY_CONFIG,
    retry_on: tuple = (Exception,),
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
            raise last_exc or Exception("Retry exhausted")
        return wrapper
    return decorator

def with_com_retry(func: Callable[..., T]) -> Callable[..., T]:
    return with_retry(
        config=RetryConfig(max_attempts=3, min_wait=0.5, max_wait=5.0),
        retry_on=(Exception,),
    )(func)

def retry_com_call(func: Callable[..., T], *args, **kwargs) -> dict:
    attempts = 0
    last_error = None

    while attempts < DEFAULT_RETRY_CONFIG.max_attempts:
        attempts += 1
        try:
            result = func(*args, **kwargs)
            return {"success": True, "result": result, "error": None, "attempts": attempts}
        except Exception as e:
            last_error = str(e)
            if attempts < DEFAULT_RETRY_CONFIG.max_attempts:
                import time
                wait_time = min(
                    DEFAULT_RETRY_CONFIG.min_wait * (DEFAULT_RETRY_CONFIG.multiplier ** (attempts - 1)),
                    DEFAULT_RETRY_CONFIG.max_wait,
                )
                time.sleep(wait_time)

    return {"success": False, "result": None, "error": last_error, "attempts": attempts}
