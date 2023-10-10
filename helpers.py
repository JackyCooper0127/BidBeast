import functools
import time

import httpx


def ssl_retry(func):
    limit = 15
    name = func.__name__
    while limit:
        try:
            return func()
        except httpx.ConnectTimeout:
            limit -= 1
            print(f"Attempting to execute `{name}")
        finally:
            raise NotImplementedError("Uncaught error when attempting to connect to SSL.")
    raise RuntimeError(f"Reached retry limit for `{name}")


def retry_on_error(max_retries=15, retry_delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Error occurred: {str(e)}")
                    time.sleep(retry_delay)
            raise Exception(f"Max retries ({max_retries}) exceeded")

        return wrapper

    return decorator
