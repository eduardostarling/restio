import types
import weakref
from typing import Any, Callable, Dict, Optional, Set, Union

ListeningMethod = Union[weakref.WeakMethod, types.FunctionType]


class EventListener:
    """
    Event listener class.

    The events registered in EventListener objects are identified by a string hash
    `event` using the method `subscribe`. The callback functions provided can be normal
    functions or instance methods. Coroutine functions are not supported.

    Callbacks are synchronously triggered by `dispatch` when they match the `event`
    hash. The order in which callbacks are triggered is not deterministic. Extra
    arguments passed to args and kwargs are then propagated to the stored callbacks.

    Methods are stored internally with the wrapper WeakMethod in order to allow for
    garbage collection of instances that are no longer in use. Methods that have been
    garbage collected are ignored if eventually dispatched.
    """

    _listener: Dict[str, Set[ListeningMethod]]

    def __init__(self):
        self._listener = {}

    def subscribe(self, event: str, method: Callable[..., Any]):
        """
        Subscribes the callback `method` to the event `event`.

        :param event: The event hash.
        :param method: The callback method.
        :raises ValueError: If no event name is provided.
        """
        if not event:
            raise ValueError("You must specify a valid event name.")

        weak_method = self._reference_method(method)
        self._listener.setdefault(event, set())
        self._listener[event].add(weak_method)

    def unsubscribe(self, event: str, method: Callable[..., Any]):
        """
        Unsubscribes the callback `method` from the event `event`.

        :param event: The event hash.
        :param method: The callback method.
        """
        weak_method = self._reference_method(method)
        if event in self._listener and weak_method in self._listener[event]:
            self._listener[event].remove(weak_method)

    def _reference_method(self, method: Callable[..., Any]) -> ListeningMethod:
        if isinstance(method, types.MethodType):
            return weakref.WeakMethod(method)  # type: ignore
        elif isinstance(method, types.FunctionType):
            return method  # type: ignore
        else:
            raise TypeError(
                "The parameter `method` must be either a method or a function"
            )

    def dispatch(self, event: str, *args, **kwargs):
        """
        Synchronously dispatches all callbacks stored with a particular `event` hash.
        `args` and `kwargs` are optional and are passed to the callbacks, therefore
        they should match the signature of all callbacks stored for the event. Errors
        should be handled by the callbacks properly, otherwise raised exceptions will
        interrupt the dispatching and will be propagated back to the caller.

        :param event: The event hash.
        :param args: The positional arguments to be passed into the subscribed methods.
        :param kwargs: The keyword arguments to be passed into the subscribed methods.
        """
        if event in self._listener:
            for weak_method in self._listener[event]:
                method = self._resolve_reference(weak_method)
                if not method:
                    continue

                method(*args, **kwargs)

    def _resolve_reference(
        self, reference: ListeningMethod
    ) -> Optional[Callable[..., Any]]:
        if isinstance(reference, weakref.WeakMethod):
            return reference()
        else:
            return reference
