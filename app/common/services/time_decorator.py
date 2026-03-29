from loguru import logger

import time

def time_it(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.debug(f"Function Name {func.__name__} Time : {end - start} in seconds")
        return result
    return wrapper
