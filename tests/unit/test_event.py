
import pytest

from restio.event import EventListener


class DummyObject:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    async def method(self):
        self.calls += 1
        return self.value


class TestEventListener:

    @pytest.fixture
    def listener(self) -> EventListener:
        return EventListener()

    @pytest.fixture
    def event(self) -> str:
        return "myevent"

    @pytest.fixture
    def value(self) -> str:
        return "value"

    @pytest.fixture
    def obj(self, value) -> DummyObject:
        return DummyObject(value)

    @pytest.fixture
    def asyncfunc(self, value, obj):
        async def asyncfunc():
            return await obj.method()
        return asyncfunc

    @pytest.mark.asyncio
    async def test_subscribe_method(self, listener, event, value, obj):
        listener.subscribe(event, obj.method)

        assert event in listener._listener

        weak_method = listener._listener[event].pop()
        method = weak_method()
        assert obj.method == method
        assert method is not None
        assert await method() == value
        assert obj.calls == 1

    @pytest.mark.asyncio
    async def test_subscribe_function(self, listener, value, event, obj, asyncfunc):
        listener.subscribe(event, asyncfunc)

        assert event in listener._listener

        method = listener._listener[event].pop()
        assert asyncfunc == method
        assert await method() == value
        assert obj.calls == 1

    def test_unsubscribe(self, listener, value, event, asyncfunc, obj):
        listener.subscribe(event, obj.method)
        listener.subscribe(event, asyncfunc)
        assert len(listener._listener[event]) == 2
        listener.unsubscribe(event, obj.method)
        assert len(listener._listener[event]) == 1
        listener.unsubscribe(event, asyncfunc)
        assert not listener._listener[event]

    @pytest.mark.asyncio
    async def test_dispatch(self, listener, value, event, asyncfunc, obj):
        def syncfunc():
            obj.calls += 1
        event2 = "mysecondevent"

        listener.subscribe(event, obj.method)
        listener.subscribe(event, asyncfunc)
        listener.subscribe(event, syncfunc)
        listener.subscribe(event2, syncfunc)
        await listener.dispatch(event)
        assert obj.calls == 3
        await listener.dispatch(event2)
        assert obj.calls == 4
