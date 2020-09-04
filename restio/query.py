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
    from restio.transaction import Transaction


ModelType = TypeVar("ModelType", bound=BaseModel, covariant=True)
FunctionType = Callable[..., Awaitable[Iterable[ModelType]]]

TRANSACTION_KEYWORD = "transaction"


class BaseQuery(Generic[ModelType]):
    """
    Defines a query object to be processed by a Transaction.

    Every BaseQuery instance has an internal hash that is generated based on the
    function to be invoked and its parameters. This hash is used by Transaction query
    cache to store results for queries already executed in the context of the instance
    of the Transaction.

    Two instances of BaseQuery pointing to the same `function` and with the same `args`
    and `kwargs` provided will resolve on the same hash, and therefore are considered
    to be the same.
    """

    __args: Tuple
    __kwargs: Dict[str, Any]
    __transaction: Optional["Transaction"]
    __has_transaction_argument: bool

    def __init__(
        self, function: FunctionType, *args, **kwargs,
    ):
        self.__function = function
        self.__args = args or tuple()
        self.__kwargs = kwargs or {}
        self.__transaction = None

        # inspect the function to look for the transaction keyword
        params = inspect.signature(function).parameters
        transaction_parameter = params.get(TRANSACTION_KEYWORD, None)
        self.__has_transaction_argument = bool(transaction_parameter)

    def __hash__(self):
        hash_list: List[Any] = [self.__function]

        signature = inspect.signature(self.__function)

        # adds the transaction for binding
        kwargs = self.__kwargs
        if self.__has_transaction_argument:
            kwargs = kwargs.copy()
            kwargs[TRANSACTION_KEYWORD] = None

        parameters = signature.bind(*self.__args, **kwargs)

        # now ignore the transaction keyword
        parameters.arguments.pop(TRANSACTION_KEYWORD, None)

        hash_list.extend(list(parameters.arguments.items()))

        return hash(tuple(hash_list))

    def _get_function(self):
        return self.__function

    def __eq__(self, other):
        if other and isinstance(other, BaseQuery):
            return self.__hash__() == other.__hash__()

        return False

    def __call__(self, transaction: "Transaction"):
        self.__transaction = transaction
        return self

    def __await__(self) -> Generator[Any, Iterable[ModelType], Iterable[ModelType]]:
        kwargs = self.__kwargs

        if self.__has_transaction_argument:
            kwargs = self.__kwargs.copy()
            transaction = self.__transaction or self.__kwargs.get(
                TRANSACTION_KEYWORD, None
            )

            if not transaction:
                raise RuntimeError(
                    f"Transaction not provided for querying {self.__function.__name__}."
                )
            kwargs[TRANSACTION_KEYWORD] = transaction

        return (yield from self.__function(*self.__args, **kwargs).__await__())


def query(function: FunctionType) -> Callable[..., BaseQuery[ModelType]]:
    f"""
    Query decorator.

    This should be used to decorate functions that return query results to be stored by
    a Transaction. Any decorated functions might contain a parameter
    `{TRANSACTION_KEYWORD}` that will receive the Transaction instance object. If this
    parameter is provided when building the query, it gets overwritten when the query
    is executed by a Transaction.

    Queries are useful when performing batch operations on the remote server. The
    Transaction instance will use the query results and store them internally for
    caching purposes.
    """

    @wraps(function)
    def wrapper(*args, **kwargs) -> BaseQuery[ModelType]:
        return BaseQuery(function, *args, **kwargs)

    return wrapper
