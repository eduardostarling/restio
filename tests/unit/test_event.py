import pytest

from restio.event import EventListener


class DummyObject:
    called = False

    def __init__(self, value):
        self.value = value
        self.calls = 0

    def method(self):
        self.calls += 1
        return self.value

    def ghost_method(self):
        DummyObject.called = True


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
    def syncfunc(self, obj, value):
        def func():
            obj.calls += 1
            return value
        return func

    def test_subscribe_method(self, listener, event, value, obj):
        listener.subscribe(event, obj.method)

        assert event in listener._listener

        weak_method = listener._listener[event].pop()
        method = weak_method()
        assert obj.method == method
        assert method is not None
        assert method() == value
        assert obj.calls == 1

    def test_subscribe_function(self, listener, value, event, obj, syncfunc):
        listener.subscribe(event, syncfunc)

        assert event in listener._listener

        method = listener._listener[event].pop()
        assert syncfunc == method
        assert method() == value
        assert obj.calls == 1

    def test_unsubscribe(self, listener, value, event, syncfunc, obj):
        listener.subscribe(event, obj.method)
        listener.subscribe(event, syncfunc)
        assert len(listener._listener[event]) == 2
        listener.unsubscribe(event, obj.method)
        assert len(listener._listener[event]) == 1
        listener.unsubscribe(event, syncfunc)
        assert not listener._listener[event]

    def test_subscribe_invalid(self, listener, event, obj):
        with pytest.raises(ValueError):
            listener.subscribe("", obj.method)
        with pytest.raises(TypeError):
            listener.subscribe(event, "var")
        with pytest.raises(TypeError):
            listener.subscribe(event, obj)

    def test_unsubscribe_invalid(self, listener, event, obj):
        listener.subscribe(event, obj.method)
        assert len(listener._listener) == 1
        assert len(listener._listener[event]) == 1
        listener.unsubscribe(f"{event}X", obj.method)
        assert len(listener._listener) == 1
        assert len(listener._listener[event]) == 1

    def test_dispatch(self, listener, value, event, syncfunc, obj):
        event2 = "mysecondevent"
        event3 = "mythirdevent"

        listener.subscribe(event, obj.method)
        listener.subscribe(event, syncfunc)
        listener.subscribe(event2, syncfunc)
        listener.dispatch(event)
        assert obj.calls == 2
        listener.dispatch(event2)
        assert obj.calls == 3
        listener.dispatch(event3)
        assert obj.calls == 3

    def test_dispatch_deleted(self, listener, event):
        obj = DummyObject("val")
        listener.subscribe(event, obj.ghost_method)
        del obj
        listener.dispatch(event)
        assert not DummyObject.called
