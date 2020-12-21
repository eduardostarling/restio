import inspect
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
)

from restio.model import BaseModel

if TYPE_CHECKING:
    from restio.session import Session


Model_co = TypeVar("Model_co", bound=BaseModel, covariant=True)

SESSION_KEYWORD = "session"


class BaseQuery(Generic[Model_co]):
    """
    Defines a query object to be processed by a Session.

    Every BaseQuery instance has an internal hash that is generated based on the
    function to be invoked and its parameters. This hash is used by Session query cache
    to store results for queries already executed in the context of the instance of the
    Session.

    Two instances of BaseQuery pointing to the same `function` and with the same `args`
    and `kwargs` provided will resolve on the same hash, and therefore are considered
    to be the same.
    """

    __args: Tuple
    __kwargs: Dict[str, Any]
    __session: Optional["Session"]
    __has_session_argument: bool

    def __init__(
        self, function: Callable[..., Awaitable[Iterable[Model_co]]], *args, **kwargs,
    ):
        self.__function = function
        self.__args = args or tuple()
        self.__kwargs = kwargs or {}
        self.__session = None

        # inspect the function to look for the session keyword
        params = inspect.signature(function).parameters
        session_parameter = params.get(SESSION_KEYWORD, None)
        self.__has_session_argument = bool(session_parameter)

    def __hash__(self):
        hash_list: List[Any] = [self.__function]

        signature = inspect.signature(self.__function)

        # adds the session for binding
        kwargs = self.__kwargs
        if self.__has_session_argument:
            kwargs = kwargs.copy()
            kwargs[SESSION_KEYWORD] = None

        parameters = signature.bind(*self.__args, **kwargs)

        # now ignore the session keyword
        parameters.arguments.pop(SESSION_KEYWORD, None)

        hash_list.extend(list(parameters.arguments.items()))

        return hash(tuple(hash_list))

    def _get_function(self):
        return self.__function

    def __eq__(self, other):
        if other and isinstance(other, BaseQuery):
            return self.__hash__() == other.__hash__()

        return False

    def __call__(self, session: "Session"):
        self.__session = session
        return self

    def __await__(self) -> Generator[Any, Iterable[Model_co], Iterable[Model_co]]:
        kwargs = self.__kwargs

        if self.__has_session_argument:
            kwargs = self.__kwargs.copy()
            session = self.__session or self.__kwargs.get(SESSION_KEYWORD, None)

            if not session:
                raise RuntimeError(
                    f"Session not provided for querying {self.__function.__name__}."
                )
            kwargs[SESSION_KEYWORD] = session

        return (yield from self.__function(*self.__args, **kwargs).__await__())


def query(
    function: Callable[..., Awaitable[Iterable[Model_co]]]
) -> Callable[..., BaseQuery[Model_co]]:
    f"""
    Query decorator.

    This should be used to decorate functions that return query results to be stored by
    a Session. Any decorated functions might contain a parameter `{SESSION_KEYWORD}`
    that will receive the Session instance object. If this parameter is provided when
    building the query, it gets overwritten when the query is executed by a
    Session.

    Queries are useful when performing batch operations on the remote server. The
    Session instance will use the query results and store them internally for
    caching purposes.
    """

    @wraps(function)
    def wrapper(*args, **kwargs) -> BaseQuery[Model_co]:
        return BaseQuery(function, *args, **kwargs)

    return wrapper
