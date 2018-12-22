import unittest
import asyncio


class TestBase(unittest.TestCase):
    @staticmethod
    def async_test(coro):
        def wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            loop.set_debug(True)
            return loop.run_until_complete(coro(*args, **kwargs))
        return wrapper
