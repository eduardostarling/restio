from typing import Tuple
from .base import TestBase

from restio.query import Query


@Query
async def ArgsQuery(self, arg1: int, arg2: int = 2) -> Tuple[str, int]:
    return (self, arg2)


@Query
async def ArgsQuery2(self, arg1: int, arg2: int = 2) -> Tuple[str, int]:
    return (self, arg2)


class TestQueryCache(TestBase):

    def test_hash(self):
        q = ArgsQuery(arg1=1, arg2=2)
        h = hash(tuple([q._get_function(), ('arg1', 1), ('arg2', 2)]))

        self.assertEqual(q.__hash__(), h)

    def test_query(self):
        q1 = ArgsQuery(arg2=2, arg1=1)
        q2 = ArgsQuery(1, 2)
        q3 = ArgsQuery(1, arg2=2)
        q4 = ArgsQuery2(1, 2)

        self.assertEqual(q1, q2)
        self.assertEqual(q2, q3)
        self.assertEqual(q1, q3)

        self.assertNotEqual(q1, q4)
        self.assertNotEqual(q2, q4)
        self.assertNotEqual(q3, q4)

        self.assertNotEqual(q1, (1, 2))

    @TestBase.async_test
    async def test_query_result(self):
        q = ArgsQuery(arg1=1, arg2=2)

        self.assertEqual(await q("text"), ("text", 2))

    def test_invalid_query(self):
        with self.assertRaises(AttributeError):
            @Query
            async def QueryNoSelf(arg1, arg2):
                pass

            QueryNoSelf(1, 2)

        with self.assertRaises(AttributeError):
            @Query
            async def QueryWrongSelf(arg1, arg2, self):
                pass

            QueryWrongSelf(1, 2, "text")
