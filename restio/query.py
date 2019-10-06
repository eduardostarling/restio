from typing import List, Dict, Any
from functools import wraps
import inspect


class BaseQuery:
    """
    Defines a query object to be processed by a Transaction.
    """
    __args: List = []
    __kwargs: Dict[str, Any] = {}

    def __init__(self, function=None, *args, **kwargs):
        self.__function = function
        self.__args = args or []
        self.__kwargs = kwargs or {}

    def __hash__(self):
        hash_list = [self.__function]

        signature = inspect.signature(self.__function)
        parameters = signature.bind(self, *self.__args, **self.__kwargs)
        parameters.arguments.pop('self')
        hash_list.extend(parameters.arguments.items())

        return hash(tuple(hash_list))

    def _get_function(self):
        return self.__function

    def __eq__(self, other):
        if other and isinstance(other, BaseQuery):
            return self.__hash__() == other.__hash__()

        return False

    async def __call__(self, transaction: Any = None) -> List[Any]:
        return await self.__function(transaction, *self.__args, **self.__kwargs)


def query(function=None):
    """
    Query decorator. This should be used to decorate functions that return
    query results to be stored by a Transaction. All decorated functions should
    start with a `self` parameter that will contain the Transaction instance object.

    Queries are useful when performing batch operations on the remote server. The
    Transaction instance will use the query results and store them internally for
    caching purposes.
    """
    params = inspect.signature(function).parameters
    keys = list(params.keys())

    if keys:
        first = keys[0]
        if first != 'self':
            raise AttributeError('The first parameter of a query needs to be "self".')
        keys.remove('self')

    if not keys:
        return BaseQuery(function=function)
    else:

        @wraps(function)
        def wrapper(*args, **kwargs):
            return BaseQuery(function, *args, **kwargs)

        return wrapper
