import unittest
import asyncio
from functools import wraps


class TestBase(unittest.TestCase):
    @staticmethod
    def async_test(coro):
        @wraps(coro)
        def wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            loop.set_debug(True)
            return loop.run_until_complete(coro(*args, **kwargs))
        return wrapper
