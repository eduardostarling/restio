from typing import Tuple

import pytest

from restio.query import query


@query
async def ArgsQuery(arg1: int, arg2: int = 2, *, transaction) -> Tuple[str, int]:
    return (transaction, arg2)


@query
async def ArgsQuery2(arg1: int, arg2: int = 2, *, transaction) -> Tuple[str, int]:
    return (transaction, arg2)


@query
async def QueryNoTransaction(arg1: int) -> Tuple[int]:
    return (arg1,)


class TestQueryCache:
    def test_hash(self):
        q = ArgsQuery(arg1=1, arg2=2)
        h = hash((q._get_function(), ("arg1", 1), ("arg2", 2)))

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

        assert q1, 1 != 2

    @pytest.mark.asyncio
    async def test_query_result(self):
        q = ArgsQuery(arg1=1, arg2=2)

        assert await q("text") == ("text", 2)

    @pytest.mark.asyncio
    async def test_query_manual_transaction(self):
        q = ArgsQuery(arg1=1, arg2=2, transaction="text")

        assert await q == ("text", 2)

    @pytest.mark.asyncio
    async def test_query_manual_transaction_overwrite(self):
        q = ArgsQuery(arg1=1, arg2=2, transaction="text")

        assert await q("overwrite") == ("overwrite", 2)

    @pytest.mark.asyncio
    async def test_query_no_transaction(self):
        q = QueryNoTransaction(arg1=1)

        assert await q("text") == (1,)

    @pytest.mark.asyncio
    async def test_query_missing_transaction(self):
        q = ArgsQuery(arg1=1, arg2=2)

        with pytest.raises(RuntimeError):
            await q
