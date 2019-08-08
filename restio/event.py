import types
import weakref
from typing import Any, Callable, Dict, Optional, Set, Union

ListeningMethod = Union[weakref.WeakMethod, types.FunctionType]


class EventListener:
    _listener: Dict[str, Set[ListeningMethod]]

    def __init__(self):
        self._listener = {}

    def subscribe(self, event: str, method: Callable[..., Any]):
        if not event:
            raise ValueError("You must specify a valid event name.")

        weak_method = self._reference_method(method)
        self._listener.setdefault(event, set())
        self._listener[event].add(weak_method)

    def unsubscribe(self, event: str, method: Callable[..., Any]):
        weak_method = self._reference_method(method)
        if event in self._listener and weak_method in self._listener[event]:
            self._listener[event].remove(weak_method)

    def _reference_method(self, method: Callable[..., Any]) -> ListeningMethod:
        if isinstance(method, types.MethodType):
            return weakref.WeakMethod(method)
        elif isinstance(method, types.FunctionType):
            return method
        else:
            raise TypeError(
                "The parameter `method` must be either a method or a function")

    def dispatch(self, event: str, *args, **kwargs):
        if event in self._listener:
            for weak_method in self._listener[event]:
                method = self._resolve_reference(weak_method)
                if not method:
                    continue

                method(*args, **kwargs)

    def _resolve_reference(self, reference: ListeningMethod) -> Optional[Callable[..., Any]]:
        if isinstance(reference, weakref.WeakMethod):
            return reference()
        else:
            return reference
