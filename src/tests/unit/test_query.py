from typing import Tuple

import pytest

from restio.query import query


@query
async def ArgsQuery(self, arg1: int, arg2: int = 2) -> Tuple[str, int]:
    return (self, arg2)


@query
async def ArgsQuery2(self, arg1: int, arg2: int = 2) -> Tuple[str, int]:
    return (self, arg2)


class TestQueryCache:

    def test_hash(self):
        q = ArgsQuery(arg1=1, arg2=2)
        h = hash(tuple([q._get_function(), ('arg1', 1), ('arg2', 2)]))

        assert q.__hash__() == h

    def test_query(self):
        q1 = ArgsQuery(arg2=2, arg1=1)
        q2 = ArgsQuery(1, 2)
        q3 = ArgsQuery(1, arg2=2)
        q4 = ArgsQuery2(1, 2)

        assert q1 == q2
        assert q2 == q3
        assert q1 == q3

        assert q1 != q4
        assert q2 != q4
        assert q3 != q4

        assert q1, (1 != 2)

    @pytest.mark.asyncio
    async def test_query_result(self):
        q = ArgsQuery(arg1=1, arg2=2)

        assert await q("text"), ("text" == 2)

    def test_invalid_query(self):
        with pytest.raises(AttributeError):
            @query
            async def QueryNoSelf(arg1, arg2):
                pass

            QueryNoSelf(1, 2)

        with pytest.raises(AttributeError):
            @query
            async def QueryWrongSelf(arg1, arg2, self):
                pass

            QueryWrongSelf(1, 2, "text")
